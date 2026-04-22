"""Store-compliance: DELETE /auth/me must soft-deactivate without destroying bylines.

App Store and Play Store both require an in-app account-deletion path. For a
journalism product we can't hard-delete: published stories carry the reporter's
byline and erasing the user would falsify historical record. Instead we:
  - anonymise PII (name, phone, email, area)
  - flip is_active=False and set deleted_at
  - phone is tombstoned (not nulled) so the unique index still holds and the
    same number can sign up fresh later

This test locks that contract in.
"""

from jose import jwt

from app.config import settings
from app.models.user import User
from app.models.story import Story


def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_delete_me_anonymises_user_and_deactivates(client, db, reporter):
    original_phone = reporter.phone
    headers = {"Authorization": f"Bearer {_token(reporter.id)}"}

    resp = client.delete("/auth/me", headers=headers)

    assert resp.status_code == 204, resp.text

    db.expire_all()
    refreshed = db.query(User).filter(User.id == reporter.id).one()
    assert refreshed.name == "Former Reporter"
    assert refreshed.phone != original_phone
    assert refreshed.phone.startswith("_deleted_")
    assert refreshed.email is None
    assert refreshed.area_name == ""
    assert refreshed.is_active is False
    assert refreshed.deleted_at is not None


def test_delete_me_revokes_subsequent_requests(client, db, reporter):
    headers = {"Authorization": f"Bearer {_token(reporter.id)}"}

    # First call deactivates.
    assert client.delete("/auth/me", headers=headers).status_code == 204

    # Token is valid JWT but the user is now deleted_at+inactive — get_current_user
    # must refuse.
    followup = client.get("/auth/me", headers=headers)
    assert followup.status_code == 401, followup.text


def test_delete_me_preserves_stories(client, db, reporter, sample_story):
    headers = {"Authorization": f"Bearer {_token(reporter.id)}"}

    assert client.delete("/auth/me", headers=headers).status_code == 204

    db.expire_all()
    story = db.query(Story).filter(Story.id == sample_story.id).one()
    # Story must still exist and still reference the (now-anonymised) reporter.
    assert story.reporter_id == reporter.id
    assert story.headline == "Original Headline"


def test_delete_me_requires_auth(client):
    resp = client.delete("/auth/me")
    assert resp.status_code == 401
