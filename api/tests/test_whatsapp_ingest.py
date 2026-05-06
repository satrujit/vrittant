"""Tests for ingest pre-processing helpers."""
from app.services.whatsapp.ingest import strip_forward_boilerplate, word_count


# ── strip_forward_boilerplate ──


def test_strip_no_boilerplate_returns_unchanged():
    assert strip_forward_boilerplate("Hello world") == "Hello world"


def test_strip_basic_forwarded_header():
    raw = "> Forwarded from: Pradip\nThe actual story body."
    assert strip_forward_boilerplate(raw) == "The actual story body."


def test_strip_italic_forwarded_header():
    raw = "> *Forwarded from* Pradip\nThe actual story body."
    assert strip_forward_boilerplate(raw) == "The actual story body."


def test_strip_multiple_quote_lines():
    raw = "> Forwarded from: A\n> Original sender: B\nBody here."
    assert strip_forward_boilerplate(raw) == "Body here."


def test_strip_preserves_quote_lines_without_forwarded_keyword():
    """Don't strip a non-Forwarded quoted-reply marker."""
    raw = "> Some quoted text from earlier\nBody here."
    assert strip_forward_boilerplate(raw) == raw


def test_strip_handles_only_boilerplate():
    raw = "> Forwarded from: X"
    assert strip_forward_boilerplate(raw) == ""


# ── word_count ──


def test_word_count_basic():
    assert word_count("hello world") == 2


def test_word_count_collapses_whitespace():
    assert word_count("hello   world\n\n\tfoo") == 3


def test_word_count_empty_string():
    assert word_count("") == 0


def test_word_count_only_whitespace():
    assert word_count("   \n\n\t") == 0


def test_word_count_odia_text():
    """Word count works for Odia (split on whitespace, not Latin words)."""
    assert word_count("ବିଜେପିର ବିଜୟ ଉତ୍ସବ ପାଳନ") == 4
