"""In-memory English → Odia name registry for fixing Sarvam STT output.

Sarvam's speech-to-text frequently emits Odia place names and personal names
in romanised English (e.g. ``ଆଜି Cuttack ରେ ଯିବି``) instead of script. This
module loads a curated dataset (``api/data/names.txt``) once on first use and
exposes a single substitution helper, :func:`replace_english_names`, that
rewrites English tokens to their Odia equivalents whenever the rest of the
transcript is otherwise correct.

Why module-level singleton instead of, say, a Redis cache?
  * The dataset is tiny (~1k entries, ~30 KB on disk).
  * Sarvam transcripts arrive on the hot path of every recording — adding a
    network round-trip would be silly.
  * Cloud Run instances are short-lived enough that a stale-after-edit risk is
    immaterial; the next deploy reloads the file.

Dataset format (intentionally lenient — the source file was hand-curated and
isn't uniformly structured):

  * ``English,Odia``                — original comma-separated rows
  * ``English Odia``                — single-space rows (most of the file)
  * ``English Word Odia ଓଡ଼ିଆ``     — multi-word English with multi-word Odia
  * ``R.Udayagiri ଆର.ଉଦୟଗିରି``     — internal punctuation preserved

The parser splits each line on the *script boundary* — the first character in
the Odia Unicode block (U+0B00–U+0B7F) — rather than on the first whitespace
or comma. This is the only rule that handles every variant correctly.
"""

from __future__ import annotations

import logging
import os
import re
from threading import Lock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

# names.txt lives at <repo>/api/data/names.txt — three levels up from this file
# (app/services/name_registry.py → app/services → app → api).
_DATA_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "names.txt")
)

# First and last code points of the Odia Unicode block.
_ODIA_RE = re.compile(r"[\u0B00-\u0B7F]")


def _load_lines() -> List[str]:
    """Read the dataset file. Indirected so tests can monkeypatch a fake source."""
    if not os.path.exists(_DATA_FILE):
        logger.warning("name_registry: dataset missing at %s — replacement disabled", _DATA_FILE)
        return []
    with open(_DATA_FILE, "r", encoding="utf-8") as fh:
        return fh.readlines()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_line(line: str) -> Optional[tuple[str, str]]:
    """Split a dataset row into ``(english_lower, odia)`` or ``None`` to skip.

    Splits on the script boundary so multi-word names on either side are kept
    intact. Strips a trailing comma (the original separator in early rows) and
    surrounding whitespace from the English half.
    """
    stripped = line.strip()
    if not stripped:
        return None
    match = _ODIA_RE.search(stripped)
    if not match:
        return None
    english = stripped[: match.start()].rstrip(", \t")
    odia = stripped[match.start() :].strip()
    if not english or not odia:
        return None
    return english.lower(), odia


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_registry_cache: Optional[Dict[str, str]] = None
_max_phrase_words: int = 1
_cache_lock = Lock()


def reset_cache() -> None:
    """Force the next :func:`get_registry` call to re-read the dataset.

    Used by tests to swap fixtures between cases. Production code never needs
    to call this; the cache is built once per process.
    """
    global _registry_cache, _max_phrase_words
    with _cache_lock:
        _registry_cache = None
        _max_phrase_words = 1


def get_registry() -> Dict[str, str]:
    """Return the parsed ``{english_lower: odia}`` map, building it on first call.

    Later duplicates override earlier ones — the curator can fix a bad entry
    by appending a corrected line at the bottom of the file rather than
    hunting for the original.
    """
    global _registry_cache, _max_phrase_words
    if _registry_cache is not None:
        return _registry_cache

    with _cache_lock:
        if _registry_cache is not None:  # double-check under lock
            return _registry_cache

        registry: Dict[str, str] = {}
        max_words = 1
        skipped = 0
        for line in _load_lines():
            parsed = _parse_line(line)
            if parsed is None:
                skipped += 1
                continue
            english, odia = parsed
            registry[english] = odia
            word_count = english.count(" ") + 1
            if word_count > max_words:
                max_words = word_count

        _registry_cache = registry
        _max_phrase_words = max_words
        logger.info(
            "name_registry: loaded %d entries (max phrase = %d words, skipped %d)",
            len(registry),
            max_words,
            skipped,
        )
        return registry


# ---------------------------------------------------------------------------
# Replacer
# ---------------------------------------------------------------------------

# Captures runs of ASCII English text — sequences of word tokens (letters with
# optional internal '.' as in 'R.Udayagiri') joined by single spaces. Trailing
# punctuation (commas, full stops, Odia danda, etc.) is intentionally outside
# the match so the replacement can keep it verbatim.
_ENGLISH_RUN_RE = re.compile(r"[A-Za-z]+(?:\.[A-Za-z]+)*(?:\s+[A-Za-z]+(?:\.[A-Za-z]+)*)*")


def replace_english_names(text: Optional[str]) -> str:
    """Rewrite English place / personal names in ``text`` to their Odia form.

    Tokens that don't match any registry entry are passed through verbatim, so
    arbitrary English (proper nouns the dataset doesn't cover, English loan
    words, etc.) survives untouched. Matching is case-insensitive and prefers
    the longest known phrase ("Cuttack Sadar" wins over "Cuttack").

    Guardrail: if the text contains zero Odia characters we return it as-is.
    The dataset now includes generic loan words ("school", "monday",
    "phone") that would otherwise mangle a fully English transcript or an
    English translation pasted back into the editor. This protects that case
    while still letting the registry rewrite mixed-script Odia STT output.
    """
    if not text:
        return text or ""
    if not _ODIA_RE.search(text):
        return text
    registry = get_registry()
    if not registry:
        return text
    max_words = _max_phrase_words

    def _rewrite_run(match: "re.Match[str]") -> str:
        words = match.group(0).split()
        out: List[str] = []
        i = 0
        while i < len(words):
            replaced = False
            # Greedy: try longest known phrase first so multi-word entries
            # (Cuttack Sadar) beat their single-word prefix (Cuttack).
            upper = min(max_words, len(words) - i)
            for length in range(upper, 0, -1):
                phrase = " ".join(words[i : i + length]).lower()
                odia = registry.get(phrase)
                if odia is not None:
                    out.append(odia)
                    i += length
                    replaced = True
                    break
            if not replaced:
                out.append(words[i])
                i += 1
        return " ".join(out)

    return _ENGLISH_RUN_RE.sub(_rewrite_run, text)
