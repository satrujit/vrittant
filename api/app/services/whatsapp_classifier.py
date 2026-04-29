"""Tiny LLM classifier for the first inbound WhatsApp message in a session.

Returns one of: 'news' | 'chitchat' | 'unclear'.
Used to keep small-talk out of the reviewer queue without dropping
anything ambiguous (those get flagged for triage instead).
"""
import logging
import re

from . import gemini_client

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


async def classify(text: str) -> str:
    """Return 'news' | 'chitchat' | 'unclear'. Never raises."""
    if not text or not text.strip():
        return "unclear"
    try:
        raw = (await gemini_client.chat(
            prompt=text.strip()[:1000],
            system=_SYSTEM,
            max_tokens=5,
            temperature=0.0,
            timeout=3.0,
        )).strip().lower()
    except Exception:
        logger.warning("WhatsApp classifier call failed; defaulting to unclear", exc_info=True)
        return "unclear"
    # Strip surrounding whitespace/punctuation so 'news.' or 'news,' still classifies.
    parts = re.split(r"[^a-z]+", raw)
    label = next((p for p in parts if p), "")
    return label if label in _VALID else "unclear"
