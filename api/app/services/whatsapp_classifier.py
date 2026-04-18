"""Tiny LLM classifier for the first inbound WhatsApp message in a session.

Returns one of: 'news' | 'chitchat' | 'unclear'.
Used to keep small-talk out of the reviewer queue without dropping
anything ambiguous (those get flagged for triage instead).
"""
import logging
import re

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_VALID = {"news", "chitchat", "unclear"}

_SYSTEM = (
    "You classify a WhatsApp message a reporter forwarded to a newsroom. "
    "The message may be in Odia, Hindi, or English. "
    "Reply with exactly one word: news, chitchat, or unclear. "
    "news = press release, news report, factual report of an event, "
    "official statement, or anything a reporter would file. "
    "chitchat = greetings, tests, questions to the editor, thank-yous, "
    "anything not intended as news content. "
    "unclear = if you cannot tell."
)


async def _sarvam_call(prompt: str) -> str:
    url = f"{settings.SARVAM_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sarvam-30b",
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 5,
    }
    async with httpx.AsyncClient(timeout=3) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip().lower()


async def classify(text: str) -> str:
    """Return 'news' | 'chitchat' | 'unclear'. Never raises."""
    if not text or not text.strip():
        return "unclear"
    try:
        raw = await _sarvam_call(text.strip()[:1000])
    except Exception:
        logger.warning("WhatsApp classifier call failed; defaulting to unclear", exc_info=True)
        return "unclear"
    # Strip surrounding whitespace/punctuation so 'news.' or 'news,' still classifies.
    parts = re.split(r"[^a-z]+", raw)
    label = next((p for p in parts if p), "")
    return label if label in _VALID else "unclear"
