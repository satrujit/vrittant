"""Gemini (Google AI Studio) chat + translate wrapper.

Same shape as ``anthropic_client.py``: thin httpx call with cost
logging into the shared ``sarvam_usage_log`` ledger so /usage/cost
reports group spend by story / user / bucket regardless of provider.

Calls hit Google AI Studio's ``generativelanguage.googleapis.com``
directly (not Vertex AI) — billed to whatever GCP project the API key
was created in (vrittant-f5ef2). Auth is API-key in the header; no
service-account token refresh dance needed.

Public API
----------
- ``chat(*, prompt, system=None, model=DEFAULT, max_tokens=2000, temperature=None)``
  Returns the assistant's text directly (no content-block unwrapping).
- ``translate(*, text, source_lang='auto', target_lang='en', ...)``
  Convenience wrapper for translate-style calls.

Cost is logged with ``service="gemini_chat"`` so it appears alongside
anthropic_chat / sarvam_chat rows in the same table.
"""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Optional

import httpx

from ..config import settings
from .sarvam_client import _CURRENT, _write_log_row

logger = logging.getLogger(__name__)


# Pricing in USD per million tokens (Gemini 2.5 Flash-Lite, AI Studio
# tier as of 2026-04-29). Update when Google moves prices. INR conversion
# via the same constant the Anthropic client uses.
_USD_TO_INR = Decimal("84")
_PRICING = {
    "gemini-2.5-flash-lite": {
        "input_per_m": Decimal("0.10"),
        "output_per_m": Decimal("0.40"),
    },
    "gemini-2.5-flash": {
        "input_per_m": Decimal("0.30"),
        "output_per_m": Decimal("2.50"),
    },
    "gemini-2.5-pro": {
        "input_per_m": Decimal("1.25"),
        "output_per_m": Decimal("10.00"),
    },
}


class GeminiError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def is_transient_error(exc: BaseException) -> bool:
    """Same predicate shape as anthropic_client.is_transient_error so
    callers that already know how to retry around Anthropic can swap
    providers without changing their retry logic."""
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, GeminiError) and exc.status_code is not None:
        return exc.status_code in (408, 429, 500, 502, 503, 504)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    *,
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: Optional[float] = None,
    timeout: float = 60.0,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """POST to /v1beta/models/{model}:generateContent. Returns the text.

    The Studio API takes ``contents`` (list of role+parts) and an
    optional ``systemInstruction``. We serialize a single-turn user
    message + optional system block — fine for the chat / translate /
    classify / categorise use cases that we currently call.
    """
    if not _api_key():
        raise GeminiError("GEMINI_API_KEY is not configured", status_code=None)

    resolved_model = model or settings.GEMINI_DEFAULT_MODEL
    url = (
        f"{_base_url()}/v1beta/models/{resolved_model}:generateContent"
    )
    payload: dict = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]},
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if temperature is not None:
        payload["generationConfig"]["temperature"] = temperature

    started = time.monotonic()
    status_code: Optional[int] = None

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            status_code = resp.status_code
            if resp.status_code >= 400:
                body_preview = resp.text[:500]
                _log_failed_call(
                    model=resolved_model,
                    started=started,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )
                raise GeminiError(
                    f"gemini /generateContent {status_code}: {body_preview}",
                    status_code=status_code,
                )
            data = resp.json()
    except (httpx.RequestError, ValueError) as exc:
        _log_failed_call(
            model=resolved_model,
            started=started,
            status_code=status_code,
            error=type(exc).__name__,
        )
        raise GeminiError(f"gemini request failed: {exc}") from exc

    # Token usage. usageMetadata always present on a 200 — we just
    # log what's there and shrug if Google ever drops the field.
    usage = (data.get("usageMetadata") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)
    cached_tokens = int(usage.get("cachedContentTokenCount") or 0)

    cost = _cost_chat(resolved_model, input_tokens, cached_tokens, output_tokens)
    _write_log_row(
        service="gemini_chat",
        model=resolved_model,
        endpoint="/v1beta/generateContent",
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return _extract_text(data)


async def translate(
    *,
    text: str,
    source_lang: str = "auto",
    target_lang: str = "en",
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """Translate ``text`` from ``source_lang`` to ``target_lang``.

    Same return-shape as a plain string. The legacy Sarvam translate
    callers stuff a payload dict and read ``data["translated_text"]``;
    we expose just the string and they unpack at the call site.
    """
    src = "auto-detect" if source_lang == "auto" else source_lang
    system = (
        "You are a faithful translator. Preserve all facts, names, "
        "places, numbers, and quotes exactly. Return ONLY the "
        "translation — no preamble, no commentary, no markdown fences."
    )
    user = (
        f"Translate the following from {src} to {target_lang}:\n\n{text}"
    )
    return await chat(
        prompt=user,
        system=system,
        model=model,
        max_tokens=2000,
        temperature=0.1,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _api_key() -> str:
    return settings.GEMINI_API_KEY or ""


def _base_url() -> str:
    return settings.GEMINI_BASE_URL.rstrip("/") or "https://generativelanguage.googleapis.com"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }


def _normalize_model(model: str) -> str:
    """Map preview / dated suffixes back to the base name we have prices
    for, so cost logging doesn't fall off if Google ships a -09-2025
    revision and we forget to update _PRICING."""
    base = model.split("/")[-1].split(":")[0]
    for canonical in _PRICING.keys():
        if base.startswith(canonical):
            return canonical
    return base


def _cost_chat(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> Decimal:
    p = _PRICING.get(_normalize_model(model))
    if not p:
        logger.warning("gemini_client: no PRICING for %r — cost will be 0", model)
        return Decimal("0")
    # Cached input tokens are billed at 25% of the regular input rate
    # on the Studio API tier; treat conservatively as 25% (rounds up
    # in our favor if Google later changes it).
    fresh_in = max(0, input_tokens - cached_tokens)
    cost_usd = (
        (Decimal(fresh_in) * p["input_per_m"] / Decimal(1_000_000))
        + (Decimal(cached_tokens) * p["input_per_m"] * Decimal("0.25") / Decimal(1_000_000))
        + (Decimal(output_tokens) * p["output_per_m"] / Decimal(1_000_000))
    )
    return (cost_usd * _USD_TO_INR).quantize(Decimal("0.0001"))


def _extract_text(data: dict) -> str:
    """Pull the assistant's text out of a generateContent response.

    Gemini returns ``candidates[0].content.parts[*].text``. We only
    emit a single-turn response so candidate 0 is what we want.
    """
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    out: list[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("text"):
            out.append(p["text"])
    return "".join(out).strip()


def _log_failed_call(
    *,
    model: str,
    started: float,
    status_code: Optional[int],
    error: str,
) -> None:
    _write_log_row(
        service="gemini_chat",
        model=model,
        endpoint="/v1beta/generateContent",
        cost_inr=Decimal("0"),
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
        error=error[:200] if error else None,
    )


import contextlib  # noqa: E402


@contextlib.asynccontextmanager
async def _maybe_client(client: Optional[httpx.AsyncClient], timeout: float):
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(timeout=timeout) as c:
        yield c
