"""Tests for the name registry — parses names.txt and rewrites English names
in Sarvam STT transcripts to their Odia equivalents.

The dataset is irregular:
  * Some lines use a comma (``Angul,ଅନୁଗୋଳ``)
  * Some lines use a single space (``Abinash ଅବିନାଶ``)
  * Some entries are multi-word English (``Cuttack Sadar କଟକ ସଦର``)
  * Some entries have internal punctuation (``R.Udayagiri ଆର.ଉଦୟଗିରି``)
  * Trailing whitespace is sometimes present

These tests pin the parser + replacer behaviour so the contract is preserved
when the dataset is extended later.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from app.services import name_registry


def _seed(monkeypatch, content: str) -> None:
    """Replace the on-disk dataset with an inline string for the test."""
    monkeypatch.setattr(name_registry, "_load_lines", lambda: content.splitlines())
    name_registry.reset_cache()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parses_comma_separated_line(monkeypatch):
    _seed(monkeypatch, "Angul,ଅନୁଗୋଳ\n")
    registry = name_registry.get_registry()
    assert registry["angul"] == "ଅନୁଗୋଳ"


def test_parses_space_separated_line(monkeypatch):
    _seed(monkeypatch, "Abinash ଅବିନାଶ\n")
    registry = name_registry.get_registry()
    assert registry["abinash"] == "ଅବିନାଶ"


def test_parses_multi_word_english_with_multi_word_odia(monkeypatch):
    """Splits on the script boundary, not first whitespace, so 'Cuttack Sadar'
    survives as a single key mapping to 'କଟକ ସଦର'."""
    _seed(monkeypatch, "Cuttack Sadar କଟକ ସଦର\n")
    registry = name_registry.get_registry()
    assert registry["cuttack sadar"] == "କଟକ ସଦର"


def test_parses_internal_period_entry(monkeypatch):
    """``R.Udayagiri ଆର.ଉଦୟଗିରି`` — internal '.' must survive on both sides."""
    _seed(monkeypatch, "R.Udayagiri ଆର.ଉଦୟଗିରି\n")
    registry = name_registry.get_registry()
    assert registry["r.udayagiri"] == "ଆର.ଉଦୟଗିରି"


def test_strips_trailing_whitespace_around_separator(monkeypatch):
    _seed(monkeypatch, "Raghurajpur ,ରଘୁରାଜପୁର\n")
    registry = name_registry.get_registry()
    assert registry["raghurajpur"] == "ରଘୁରାଜପୁର"


def test_skips_blank_and_odia_less_lines(monkeypatch):
    content = textwrap.dedent("""\
        Angul,ଅନୁଗୋଳ


        notreallyanentry
        Abinash ଅବିନାଶ
    """)
    _seed(monkeypatch, content)
    registry = name_registry.get_registry()
    assert set(registry.keys()) == {"angul", "abinash"}


def test_later_entry_overrides_earlier_duplicate(monkeypatch):
    """The dataset has duplicates (e.g. Bargarh twice). The last one wins so a
    curator can fix a bad entry by appending without hunting through the file."""
    _seed(monkeypatch, "Bargarh,WRONG\nBargarh ବରଗଡ଼\n")
    registry = name_registry.get_registry()
    assert registry["bargarh"] == "ବରଗଡ଼"


def test_registry_is_cached(monkeypatch):
    calls = {"n": 0}

    def fake_loader():
        calls["n"] += 1
        return ["Angul,ଅନୁଗୋଳ"]

    monkeypatch.setattr(name_registry, "_load_lines", fake_loader)
    name_registry.reset_cache()

    name_registry.get_registry()
    name_registry.get_registry()
    name_registry.get_registry()
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# Replacer
# ---------------------------------------------------------------------------


def test_replaces_single_word_match(monkeypatch):
    _seed(monkeypatch, "Cuttack କଟକ\n")
    out = name_registry.replace_english_names("ଆଜି Cuttack ରେ ଯିବି")
    assert out == "ଆଜି କଟକ ରେ ଯିବି"


def test_replacement_is_case_insensitive(monkeypatch):
    _seed(monkeypatch, "Cuttack କଟକ\n")
    assert name_registry.replace_english_names("cuttack") == "କଟକ"
    assert name_registry.replace_english_names("CUTTACK") == "କଟକ"
    assert name_registry.replace_english_names("CutTaCk") == "କଟକ"


def test_prefers_longest_phrase_match(monkeypatch):
    _seed(monkeypatch, "Cuttack କଟକ\nCuttack Sadar କଟକ ସଦର\n")
    # Two matches possible: just 'Cuttack' or 'Cuttack Sadar'. The longer
    # phrase wins so the second word doesn't dangle in English.
    out = name_registry.replace_english_names("ଆଜି Cuttack Sadar ରେ")
    assert out == "ଆଜି କଟକ ସଦର ରେ"


def test_leaves_unmatched_english_untouched(monkeypatch):
    _seed(monkeypatch, "Cuttack କଟକ\n")
    out = name_registry.replace_english_names("Donald Trump visited Cuttack today")
    assert out == "Donald Trump visited କଟକ today"


def test_does_not_match_substring(monkeypatch):
    """'Cuttack' must not match inside 'Cuttacking' or 'MyCuttack'."""
    _seed(monkeypatch, "Cuttack କଟକ\n")
    out = name_registry.replace_english_names("Cuttacking is a verb")
    assert out == "Cuttacking is a verb"


def test_handles_punctuation_around_token(monkeypatch):
    """A trailing comma/period on the English token should not block the match
    and must be preserved on the Odia side."""
    _seed(monkeypatch, "Cuttack କଟକ\n")
    out = name_registry.replace_english_names("ଆଜି Cuttack, ରେ ଯିବି।")
    assert out == "ଆଜି କଟକ, ରେ ଯିବି।"


def test_leaves_odia_only_text_unchanged(monkeypatch):
    _seed(monkeypatch, "Cuttack କଟକ\n")
    out = name_registry.replace_english_names("ଆଜି କଟକରେ ଯିବି")
    assert out == "ଆଜି କଟକରେ ଯିବି"


@pytest.mark.parametrize("value", ["", None])
def test_handles_empty_input(monkeypatch, value):
    _seed(monkeypatch, "Cuttack କଟକ\n")
    assert name_registry.replace_english_names(value) == (value or "")


# ---------------------------------------------------------------------------
# Streaming WS rewriter (sarvam.py)
# ---------------------------------------------------------------------------


def test_ws_rewriter_replaces_top_level_transcript_field(monkeypatch):
    from app.routers.sarvam import _rewrite_transcript_message

    _seed(monkeypatch, "Cuttack କଟକ\n")
    msg = '{"type":"data","transcript":"ଆଜି Cuttack ରେ"}'
    out = _rewrite_transcript_message(msg)
    assert json.loads(out)["transcript"] == "ଆଜି କଟକ ରେ"


def test_ws_rewriter_replaces_nested_data_transcript(monkeypatch):
    from app.routers.sarvam import _rewrite_transcript_message

    _seed(monkeypatch, "Cuttack କଟକ\n")
    msg = '{"type":"data","data":{"transcript":"Cuttack today"}}'
    out = _rewrite_transcript_message(msg)
    assert json.loads(out)["data"]["transcript"] == "କଟକ today"


def test_ws_rewriter_passes_through_non_json(monkeypatch):
    from app.routers.sarvam import _rewrite_transcript_message

    _seed(monkeypatch, "Cuttack କଟକ\n")
    # Sarvam may send keepalive pings or future protocol frames we don't
    # understand — never break the relay.
    assert _rewrite_transcript_message("ping") == "ping"


def test_ws_rewriter_returns_unchanged_when_no_match(monkeypatch):
    from app.routers.sarvam import _rewrite_transcript_message

    _seed(monkeypatch, "Cuttack କଟକ\n")
    msg = '{"type":"control","status":"ok"}'
    # No transcript field present → return verbatim (preserves whitespace,
    # key order, etc).
    assert _rewrite_transcript_message(msg) == msg


# ---------------------------------------------------------------------------
# Real dataset smoke
# ---------------------------------------------------------------------------


def test_real_dataset_loads_without_errors():
    """Sanity-check the actual shipped names.txt parses to a non-trivial
    registry. Catches accidental file corruption / encoding regressions."""
    name_registry.reset_cache()
    registry = name_registry.get_registry()
    # Should comfortably hold hundreds of entries (file has ~959 lines).
    assert len(registry) > 500
    # Spot-check a few well-known entries (case-insensitive lookup).
    assert registry.get("cuttack") == "କଟକ"
    assert registry.get("bhubaneswar") == "ଭୁବନେଶ୍ୱର"
    assert registry.get("cuttack sadar") == "କଟକ ସଦର"
