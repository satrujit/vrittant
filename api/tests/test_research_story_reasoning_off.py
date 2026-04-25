"""Lock in two regressions in /admin/news-articles/{id}/research-story:

1. The Sarvam call must send `reasoning_effort=None`. sarvam-30b is a
   reasoning model — chain-of-thought tokens count toward `max_tokens`, so a
   verbose <think> block routinely consumed the entire budget and left the
   JSON answer empty / cut off mid-sentence. Disabling reasoning kills that.

2. When the first response is Romanised Odia (`_odia_ratio < 0.6`), the
   retry path must not crash with `NameError`. The previous version called
   raw `httpx` with undefined `url`/`headers` (refactor leftover) and
   silently fell back to the article's English title. The retry must go
   through `sarvam_client.chat()` like the initial call.
"""

import pytest
from unittest.mock import AsyncMock, patch

from jose import jwt

from app.config import settings
from app.models.news_article import NewsArticle
from app.models.user import User


def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def reviewer_with_token(db):
    user = User(
        id="reviewer-rs",
        name="RS Reviewer",
        phone="+919900099000",
        user_type="reviewer",
        organization="Test Org",
        organization_id="org-test",
    )
    db.add(user)
    db.commit()
    return user, {"Authorization": f"Bearer {_token(user.id)}"}


@pytest.fixture
def article(db):
    a = NewsArticle(
        id="art-rs-1",
        title="Mumbai man wins lottery",
        description="A 42-year-old auto driver from Bandra won 1cr in the state lottery.",
        url="https://example.com/article-rs-1",
        source="Test Source",
        category="general",
    )
    db.add(a)
    db.commit()
    return a


def _ok_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60},
        "model": "sarvam-30b",
    }


def test_research_story_sends_reasoning_effort_none(client, db, reviewer_with_token, article):
    _, headers = reviewer_with_token

    valid_odia = '{"headline": "ମୁମ୍ବାଇର ଜଣେ ବ୍ୟକ୍ତି ଲଟେରୀ ଜିତିଲେ", "body": "ବାନ୍ଦ୍ରାର ୪୨ ବର୍ଷୀୟ ଅଟୋ ଚାଳକ ଏକ କୋଟି ଟଙ୍କା ଜିତିଲେ।", "category": "general", "location": "Mumbai"}'

    with patch("app.routers.news_articles.fetch_article_content", new=AsyncMock(return_value="full text body")), \
         patch("app.routers.news_articles.sarvam_client.chat", new=AsyncMock(return_value=_ok_response(valid_odia))) as mock_chat:
        resp = client.post(
            f"/admin/news-articles/{article.id}/research-story",
            headers=headers,
            json={"word_count": 200},
        )

    assert resp.status_code == 200, resp.text
    assert mock_chat.await_count == 1
    payload = mock_chat.await_args.kwargs["payload"]
    assert "reasoning_effort" in payload, "Must send reasoning_effort to Sarvam"
    assert payload["reasoning_effort"] is None, "reasoning_effort must be None to disable thinking"


def test_research_story_retry_does_not_crash_on_romanised_output(
    client, db, reviewer_with_token, article
):
    """First response is Romanised Odia → retry must run via sarvam_client.chat
    and not raise NameError on `url`/`headers`."""
    _, headers = reviewer_with_token

    romanised = '{"headline": "Mumbai-ra jane byakti lottery jitile", "body": "Bandra-ra 42 barshiya auto driver eka koti tanka jitile.", "category": "general", "location": "Mumbai"}'
    valid_odia = '{"headline": "ମୁମ୍ବାଇର ଜଣେ ବ୍ୟକ୍ତି ଲଟେରୀ ଜିତିଲେ", "body": "ବାନ୍ଦ୍ରାର ୪୨ ବର୍ଷୀୟ ଅଟୋ ଚାଳକ ଏକ କୋଟି ଟଙ୍କା ଜିତିଲେ।", "category": "general", "location": "Mumbai"}'

    chat_mock = AsyncMock(side_effect=[_ok_response(romanised), _ok_response(valid_odia)])

    with patch("app.routers.news_articles.fetch_article_content", new=AsyncMock(return_value="full text body")), \
         patch("app.routers.news_articles.sarvam_client.chat", new=chat_mock):
        resp = client.post(
            f"/admin/news-articles/{article.id}/research-story",
            headers=headers,
            json={"word_count": 200},
        )

    # Retry must have been triggered (odia_ratio of romanised body is 0)
    assert chat_mock.await_count == 2, (
        f"Expected initial + retry = 2 sarvam_client.chat calls, got {chat_mock.await_count}. "
        f"Retry path likely crashed."
    )

    # Retry payload must also disable reasoning
    retry_payload = chat_mock.await_args_list[1].kwargs["payload"]
    assert retry_payload["reasoning_effort"] is None
    assert retry_payload["temperature"] == 0.4  # stricter retry temperature

    # Final response must be the valid Odia one (retry won)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ମୁମ୍ବାଇ" in body["headline"], f"Expected Odia headline, got: {body['headline']}"
