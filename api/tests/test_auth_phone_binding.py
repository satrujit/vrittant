"""Security: /auth/msg91-login must bind the verified phone to the requested phone.

Vuln (pre-fix): handler verified the MSG91 access token but never checked that
the phone the token was issued for matched body.phone. Attacker completed OTP
for their own phone and POSTed body.phone="<victim>" to take over the victim's
account.
"""

from unittest.mock import patch

from app.models.user import User


def _make_users(db):
    attacker = User(
        id="user-attacker",
        name="Attacker",
        phone="+919999999999",
        user_type="reviewer",
        organization="Test Org",
        organization_id="org-test",
    )
    victim = User(
        id="user-victim",
        name="Victim Org Admin",
        phone="+918888888888",
        user_type="org_admin",
        organization="Test Org",
        organization_id="org-test",
    )
    db.add_all([attacker, victim])
    db.commit()
    return attacker, victim


def test_msg91_login_rejects_phone_mismatch(client, db):
    """Token issued for attacker's phone must NOT log in as victim."""
    _make_users(db)

    # MSG91 verifyAccessToken response shape — verified mobile in `message`
    # for success responses. We mock to simulate the token was issued for the
    # attacker's number.
    fake_msg91_response = {"type": "success", "message": "919999999999"}

    with patch("app.routers.auth.verify_access_token", return_value=fake_msg91_response):
        resp = client.post(
            "/auth/msg91-login",
            json={"phone": "+918888888888", "access_token": "attacker-token"},
        )

    assert resp.status_code == 401, (
        f"Expected 401 phone-mismatch rejection, got {resp.status_code}: {resp.text}"
    )


def test_msg91_login_accepts_matching_phone(client, db):
    """Token issued for victim's phone, login as victim — must succeed."""
    _, victim = _make_users(db)

    fake_msg91_response = {"type": "success", "message": "918888888888"}

    with patch("app.routers.auth.verify_access_token", return_value=fake_msg91_response):
        resp = client.post(
            "/auth/msg91-login",
            json={"phone": "+918888888888", "access_token": "victim-token"},
        )

    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


def test_msg91_login_handles_alt_response_shapes(client, db):
    """MSG91 sometimes returns the verified mobile under data.mobile or data.message."""
    _, victim = _make_users(db)

    # data.mobile shape
    with patch(
        "app.routers.auth.verify_access_token",
        return_value={"type": "success", "data": {"mobile": "918888888888"}},
    ):
        resp = client.post(
            "/auth/msg91-login",
            json={"phone": "+918888888888", "access_token": "long-enough-fake-token"},
        )
    assert resp.status_code == 200, resp.text


def test_msg91_login_rejects_when_response_lacks_phone(client, db):
    """If MSG91 doesn't return a verified mobile, reject — fail closed."""
    _make_users(db)

    with patch(
        "app.routers.auth.verify_access_token",
        return_value={"type": "success"},  # no mobile field
    ):
        resp = client.post(
            "/auth/msg91-login",
            json={"phone": "+918888888888", "access_token": "long-enough-fake-token"},
        )

    assert resp.status_code == 401, resp.text
