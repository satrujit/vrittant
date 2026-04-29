"""Dev-only seed script.

Seeds organizations, users, entitlements, and per-org config when the database
is empty. Invoked automatically at app import time when ``settings.ENV != "prod"``,
and can also be run manually:

    python -m app.scripts.seed_dev
"""

from ..database import SessionLocal
from ..models.user import User, Entitlement
from ..models.organization import Organization


def seed_data():
    db = SessionLocal()
    try:
        if db.query(Organization).count() == 0:
            # ── Organizations ──
            orgs = [
                Organization(
                    id="org-pragativadi",
                    name="Pragativadi",
                    slug="pragativadi",
                    display_code="PNS",
                    logo_url="/uploads/org-logos/pragativadi.png",
                    theme_color="#FA6C38",
                ),
                Organization(
                    id="org-sambad",
                    name="Sambad",
                    slug="sambad",
                    display_code="SNS",
                    logo_url="/uploads/org-logos/sambad.jpg",
                    theme_color="#1A1A1A",
                ),
                Organization(
                    id="org-prajaspoorthi",
                    name="Prajaspoorthi",
                    slug="prajaspoorthi",
                    display_code="PJS",
                    logo_url="/uploads/org-logos/prajaspoorthi.png",
                    theme_color="#2A2A8E",
                ),
            ]
            db.add_all(orgs)
            db.flush()

            page_keys = ["dashboard", "stories", "review", "editions", "reporters", "social_export", "news_feed"]

            # ── Pragativadi users ──
            prag_reporter = User(
                name="Satrujit Mohapatra",
                phone="+917008660295",
                area_name="ନୟାଗଡ଼",
                organization="Pragativadi",
                organization_id="org-pragativadi",
                user_type="reporter",
            )
            db.add(prag_reporter)

            prag_reviewer1 = User(
                name="Editor Reviewer",
                phone="+918984336534",
                user_type="org_admin",
                organization="Pragativadi",
                organization_id="org-pragativadi",
            )
            db.add(prag_reviewer1)

            prag_reviewer2 = User(
                name="Aishwarya",
                phone="+918280103897",
                user_type="reviewer",
                organization="Pragativadi",
                organization_id="org-pragativadi",
            )
            db.add(prag_reviewer2)
            db.flush()

            for u in [prag_reviewer1, prag_reviewer2]:
                for key in page_keys:
                    db.add(Entitlement(user_id=u.id, page_key=key))

            # ── Sambad users ──
            sambad_reporter1 = User(
                name="Rajesh Panda",
                phone="+919000000101",
                area_name="ଭୁବନେଶ୍ୱର",
                organization="Sambad",
                organization_id="org-sambad",
                user_type="reporter",
            )
            sambad_reporter2 = User(
                name="Priyanka Sahoo",
                phone="+919000000102",
                area_name="କଟକ",
                organization="Sambad",
                organization_id="org-sambad",
                user_type="reporter",
            )
            sambad_reviewer = User(
                name="Sambad Editor",
                phone="+919000000103",
                user_type="org_admin",
                organization="Sambad",
                organization_id="org-sambad",
            )
            db.add_all([sambad_reporter1, sambad_reporter2, sambad_reviewer])
            db.flush()

            for key in page_keys:
                db.add(Entitlement(user_id=sambad_reviewer.id, page_key=key))

            # ── Prajaspoorthi users ──
            praja_reporter1 = User(
                name="Venkat Reddy",
                phone="+919000000201",
                area_name="Hyderabad",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
                user_type="reporter",
            )
            praja_reporter2 = User(
                name="Lakshmi Devi",
                phone="+919000000202",
                area_name="Vijayawada",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
                user_type="reporter",
            )
            praja_reviewer = User(
                name="Prajaspoorthi Editor",
                phone="+919000000203",
                user_type="org_admin",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
            )
            db.add_all([praja_reporter1, praja_reporter2, praja_reviewer])
            db.flush()

            for key in page_keys:
                db.add(Entitlement(user_id=praja_reviewer.id, page_key=key))

            db.commit()

        # ── Seed OrgConfig for each org ──
        from ..models.org_config import (
            OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        if db.query(OrgConfig).count() == 0:
            all_orgs = db.query(Organization).all()
            for org in all_orgs:
                db.add(OrgConfig(
                    organization_id=org.id,
                    categories=DEFAULT_CATEGORIES,
                    publication_types=DEFAULT_PUBLICATION_TYPES,
                    page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
                    priority_levels=DEFAULT_PRIORITY_LEVELS,
                    default_language="odia",
                ))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
