"""Best-effort LLM categorisation for inbound stories.

Used by the WhatsApp webhook to slot forwarded messages into a category
slot at ingestion time, so reviewers don't have to tag every message
by hand. The contract is best-effort: if Sarvam is unreachable, slow,
or returns garbage, we return ``None`` and the story is created with no
category (the previous behaviour). The webhook MUST NOT fail because
of a categorisation problem.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Keep the prompt small. Sarvam-30b is fluent in Odia/Hindi/English so we
# don't need to translate first — just hand it the message and the
# allowed keys and ask for one back.
_SYSTEM = (
    "You are a news desk categoriser. Read the news message and pick the "
    "single best category from the allowed list. Reply with only the "
    "category key (lowercase, no punctuation, no explanation). If nothing "
    "fits, reply 'other'."
)

# Roughly the worst-case response we want to honour — a single key.
# Larger replies are truncated and pattern-matched against the allowed set.
_MAX_TOKENS = 16
_TIMEOUT_SECONDS = 8.0


async def classify_category(
    text: str,
    allowed_keys: Iterable[str],
) -> Optional[str]:
    """Return the best-fit category key for *text*, or ``None`` on failure.

    *allowed_keys* is the org's configured set of category keys (e.g.
    ``["politics", "sports", "crime", ...]``). Pass an empty iterable
    and we'll skip the call and return ``None``.
    """
    keys = [k for k in allowed_keys if k]
    if not keys or not (text and text.strip()):
        return None

    if not (settings.SARVAM_API_KEY and settings.SARVAM_BASE_URL):
        return None

    user_msg = (
        f"Allowed categories: {', '.join(keys)}\n\n"
        f"News message:\n{text.strip()[:2000]}"
    )

    payload = {
        "model": "sarvam-30b",
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.0,
        "max_tokens": _MAX_TOKENS,
    }

    url = f"{settings.SARVAM_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("categorizer: sarvam call failed: %s", exc)
        return None

    try:
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None

    # Strip <think> tags, lower-case, keep alnum + underscore. The model
    # sometimes wraps a single key in quotes or returns "Key: politics" —
    # the regex sweep handles all of that without us hand-rolling cases.
    cleaned = re.sub(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.strip().lower()
    tokens = re.findall(r"[a-z_]+", cleaned)

    keys_set = {k.lower() for k in keys}
    for tok in tokens:
        if tok in keys_set:
            return tok

    # The model said something but it doesn't match any key — log so we
    # can spot prompt drift, then give up.
    logger.info("categorizer: unmatched reply %r (allowed=%s)", raw[:80], keys)
    return None
