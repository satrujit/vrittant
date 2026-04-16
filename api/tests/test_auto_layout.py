"""Tests for POST /admin/stories/{story_id}/auto-layout."""

from unittest.mock import AsyncMock, patch


VALID_HTML_RESPONSE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Test</title>
<style>body { font-family: serif; max-width: 900px; margin: 0 auto; padding: 40px; }
h1 { font-size: 48px; line-height: 1.1; } p { font-size: 14px; line-height: 1.6; }</style>
</head><body><h1>Original Headline</h1><p>Original paragraph one.</p></body></html>"""


MARKDOWN_WRAPPED_HTML = """```html
<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><h1>Wrapped</h1></body></html>
```"""


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_returns_html(mock_openai, client, auth_header, sample_story):
    """Valid AI response should return HTML content."""
    mock_openai.return_value = VALID_HTML_RESPONSE

    resp = client.post(
        f"/admin/stories/{sample_story.id}/auto-layout",
        json={},
        headers=auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "html" in data
    assert "<!DOCTYPE html>" in data["html"]
    assert "<h1>" in data["html"]

    mock_openai.assert_awaited_once()


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_strips_markdown_fencing(mock_openai, client, auth_header, sample_story):
    """Markdown-fenced HTML should have fencing stripped."""
    mock_openai.return_value = MARKDOWN_WRAPPED_HTML

    resp = client.post(
        f"/admin/stories/{sample_story.id}/auto-layout",
        json={},
        headers=auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "html" in data
    assert "```" not in data["html"]
    assert "<html>" in data["html"]


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_story_not_found(mock_openai, client, auth_header):
    """Request for nonexistent story should return 404."""
    resp = client.post(
        "/admin/stories/nonexistent-id/auto-layout",
        json={},
        headers=auth_header,
    )
    assert resp.status_code == 404
    mock_openai.assert_not_awaited()
