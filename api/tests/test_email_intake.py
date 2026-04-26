"""POST /internal/email/inbound — SendGrid Inbound Parse webhook.

Coverage matrix:
    * dropped_org    — local part doesn't match any org slug
    * dropped_fwd    — forwarder gateway not in OrgConfig.email_forwarders
    * dropped_sender — From: doesn't match a reporter or whitelisted contributor
    * dropped_spam   — spam_score > threshold
    * dropped_dup    — same Message-ID seen for this org
    * accepted (reporter)         — From: matches an existing reporter
    * accepted (new contributor)  — From: matches a whitelist entry → User created
    * accepted (existing contributor) — second email from same contributor → no second User row
    * subject prefix stripping    — "Fwd: Re: …" promotes to clean headline
    * paragraph splitting         — blank-line splits, quote-trailer stripped
"""
from __future__ import annotations

import io
import os
import uuid

import pytest
from app.config import settings
from app.models.email_intake_log import EmailIntakeLog
from app.models.organization import Organization
from app.models.org_config import OrgConfig
from app.models.story import Story
from app.models.user import User


TOKEN = "test-internal-token"
ORG_SLUG = "pragativadi"
ORG_ID = "org-pragativadi-test"
FORWARDER = "pragativadi@gmail.com"
REPORTER_EMAIL = "subash.pragati@gmail.com"
CONTRIB_EMAIL = "shreya.contrib@gmail.com"


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "INBOUND_EMAIL_DOMAIN", "desk.vrittant.in")


@pytest.fixture
def org_setup(db):
    """Pragativadi org + an OrgConfig with the right allowlists +
    one registered reporter Subash."""
    org = Organization(
        id=ORG_ID,
        name="Pragativadi",
        slug=ORG_SLUG,
        is_active=True,
    )
    cfg = OrgConfig(
        organization_id=ORG_ID,
        categories=[],
        publication_types=[],
        page_suggestions=[],
        priority_levels=[],
        edition_schedule=[],
        edition_names=[],
        email_forwarders=[FORWARDER],
        whitelisted_contributors=[
            {"email": CONTRIB_EMAIL, "name": "Shreya Contributor"},
        ],
    )
    reporter = User(
        id="user-subash",
        organization="Pragativadi",
        organization_id=ORG_ID,
        name="Subash Sahoo",
        phone="+919999999999",
        email=REPORTER_EMAIL,
        user_type="reporter",
        area_name="Bhubaneswar",
        is_active=True,
    )
    db.add_all([org, cfg, reporter])
    db.commit()
    return {"org": org, "cfg": cfg, "reporter": reporter}


def _payload(*, msg_id="<msg-1@gmail.com>", subject="Test story",
             from_addr=REPORTER_EMAIL, from_name="Subash Sahoo",
             to_addr=f"{ORG_SLUG}@desk.vrittant.in",
             forwarder=FORWARDER, text="Hello world",
             spam_score="0.1"):
    """Build a SendGrid-shaped multipart payload mirroring the real
    Received: chain Gmail forwarding produces:

        1. SendGrid's own hop at the top — "for <slug@desk.vrittant.in>"
        2. Gmail's hop right below — "for <gateway@gmail.com>"
        3. Original sender's MTA at the bottom

    The parser must skip line (1) (matches our INBOUND_EMAIL_DOMAIN)
    and return line (2)'s gateway. Tests would have falsely passed
    with a single-line fixture, which is what masked the original bug.
    """
    headers = (
        f"Received: by mx.sendgrid.net with SMTP id sg1; "
        f"for <{to_addr}>; Sat, 26 Apr 2026 12:00:00 +0000\r\n"
        f"Received: by mail.gmail.com with SMTP id gm1; "
        f"for <{forwarder}>; Sat, 26 Apr 2026 11:59:50 +0000\r\n"
        f"Message-ID: {msg_id}\r\n"
        f"From: {from_name} <{from_addr}>\r\n"
        f"To: {to_addr}\r\n"
    )
    return {
        "to": to_addr,
        "from": f"{from_name} <{from_addr}>",
        "subject": subject,
        "text": text,
        "headers": headers,
        "spam_score": spam_score,
        "attachments": "0",
    }


# ── Drop cases ────────────────────────────────────────────────────────


def test_drops_when_org_slug_unknown(client, db, org_setup):
    payload = _payload(to_addr="nosuchorg@desk.vrittant.in")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200
    log = db.query(EmailIntakeLog).filter(EmailIntakeLog.status == "dropped_org").one()
    assert log.organization_id is None
    assert db.query(Story).count() == 0


def test_drops_when_forwarder_not_in_allowlist(client, db, org_setup):
    payload = _payload(forwarder="some-other-gateway@gmail.com")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200
    log = db.query(EmailIntakeLog).filter(EmailIntakeLog.status == "dropped_fwd").one()
    assert log.organization_id == ORG_ID
    assert "not in allowlist" in (log.error_msg or "")
    assert db.query(Story).count() == 0


def test_drops_when_sender_not_reporter_or_whitelisted(client, db, org_setup):
    payload = _payload(from_addr="random.stranger@gmail.com", from_name="Stranger")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200
    log = db.query(EmailIntakeLog).filter(EmailIntakeLog.status == "dropped_sender").one()
    assert log.organization_id == ORG_ID
    assert db.query(Story).count() == 0


def test_drops_high_spam_score(client, db, org_setup):
    payload = _payload(spam_score="9.5")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200
    log = db.query(EmailIntakeLog).filter(EmailIntakeLog.status == "dropped_spam").one()
    assert log.organization_id == ORG_ID
    assert db.query(Story).count() == 0


def test_dedupes_by_message_id(client, db, org_setup):
    payload = _payload(msg_id="<dup-1@gmail.com>")
    r1 = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    r2 = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert r1.status_code == r2.status_code == 200
    # Only one accepted row, no second log entry for the dup.
    assert db.query(Story).count() == 1
    assert db.query(EmailIntakeLog).count() == 1


# ── Accept cases ──────────────────────────────────────────────────────


def test_accepts_known_reporter_and_creates_story(client, db, org_setup):
    payload = _payload(subject="Fwd: Re: Local festival report",
                       text="Para one.\n\nPara two with details.")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200

    story = db.query(Story).one()
    assert story.organization_id == ORG_ID
    assert story.reporter_id == "user-subash"
    assert story.status == "submitted"
    # "Fwd: Re:" stripped.
    assert story.headline == "Local festival report"
    # Body split into two paragraphs.
    assert len(story.paragraphs) == 2
    assert story.paragraphs[0]["text"] == "Para one."
    assert story.paragraphs[1]["text"] == "Para two with details."
    # Source labels the inbound origin.
    assert "Email" in (story.source or "")

    log = db.query(EmailIntakeLog).filter(EmailIntakeLog.status == "accepted").one()
    assert log.story_id == story.id


def test_creates_passive_user_for_first_time_whitelisted_contributor(
    client, db, org_setup
):
    payload = _payload(from_addr=CONTRIB_EMAIL, from_name="Shreya Contributor")
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200

    contrib = db.query(User).filter(User.email == CONTRIB_EMAIL).one()
    # Synthetic phone — they can never log in via OTP.
    assert contrib.phone == f"email:{CONTRIB_EMAIL}"
    assert contrib.user_type == "reporter"
    assert contrib.is_active is True
    # Story attributed to the new user.
    story = db.query(Story).one()
    assert story.reporter_id == contrib.id


def test_reuses_existing_contributor_on_second_email(client, db, org_setup):
    payload1 = _payload(msg_id="<c1@gmail.com>", from_addr=CONTRIB_EMAIL,
                        from_name="Shreya Contributor")
    payload2 = _payload(msg_id="<c2@gmail.com>", from_addr=CONTRIB_EMAIL,
                        from_name="Shreya Contributor",
                        subject="Second piece")
    client.post(f"/internal/email/inbound?token={TOKEN}", data=payload1)
    client.post(f"/internal/email/inbound?token={TOKEN}", data=payload2)

    contribs = db.query(User).filter(User.email == CONTRIB_EMAIL).all()
    assert len(contribs) == 1, "second email must NOT create a duplicate user"
    stories = db.query(Story).all()
    assert len(stories) == 2
    assert {s.reporter_id for s in stories} == {contribs[0].id}


# ── Auth / config ────────────────────────────────────────────────────


def test_rejects_missing_token(client, db, org_setup):
    payload = _payload()
    resp = client.post("/internal/email/inbound?token=wrong", data=payload)
    assert resp.status_code == 403


def test_returns_503_when_token_not_configured(client, db, org_setup, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_TOKEN", "")
    payload = _payload()
    resp = client.post(f"/internal/email/inbound?token=anything", data=payload)
    assert resp.status_code == 503


# ── Pure parser helpers ─────────────────────────────────────────────


def test_clean_subject_strips_stacked_prefixes():
    from app.services.email_intake import clean_subject
    assert clean_subject("Fwd: Re: Fwd: Hello") == "Hello"
    assert clean_subject("RE: Status") == "Status"
    assert clean_subject("Plain subject") == "Plain subject"


def test_split_paragraphs_drops_quoted_reply_trailer():
    from app.services.email_intake import split_paragraphs
    body = (
        "Here is my story.\n\n"
        "Second paragraph.\n\n"
        "On Sat, Apr 26, 2026 at 10:00, Subash <s@x.com> wrote:\n"
        "> old quoted text we don't want\n"
    )
    paras = split_paragraphs(body)
    assert len(paras) == 2
    assert paras[0]["text"] == "Here is my story."
    assert paras[1]["text"] == "Second paragraph."


def test_extract_forwarder_pulls_for_address_from_received_chain():
    from app.services.email_intake import extract_forwarder
    headers = (
        "Received: from outbound.example by gmail with SMTP id xyz;\r\n"
        "Received: by 2002:1; for <pragativadi@gmail.com>; Sat 26 Apr\r\n"
        "Subject: hi\r\n"
    )
    assert extract_forwarder(headers) == "pragativadi@gmail.com"


def test_captures_gmail_forwarding_verification_body(client, db, org_setup):
    """Gmail's forwarding-noreply email must be captured (status =
    'forwarding_verification') with the body in error_msg so an
    admin can grep the 9-digit code without a webhook.site detour.
    Without this special-case the email would fail the forwarder
    allowlist and silently drop."""
    payload = _payload(
        from_addr="forwarding-noreply@google.com",
        from_name="Gmail Team",
        subject="(#345678) Gmail Forwarding Confirmation",
        text=(
            "Pragativadi Desk has requested to automatically forward mail to your "
            "email address pragativadi@desk.vrittant.in.\n\n"
            "Confirmation code: 345678901\n\n"
            "To allow Pragativadi Desk to automatically forward mail to your address, "
            "please click the link below to confirm the request:\n"
            "https://mail-settings.google.com/mail/vf-%5BANGjdJ_example%5D\n"
        ),
    )
    resp = client.post(f"/internal/email/inbound?token={TOKEN}", data=payload)
    assert resp.status_code == 200

    log = db.query(EmailIntakeLog).one()
    assert log.status == "forwarding_verification"
    assert log.organization_id == ORG_ID
    assert "345678901" in (log.error_msg or "")
    assert "https://mail-settings.google.com" in (log.error_msg or "")
    # No Story should be created for verification emails.
    assert db.query(Story).count() == 0


def test_extract_forwarder_skips_our_own_sendgrid_hop():
    """Top-most Received line is SendGrid's own — its 'for' address
    points at our INBOUND_EMAIL_DOMAIN. The parser must skip past it
    and return the next 'for' (the actual gateway). This test would
    catch the regression we shipped initially where every real email
    failed the forwarder allowlist check because the parser returned
    SendGrid's hop instead of Gmail's."""
    from app.services.email_intake import extract_forwarder
    headers = (
        "Received: by mx.sendgrid.net with SMTP id sg1; "
        "for <pragativadi@desk.vrittant.in>; Sat, 26 Apr 2026 12:00\r\n"
        "Received: by mail.gmail.com with SMTP id gm1; "
        "for <pragativadi@gmail.com>; Sat, 26 Apr 2026 11:59\r\n"
        "Subject: hi\r\n"
    )
    assert extract_forwarder(headers, "desk.vrittant.in") == "pragativadi@gmail.com"


def test_org_slug_from_to_handles_display_name_and_case():
    from app.services.email_intake import org_slug_from_to
    assert org_slug_from_to(
        "Vrittant Desk <PRAGATIVADI@desk.vrittant.in>",
        "desk.vrittant.in",
    ) == "pragativadi"
    assert org_slug_from_to("foo@otherdomain.com", "desk.vrittant.in") is None
