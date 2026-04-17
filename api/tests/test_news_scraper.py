"""Tests for pure scrape/parse helpers extracted from routers/news_articles.py.

These functions used to live inline inside the news_articles router and were
not unit-testable in isolation — calling them required spinning up the whole
research-story endpoint with a mocked Sarvam response. After Phase 2.3 they
live in services/news_scraper.py and the router only handles HTTP shape, so
the parsing/normalization logic can be exercised here directly.
"""

from app.services.news_scraper import (
    build_research_prompt,
    build_research_user_prompt,
    build_title_search_sql,
    cluster_by_pairs,
    expand_search_terms,
    parse_sarvam_response,
    strip_think_tags,
)


# ---------------------------------------------------------------------------
# build_research_prompt
# ---------------------------------------------------------------------------


def test_build_research_prompt_includes_word_count():
    # Word count appears twice — in the LENGTH directive and in the closing
    # reminder. Both matter; missing the closing reminder caused Sarvam to
    # truncate at ~150 words during early testing.
    prompt = build_research_prompt(word_count=400, instructions=None)

    assert "approximately 400 words" in prompt
    assert "approximately 400 Odia words" in prompt
    assert "ADDITIONAL EDITOR INSTRUCTIONS" not in prompt


def test_build_research_prompt_appends_editor_instructions():
    # When the reviewer passes free-text instructions they must be appended
    # under a clearly labeled section so the LLM doesn't confuse them with
    # the system rules above.
    prompt = build_research_prompt(word_count=600, instructions="Focus on the youth angle")

    assert "ADDITIONAL EDITOR INSTRUCTIONS: Focus on the youth angle" in prompt
    assert "approximately 600 words" in prompt


# ---------------------------------------------------------------------------
# strip_think_tags
# ---------------------------------------------------------------------------


def test_strip_think_tags_removes_closed_thinking_block():
    raw = '<think>let me reason about this</think>{"headline": "Hi"}'

    cleaned = strip_think_tags(raw)

    assert "<think>" not in cleaned
    assert "let me reason" not in cleaned
    assert '{"headline": "Hi"}' in cleaned


def test_strip_think_tags_handles_unclosed_think_with_json_after():
    # Sarvam sometimes emits an unclosed <think> tag and then jumps straight
    # into the JSON object. We must keep the JSON, not strip everything.
    raw = '<think>partial reasoning {"headline": "Real"}'

    cleaned = strip_think_tags(raw)

    assert '{"headline": "Real"}' in cleaned


def test_strip_think_tags_passthrough_when_no_tags():
    raw = '{"headline": "Plain"}'

    assert strip_think_tags(raw).strip() == raw


# ---------------------------------------------------------------------------
# parse_sarvam_response
# ---------------------------------------------------------------------------


def test_parse_sarvam_response_direct_json():
    raw = '{"headline": "H", "body": "B", "category": "politics", "location": "Bhubaneswar"}'

    parsed = parse_sarvam_response(raw)

    assert parsed == {
        "headline": "H",
        "body": "B",
        "category": "politics",
        "location": "Bhubaneswar",
    }


def test_parse_sarvam_response_strips_markdown_fence():
    raw = '```json\n{"headline": "H", "body": "B"}\n```'

    parsed = parse_sarvam_response(raw)

    assert parsed["headline"] == "H"
    assert parsed["body"] == "B"


def test_parse_sarvam_response_extracts_fields_via_regex_when_json_broken():
    # Sarvam sometimes emits unescaped quotes or trailing junk that breaks
    # both json.loads and the newline-fix strategy. The regex fallback must
    # still pull headline/body so the user sees something useful.
    raw = 'garbage "headline": "Real Headline" "body": "Real Body" trailing'

    parsed = parse_sarvam_response(raw)

    assert parsed is not None
    assert parsed["headline"] == "Real Headline"
    assert parsed["body"] == "Real Body"


def test_parse_sarvam_response_returns_none_for_garbage():
    # No JSON-shape, no quoted headline/body fields — caller falls back to
    # the article's own title/description.
    assert parse_sarvam_response("absolutely not parseable garbage text") is None


# ---------------------------------------------------------------------------
# cluster_by_pairs
# ---------------------------------------------------------------------------


def test_cluster_by_pairs_no_pairs_yields_singletons():
    # With no similarity pairs, each article is its own cluster. Order of
    # the input list must be preserved in the output (the router uses the
    # original published_at-desc order to pick lead articles).
    clusters = cluster_by_pairs(["a", "b", "c"], pairs=[])

    assert clusters == [["a"], ["b"], ["c"]]


def test_expand_search_terms_dedups_and_filters_short_and_stopwords():
    # Significant words (>=4 chars, not in stop-list) get appended for partial
    # matching; short words ("the"), stop-words ("with"), and exact dupes are
    # dropped. Original phrase order is preserved at the front.
    expanded = expand_search_terms(["election results", "voter turnout"])

    # Original phrases come first
    assert expanded[0] == "election results"
    assert expanded[1] == "voter turnout"
    # Significant words appended
    assert "election" in expanded
    assert "results" in expanded
    assert "voter" in expanded
    assert "turnout" in expanded
    # No duplicates
    assert len(expanded) == len(set(expanded))


def test_expand_search_terms_caps_at_six_terms():
    # Hard cap protects the SQL query from explosion when the translation
    # is long. Caller (router) relies on this guarantee for the params dict.
    expanded = expand_search_terms(["one two three four five six seven eight nine"])

    assert len(expanded) <= 6


def test_build_title_search_sql_emits_one_param_per_term():
    sql, params = build_title_search_sql(["alpha", "beta"], threshold=0.2, limit=5)

    assert params["q0"] == "alpha"
    assert params["q1"] == "beta"
    assert params["threshold"] == 0.2
    assert params["lim"] == 5
    # Both terms appear in the WHERE clause
    assert ":q0" in sql
    assert ":q1" in sql
    assert "GREATEST" in sql
    assert "LIMIT :lim" in sql


def test_build_research_user_prompt_labels_primary_and_appends_reminder():
    # Primary article gets the "Primary" label; secondary sources get
    # numeric labels. The Odia-script reminder must be appended verbatim
    # so Sarvam doesn't lapse back into English.
    blocks = [
        ("First Title", "Reuters", "politics", "2026-04-01", "First content body"),
        ("Second Title", "PTI", "politics", "2026-04-02", "Second content body"),
    ]

    prompt = build_research_user_prompt(blocks, word_count=500)

    assert "SOURCE 1 (Primary)" in prompt
    assert "SOURCE 2 (2)" in prompt
    assert "First content body" in prompt
    assert "Second content body" in prompt
    assert "Combine information from all 2 sources" in prompt
    assert "ଓଡ଼ିଆ" in prompt
    assert "500 words" in prompt


def test_build_research_user_prompt_single_source_skips_combine_directive():
    # With one source the "combine all sources" line would be misleading,
    # so it must be omitted.
    blocks = [("Only Title", "Reuters", "politics", "2026-04-01", "Only content")]

    prompt = build_research_user_prompt(blocks, word_count=300)

    assert "Combine information" not in prompt
    assert "SOURCE 1 (Primary)" in prompt


def test_cluster_by_pairs_merges_transitively():
    # Pairs (a,b) and (b,c) — union-find should put all three in one cluster.
    # The cluster appears once, in the position of its first member in the
    # input order.
    clusters = cluster_by_pairs(["a", "b", "c", "d"], pairs=[("a", "b"), ("b", "c")])

    assert len(clusters) == 2
    assert sorted(clusters[0]) == ["a", "b", "c"]
    assert clusters[1] == ["d"]
