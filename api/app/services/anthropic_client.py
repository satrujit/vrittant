"""Anthropic Messages API wrapper, modelled on services/sarvam_client.py.

Why this exists
---------------
Anthropic was added to the stack for /api/llm/generate-story (Claude Haiku 4.5).
This module gives us:

  1. **One place** that talks to Anthropic.
  2. **Per-call cost calculation** (USD → INR) in the same ledger
     (`sarvam_usage_log`) that already tracks Sarvam, so existing reports
     surface Anthropic spend without schema changes.
  3. **Attribution** via the same contextvar Sarvam uses
     (``sarvam_client.cost_context``) — request handlers set it once,
     both providers inherit it.

The ledger table is named ``sarvam_usage_log`` for historical reasons; treat
it as the LLM ledger now. Rows from this module set ``service="anthropic_chat"``
and ``model="claude-haiku-4-5"`` so analytics can split by provider.

Failure handling
----------------
Same contract as sarvam_client: cost logging never breaks the calling
request. If anything in the ledger path fails we log a warning and let
the response through unchanged. Upstream HTTP/network errors propagate
to the caller (the generate-story endpoint catches transient ones and
falls back to Sarvam).

Pricing source of truth
-----------------------
Anthropic publishes prices in USD per million tokens. We convert to INR
at log-time using a single constant; reconcile against Anthropic's USD
invoice monthly to catch FX drift.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Optional

import httpx

from ..config import settings
# Reuse Sarvam's contextvar + ledger writer so attribution is a single
# concept across providers. The table name is misleading (it's named
# `sarvam_usage_log`) — treat it as the LLM ledger.
from .sarvam_client import _CURRENT, _write_log_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing (USD per million tokens). Mirrors https://www.anthropic.com/pricing
# as of 2026-04-25. Update when Anthropic moves prices.
# ---------------------------------------------------------------------------

_CHAT_PRICING_PER_M_TOKENS_USD: dict[str, dict[str, Decimal]] = {
    # Claude Haiku 4.5 — the small fast model. $1/$5 per MTok input/output;
    # cache reads $0.10/MTok, cache writes $1.25/MTok. We don't use prompt
    # caching for /api/llm/generate-story (every call is unique reporter
    # notes), so the cache columns stay zero — but they're here for when
    # we wire caching into longer-lived prompts.
    "claude-haiku-4-5": {
        "input": Decimal("1"),
        "cached_read": Decimal("0.10"),
        "cached_write": Decimal("1.25"),
        "output": Decimal("5"),
    },
}

# 1 USD ≈ 85 INR (mid-2026). The ledger is for internal tracking, not
# accounting — small FX drift is fine. Bump this when the dollar moves
# significantly. Check with: `curl https://open.er-api.com/v6/latest/USD`.
_USD_TO_INR: Decimal = Decimal("85")

_PER_MILLION = Decimal("1000000")


def _normalize_model(model: str) -> str:
    return (model or "").strip().lower()


def _cost_chat(
    model: str,
    input_tokens: int,
    cached_read_tokens: int,
    cached_write_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Cost in INR for one Anthropic Messages call."""
    rates = _CHAT_PRICING_PER_M_TOKENS_USD.get(_normalize_model(model))
    if not rates:
        logger.warning(
            "anthropic_client: no PRICING for chat model=%r — cost will be 0",
            model,
        )
        return Decimal("0")
    # Anthropic bills cached_read at the cache_read rate, cached_write at the
    # cache_write rate, and the rest of the input at the standard input rate.
    uncached = max(0, input_tokens - cached_read_tokens - cached_write_tokens)
    usd = (
        Decimal(uncached) * rates["input"]
        + Decimal(cached_read_tokens) * rates["cached_read"]
        + Decimal(cached_write_tokens) * rates["cached_write"]
        + Decimal(output_tokens) * rates["output"]
    ) / _PER_MILLION
    return usd * _USD_TO_INR


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.anthropic.com"
# Anthropic's stable API version header. Bump when we adopt features behind
# a newer version (e.g. "2024-10-22" for prompt caching beta). Current docs:
# https://docs.anthropic.com/en/api/versioning
_API_VERSION = "2023-06-01"


def _base_url() -> str:
    return getattr(settings, "ANTHROPIC_BASE_URL", None) or _DEFAULT_BASE_URL


def _api_key() -> str:
    return getattr(settings, "ANTHROPIC_API_KEY", "") or ""


def _headers() -> dict[str, str]:
    return {
        "x-api-key": _api_key(),
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }


class AnthropicError(RuntimeError):
    """Raised for any Anthropic call failure. Carries the upstream HTTP status
    when there was one (None for network/timeout errors), so the caller can
    decide whether to fall back (transient: 5xx, 429, 529, no-status) or
    bubble up loud (4xx auth/payload bugs)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def is_transient_error(exc: BaseException) -> bool:
    """True when the failure looks like an availability issue worth retrying
    on a different provider. Used by the generate-story fallback chain.

    Transient: HTTP 5xx, 429 (rate-limit), 529 (Anthropic overloaded),
    and any network error (timeout, DNS, connection reset) — these have
    no status_code on the AnthropicError.

    Non-transient: 4xx auth/payload errors (400, 401, 403, 404). Falling
    back on these would just hide our own bug forever.
    """
    if isinstance(exc, AnthropicError):
        if exc.status_code is None:
            return True  # network / timeout
        return exc.status_code >= 500 or exc.status_code in (429, 529)
    # Unexpected exception types (e.g. a JSON parse error) — treat as
    # transient so we still get a result for the user.
    return True


async def chat(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: Optional[float] = None,
    timeout: float = 60.0,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """POST to /v1/messages and write a ledger row.

    ``messages`` follows Anthropic's user/assistant turn shape:
        [{"role": "user", "content": "..."}]
    The system prompt goes in the top-level ``system`` field, not in the
    messages list (different from Sarvam/OpenAI).

    Returns the parsed JSON response. Caller is responsible for picking
    the text out of ``response["content"]`` (a list of content blocks).

    Raises ``AnthropicError`` on any failure. Use ``is_transient_error``
    on the exception to decide whether to fall back.
    """
    if not _api_key():
        raise AnthropicError(
            "ANTHROPIC_API_KEY is not configured", status_code=None
        )

    url = f"{_base_url()}/v1/messages"
    payload: dict = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    started = time.monotonic()
    status_code: Optional[int] = None

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            status_code = resp.status_code
            if resp.status_code >= 400:
                # Don't use raise_for_status — we want the body in the log.
                body_preview = resp.text[:500]
                _log_failed_call(
                    model=model,
                    started=started,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )
                raise AnthropicError(
                    f"anthropic /v1/messages {status_code}: {body_preview}",
                    status_code=status_code,
                )
            data = resp.json()
    except (httpx.RequestError, ValueError) as exc:
        _log_failed_call(
            model=model,
            started=started,
            status_code=status_code,
            error=type(exc).__name__,
        )
        raise AnthropicError(f"anthropic request failed: {exc}") from exc

    usage = (data.get("usage") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cached_read = int(usage.get("cache_read_input_tokens") or 0)
    cached_write = int(usage.get("cache_creation_input_tokens") or 0)

    cost = _cost_chat(model, input_tokens, cached_read, cached_write, output_tokens)
    _write_log_row(
        service="anthropic_chat",
        model=model,
        endpoint="/v1/messages",
        input_tokens=input_tokens,
        # We reuse the existing `cached_tokens` column for cache_read; the
        # invoice-side total already lumps them together, and adding a new
        # column for the (currently unused) cache_write number isn't worth
        # the migration. If we ever turn on prompt caching for real, split
        # this into two columns then.
        cached_tokens=cached_read + cached_write,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return data


def extract_text(response: dict) -> str:
    """Pull the assistant's text out of an Anthropic Messages response.

    Anthropic returns ``content`` as a list of typed blocks
    (text, tool_use, etc.). For our chat-style use we only emit text
    blocks; concatenate them in order.
    """
    blocks = response.get("content") or []
    out: list[str] = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            text = b.get("text") or ""
            if text:
                out.append(text)
    return "".join(out).strip()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _log_failed_call(
    *,
    model: str,
    started: float,
    status_code: Optional[int],
    error: str,
) -> None:
    """Write a ledger row even on failure, with cost=0."""
    _write_log_row(
        service="anthropic_chat",
        model=model,
        endpoint="/v1/messages",
        cost_inr=Decimal("0"),
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
        error=error[:200] if error else None,
    )


import contextlib  # noqa: E402 — kept here so the public API is up top


@contextlib.asynccontextmanager
async def _maybe_client(client: Optional[httpx.AsyncClient], timeout: float):
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(timeout=timeout) as c:
        yield c
