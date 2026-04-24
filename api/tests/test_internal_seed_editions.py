"""Tests for the nightly edition-seeding endpoint."""
from datetime import date

import pytest

from app.config import settings
from app.models.edition import Edition, EditionPage
from app.models.org_config import OrgConfig
from app.models.organization import Organization


PRAGATIVADI_SCHEDULE = [
    {
        "name": "Ed 1",
        "weekdays": [0, 1, 2, 3, 4, 5],
        "pages": [{"page_number": i, "page_name": f"pg_{i}"} for i in range(1, 13)],
    },
    {
        "name": "Avimat",
        "weekdays": [6],
        "pages": [{"page_number": i, "page_name": f"pg_{i}"} for i in range(1, 11)],
    },
]


@pytest.fixture
def internal_token(monkeypatch):
    # `settings` is loaded at import time, so flipping the env var alone
    # has no effect — patch the live settings object directly.
    monkeypatch.setattr(settings, "INTERNAL_TOKEN", "test-token")
    return "test-token"


@pytest.fixture
def organization(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org")
    db.add(org)
    db.commit()
    return org


def _set_schedule(db, org_id, schedule):
    cfg = db.query(OrgConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        cfg = OrgConfig(organization_id=org_id, edition_schedule=schedule)
        db.add(cfg)
    else:
        cfg.edition_schedule = schedule
    db.commit()


def test_creates_editions_for_org_with_schedule(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    target = date(2026, 4, 27)  # Monday
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": target.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["created"]) == 1
    eds = db.query(Edition).filter_by(organization_id=organization.id, publication_date=target).all()
    assert {e.title for e in eds} == {"Ed 1"}
    pages = db.query(EditionPage).filter_by(edition_id=eds[0].id).all()
    assert len(pages) == 12


def test_idempotent_on_repeat(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    target = date(2026, 4, 27)
    payload = {"date": target.isoformat()}
    headers = {"X-Internal-Token": internal_token}
    client.post("/internal/seed-todays-editions", headers=headers, json=payload)
    resp = client.post("/internal/seed-todays-editions", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == []
    assert "Ed 1" in body["skipped"][0]
    eds = db.query(Edition).filter_by(organization_id=organization.id, publication_date=target).all()
    assert len(eds) == 1


def test_sunday_creates_avimat_only(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    target = date(2026, 4, 26)  # Sunday
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": target.isoformat()},
    )
    assert resp.status_code == 200
    titles = {e.title for e in db.query(Edition).filter_by(publication_date=target).all()}
    assert titles == {"Avimat"}


def test_no_op_for_org_without_schedule(client, db, organization, internal_token):
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": "2026-04-27"},
    )
    assert resp.status_code == 200
    assert db.query(Edition).filter_by(organization_id=organization.id).count() == 0


def test_rejects_missing_token(client, db, organization, internal_token):
    resp = client.post(
        "/internal/seed-todays-editions",
        json={"date": "2026-04-27"},
    )
    assert resp.status_code in (401, 403)
