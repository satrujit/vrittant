"""Store-reviewer OTP bypass — temporary, expires 2026-05-07.

App-store reviewers can't receive Indian SMS, so we hardcode a single phone
(+917362837632) + OTP (736826) that issues a real JWT without contacting
MSG91. The bypass auto-expires on a hard date so a forgotten constant can't
become a permanent prod backdoor.

These tests lock in:
  - the reviewer phone + OTP combo issues a token and provisions the user
  - the wrong OTP for the reviewer phone returns 401 (no MSG91 call)
  - check-phone / request-otp / resend-otp all short-circuit cleanly
  - after the expiry date, the bypass is inert

REMOVE THIS FILE WHEN THE BYPASS IS REMOVED (target: 2026-05-07).
"""

from datetime import date, timedelta
from unittest.mock import patch

from app.models.user import User
from app.routers import auth as auth_router


REVIEWER_PHONE = "+917362837632"
REVIEWER_OTP = "736826"


def test_verify_otp_with_reviewer_phone_and_correct_otp_issues_token(client, db):
    resp = client.post(
        "/auth/verify-otp",
        json={"phone": REVIEWER_PHONE, "otp": REVIEWER_OTP},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body and body["access_token"]

    # User auto-provisioned as reporter.
    user = db.query(User).filter(User.phone == REVIEWER_PHONE).one()
    assert user.user_type == "reporter"
    assert user.is_active is True


def test_verify_otp_with_reviewer_phone_and_wrong_otp_returns_401(client, db):
    resp = client.post(
        "/auth/verify-otp",
        json={"phone": REVIEWER_PHONE, "otp": "000000"},
    )
    assert resp.status_code == 401, resp.text
    # User must NOT be created on a failed verify.
    assert db.query(User).filter(User.phone == REVIEWER_PHONE).first() is None


def test_check_phone_for_reviewer_returns_registered_and_provisions(client, db):
    resp = client.post("/auth/check-phone", json={"phone": REVIEWER_PHONE})
    assert resp.status_code == 200, resp.text
    assert resp.json()["registered"] is True
    assert db.query(User).filter(User.phone == REVIEWER_PHONE).one() is not None


def test_request_otp_for_reviewer_skips_msg91(client, db):
    # If MSG91 were called, otp_send would raise (no creds in test env).
    resp = client.post("/auth/request-otp", json={"phone": REVIEWER_PHONE})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["req_id"] == "reviewer"
    assert "reviewer" in body["message"].lower()


def test_resend_otp_for_reviewer_skips_msg91(client):
    resp = client.post("/auth/resend-otp", json={"phone": REVIEWER_PHONE})
    assert resp.status_code == 200, resp.text
    assert "reviewer" in resp.json()["message"].lower()


def test_bypass_inert_after_expiry(client, db):
    """After the hard expiry date the bypass falls through to normal flow."""
    expired = auth_router._REVIEWER_BYPASS_UNTIL + timedelta(days=1)

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return expired

    with patch.object(auth_router, "date", _FakeDate):
        # No reviewer user exists → falls through to 404 from normal lookup.
        resp = client.post(
            "/auth/verify-otp",
            json={"phone": REVIEWER_PHONE, "otp": REVIEWER_OTP},
        )
        assert resp.status_code == 404, resp.text


def test_non_reviewer_phone_unaffected_by_bypass(client, db):
    """Other phones still hit the normal not-registered path."""
    resp = client.post(
        "/auth/verify-otp",
        json={"phone": "+919999999999", "otp": REVIEWER_OTP},
    )
    assert resp.status_code == 404, resp.text
