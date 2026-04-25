"""Lock in: POST /api/llm/chat sends `reasoning_effort="medium"` to Sarvam.

Both sarvam-30b and sarvam-105b are reasoning models. Without an explicit
effort setting they ramble in `reasoning_content` until they hit max_tokens
and the actual `content` comes back empty. Mobile chat (title generation,
auto-polish, generate-story) hits this endpoint, so missing the parameter
silently breaks the mobile experience.

We pick "medium" rather than "high" as the cost/quality compromise for
mobile's mostly-short prompts. The research-story endpoint uses "high"
because its 400-word generations need the larger reasoning budget.
"""

import pytest
from unittest.mock import AsyncMock, patch

from jose import jwt

from app.config import settings
from app.models.user import User


def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def reporter_with_token(db):
    user = User(
        id="reporter-llm",
        name="LLM Reporter",
        phone="+919900088000",
        user_type="reporter",
        area_name="Test",
        organization="Test Org",
        organization_id="org-llm",
    )
    db.add(user)
    db.commit()
    return user, {"Authorization": f"Bearer {_token(user.id)}"}


def _ok_response(content: str = "polished") -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "model": "sarvam-105b",
    }


def test_llm_chat_sends_reasoning_effort_medium(client, db, reporter_with_token):
    _, headers = reporter_with_token

    with patch(
        "app.routers.sarvam.sarvam_client.chat",
        new=AsyncMock(return_value=_ok_response()),
    ) as mock_chat:
        resp = client.post(
            "/api/llm/chat",
            headers=headers,
            json={
                "model": "sarvam-105b",
                "messages": [
                    {"role": "system", "content": "You are an Odia editor."},
                    {"role": "user", "content": "polish this"},
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            },
        )

    assert resp.status_code == 200, resp.text
    payload = mock_chat.await_args.kwargs["payload"]
    assert "reasoning_effort" in payload, (
        "Must send reasoning_effort to Sarvam — without it sarvam-30b/105b "
        "ramble in reasoning_content and the actual answer comes back empty."
    )
    assert payload["reasoning_effort"] == "medium"
