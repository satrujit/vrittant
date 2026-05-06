"""Tests for the WhatsApp i18n catalog and language resolver."""
from app.services.whatsapp.i18n import t, resolve_lang


def test_t_returns_odia_when_lang_is_or():
    assert "ବାର୍ତ୍ତା" in t("thread.first", "or")


def test_t_returns_english_when_lang_is_en():
    assert "Got 1 message" in t("thread.first", "en")


def test_t_returns_hindi_when_lang_is_hi():
    assert "संदेश मिला" in t("thread.first", "hi")


def test_t_falls_back_to_english_for_unknown_lang():
    assert "Got 1 message" in t("thread.first", "xx")


def test_t_returns_key_when_key_unknown():
    """Defensive: a missing key should not raise; should be diagnosable."""
    assert t("nonexistent.key", "or") == "nonexistent.key"


def test_t_substitutes_vars_with_format():
    s = t("thread.update", "en", count=3, text=1, media=2)
    assert "3 messages" in s
    assert "1 text" in s
    assert "2 media" in s


def test_t_substitution_for_locked_story():
    s = t("err.locked", "en", display_id="PNS-26-688")
    assert "PNS-26-688" in s


def test_resolve_lang_uses_org_default(db):
    from app.models.organization import Organization
    from app.models.user import User
    org = Organization(id="o1", name="X", slug="x", default_language="hi")
    user = User(
        id="u1", phone="+91", name="N",
        organization="X", organization_id="o1", user_type="reporter",
    )
    db.add_all([org, user])
    db.commit()
    db.refresh(user, ["org"])
    assert resolve_lang(user) == "hi"


def test_resolve_lang_defaults_to_or_when_user_is_none():
    assert resolve_lang(None) == "or"


def test_resolve_lang_defaults_to_or_when_user_has_no_org():
    """A reporter row without a populated org relation falls back to 'or'."""
    class FakeUser:
        org = None
    assert resolve_lang(FakeUser()) == "or"
