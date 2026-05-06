# WhatsApp Self-Service & Edge-Case Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reporter self-service (today's stories, add-to-existing-story, app deep-link), replace the "done" keyword with interactive buttons, fix 18 known edge cases, and internationalize all replies.

**Architecture:** The existing 533-line `api/app/routers/webhooks_whatsapp.py` is refactored into a dispatcher + service modules under `api/app/services/whatsapp/`. New tables hold a universal media buffer (`whatsapp_pending_media`), content-level dedup (`whatsapp_content_dedup`), and per-sender thread state (`whatsapp_thread_state`). Every reply is routed through `whatsapp/i18n.py` with the locale resolved from `org.default_language`. Universal Links served from `vrittant.in/r/*` open the Flutter mobile app; the web fallback page only shows install-app badges.

**Tech Stack:** FastAPI, SQLAlchemy 2 (Postgres), Pydantic, Gupshup WhatsApp API, Gemini Flash-Lite, Flutter (mobile app), React + Vite (panel for fallback page), Firebase Hosting.

**Design source:** `docs/plans/2026-05-06-whatsapp-self-service-design.md`

**Required skills during execution:**
- @superpowers:test-driven-development for every behavior change
- @superpowers:verification-before-completion before claiming any task done
- @superpowers:using-git-worktrees before starting (isolate from current workspace)

---

## Phase 1 — Foundation: DB schema + reliability layer

### Task 1: SQL migration for the four new tables + columns

**Files:**
- Create: `api/migrations/2026-05-06-whatsapp-self-service.sql`

**Step 1: Write the migration file**

```sql
-- 2026-05-06-whatsapp-self-service.sql
-- Adds the four tables + columns the WhatsApp self-service feature needs.
-- Apply order (idempotent): CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- ALTER TABLE ... ADD COLUMN IF NOT EXISTS where supported.

BEGIN;

-- 1. Universal media buffer
CREATE TABLE IF NOT EXISTS whatsapp_pending_media (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_phone             VARCHAR NOT NULL,
    media_type               VARCHAR NOT NULL,
    gupshup_media_url        TEXT NOT NULL,
    storage_url              TEXT,
    content_hash             VARCHAR,
    caption                  TEXT,
    received_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drained_at               TIMESTAMPTZ,
    drained_into_story_id    UUID REFERENCES stories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_pending_media_sender_received
    ON whatsapp_pending_media (sender_phone, received_at);
CREATE INDEX IF NOT EXISTS ix_pending_media_undrained
    ON whatsapp_pending_media (sender_phone)
    WHERE drained_at IS NULL;

-- 2. Confirmation msg ID on stories (for reply-quote -> add-to-story)
ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS whatsapp_confirm_message_id VARCHAR;
CREATE INDEX IF NOT EXISTS ix_stories_whatsapp_confirm
    ON stories (whatsapp_confirm_message_id)
    WHERE whatsapp_confirm_message_id IS NOT NULL;

-- 3. Active per-sender thread state
CREATE TABLE IF NOT EXISTS whatsapp_thread_state (
    sender_phone           VARCHAR PRIMARY KEY,
    thread_kind            VARCHAR NOT NULL DEFAULT 'new',
    target_story_id        UUID REFERENCES stories(id) ON DELETE SET NULL,
    thread_started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pending_text_count     INT NOT NULL DEFAULT 0,
    pending_media_count    INT NOT NULL DEFAULT 0,
    pending_text_concat    TEXT NOT NULL DEFAULT '',
    interactive_msg_id     VARCHAR,
    audio_warning_shown    BOOLEAN NOT NULL DEFAULT FALSE
);

-- 4. Content-level dedup
CREATE TABLE IF NOT EXISTS whatsapp_content_dedup (
    sender_phone   VARCHAR NOT NULL,
    content_hash   VARCHAR NOT NULL,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sender_phone, content_hash)
);
CREATE INDEX IF NOT EXISTS ix_content_dedup_received
    ON whatsapp_content_dedup (received_at);

-- 5. Org default language
ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS default_language VARCHAR(2) NOT NULL DEFAULT 'or';
COMMENT ON COLUMN organizations.default_language IS
    'ISO 639-1: or=Odia (default), hi=Hindi, en=English. Drives WhatsApp reply locale.';

COMMIT;
```

**Step 2: Apply to UAT via cloud-sql-proxy on port 5433**

Run:
```bash
PW=$(gcloud secrets versions access latest --secret=DATABASE_URL_UAT --project=vrittant-f5ef2 | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')
PGPASSWORD="$PW" psql -h localhost -p 5433 -U postgres -d vrittant_uat \
  -f api/migrations/2026-05-06-whatsapp-self-service.sql
```
Expected: `BEGIN`, `CREATE TABLE`s, `CREATE INDEX`s, `ALTER TABLE`s, `COMMIT`. No errors.

**Step 3: Verify schema**

Run:
```bash
PGPASSWORD="$PW" psql -h localhost -p 5433 -U postgres -d vrittant_uat -c "\d whatsapp_pending_media"
PGPASSWORD="$PW" psql -h localhost -p 5433 -U postgres -d vrittant_uat -c "\d whatsapp_thread_state"
PGPASSWORD="$PW" psql -h localhost -p 5433 -U postgres -d vrittant_uat -c "SELECT default_language FROM organizations LIMIT 3;"
```
Expected: tables exist with columns above; `default_language` returns `or` for all rows.

**Step 4: Apply to prod**

Same command but db=`vrittant` and secret=`DATABASE_URL`.

**Step 5: Commit**

```bash
git add api/migrations/2026-05-06-whatsapp-self-service.sql
git commit -m "feat(api): migration — WhatsApp self-service tables + org default_language"
```

---

### Task 2: SQLAlchemy models for new tables

**Files:**
- Create: `api/app/models/whatsapp_buffer.py`
- Modify: `api/app/models/story.py` (add `whatsapp_confirm_message_id` column)
- Modify: `api/app/models/organization.py` (add `default_language` column)

**Step 1: Write failing test**

Create `api/tests/test_whatsapp_models.py`:

```python
from datetime import datetime, timedelta, timezone
from app.models.whatsapp_buffer import (
    WhatsAppPendingMedia, WhatsAppThreadState, WhatsAppContentDedup,
)


def test_pending_media_can_be_inserted_and_queried(db):
    pm = WhatsAppPendingMedia(
        sender_phone="+919437115223",
        media_type="image",
        gupshup_media_url="https://media.gupshup.io/abc",
        content_hash="sha256-deadbeef",
    )
    db.add(pm); db.commit()
    found = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919437115223").first()
    assert found is not None
    assert found.media_type == "image"
    assert found.drained_at is None


def test_thread_state_defaults(db):
    ts = WhatsAppThreadState(sender_phone="+919437115223")
    db.add(ts); db.commit()
    found = db.query(WhatsAppThreadState).filter_by(sender_phone="+919437115223").first()
    assert found.thread_kind == "new"
    assert found.pending_text_count == 0
    assert found.pending_media_count == 0
    assert found.audio_warning_shown is False


def test_content_dedup_primary_key(db):
    db.add(WhatsAppContentDedup(sender_phone="+91", content_hash="x"))
    db.commit()
    # Second insert with same PK should fail
    db.add(WhatsAppContentDedup(sender_phone="+91", content_hash="x"))
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
```

**Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_whatsapp_models.py -v`
Expected: ImportError — module doesn't exist.

**Step 3: Write the model module**

```python
# api/app/models/whatsapp_buffer.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Boolean, Integer, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


class WhatsAppPendingMedia(Base):
    """Buffers media (photo/PDF/audio/video) that arrives before its accompanying
    text in a WhatsApp forward thread. Drained on submit; can also be auto-finalized
    after a 60s idle window if text never arrives.
    """
    __tablename__ = "whatsapp_pending_media"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_phone = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    gupshup_media_url = Column(Text, nullable=False)
    storage_url = Column(Text)
    content_hash = Column(String)
    caption = Column(Text)
    received_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    drained_at = Column(DateTime(timezone=True))
    drained_into_story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_pending_media_sender_received", "sender_phone", "received_at"),
    )


class WhatsAppThreadState(Base):
    """Per-sender state for the active forward thread. One row per sender at any
    time. `interactive_msg_id` is the Gupshup message id of the [Submit][Cancel]
    interactive message, used to edit-in-place as more forwards arrive.
    """
    __tablename__ = "whatsapp_thread_state"
    sender_phone = Column(String, primary_key=True)
    thread_kind = Column(String, nullable=False, default="new")  # "new" | "add"
    target_story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="SET NULL"))
    thread_started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_message_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    pending_text_count = Column(Integer, nullable=False, default=0)
    pending_media_count = Column(Integer, nullable=False, default=0)
    pending_text_concat = Column(Text, nullable=False, default="")
    interactive_msg_id = Column(String)
    audio_warning_shown = Column(Boolean, nullable=False, default=False)


class WhatsAppContentDedup(Base):
    """Tracks the SHA256 of every inbound text/media payload per sender. Same hash
    seen twice within a 24h window (cleaned up on read or by a daily cron) is a
    duplicate forward — silently skipped.
    """
    __tablename__ = "whatsapp_content_dedup"
    sender_phone = Column(String, primary_key=True)
    content_hash = Column(String, primary_key=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

**Step 4: Add columns to existing models**

Modify `api/app/models/story.py` — add after the existing whatsapp_session column:

```python
    whatsapp_confirm_message_id = Column(String, index=True)
```

Modify `api/app/models/organization.py` — add to the Organization class:

```python
    default_language = Column(String(2), nullable=False, default="or")
```

**Step 5: Re-export from `api/app/models/__init__.py`** if there's a central export list:

```bash
grep -l "WhatsApp\|whatsapp" api/app/models/__init__.py 2>/dev/null
```
If `__init__.py` exports models, add `whatsapp_buffer` exports.

**Step 6: Run tests to verify they pass**

Run: `cd api && pytest tests/test_whatsapp_models.py -v`
Expected: all 3 tests pass.

**Step 7: Commit**

```bash
git add api/app/models/whatsapp_buffer.py api/app/models/story.py api/app/models/organization.py api/tests/test_whatsapp_models.py
git commit -m "feat(api): SQLAlchemy models for WhatsApp self-service tables"
```

---

### Task 3: TCP keepalives on the SQLAlchemy engine

**Files:**
- Modify: `api/app/database.py:17-52` (the engine config block we already inspected)

**Step 1: Look at current connect_args**

Run: `grep -n "connect_args\|pool_kwargs" api/app/database.py | head -20`

**Step 2: Add keepalives**

In `api/app/database.py`, add to the connect_args dict (only for Postgres, not SQLite):

```python
# TCP-level keepalives so the OS detects dead Cloud SQL sockets faster
# than psycopg2's defaults. Without these, a connection killed at the
# network layer can sit in the pool unnoticed until a query mid-flight
# returns "PGRES_TUPLES_OK and no message from the libpq" — observed
# 2026-05-05 causing 503s to Gupshup. pool_pre_ping catches dead-on-
# checkout; keepalives catch dead-mid-query.
if not is_sqlite:
    connect_args.update({
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    })
```

**Step 3: Verify import + boot**

Run: `cd api && python -c "from app.database import engine; print(engine.url)"`
Expected: prints the engine URL with no errors.

**Step 4: Commit**

```bash
git add api/app/database.py
git commit -m "fix(api): TCP keepalives on Cloud SQL engine connect_args"
```

---

### Task 4: Transient-DB-error retry middleware

**Files:**
- Create: `api/app/services/whatsapp/__init__.py` (empty)
- Create: `api/app/services/whatsapp/reliability.py`
- Create: `api/tests/test_whatsapp_retry_middleware.py`
- Modify: `api/app/main.py` to register the middleware on webhook routes only

**Step 1: Write failing test**

```python
# api/tests/test_whatsapp_retry_middleware.py
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.services.whatsapp.reliability import (
    retry_on_transient_db_errors,
    is_transient_db_error,
)


def test_is_transient_recognises_psycopg2_terminating():
    e = OperationalError("stmt", {}, Exception("server closed the connection unexpectedly"))
    assert is_transient_db_error(e) is True


def test_is_transient_skips_unique_violation():
    from sqlalchemy.exc import IntegrityError
    e = IntegrityError("stmt", {}, Exception("duplicate key"))
    assert is_transient_db_error(e) is False


def test_middleware_retries_once_then_succeeds():
    """First call raises a transient error; second call succeeds."""
    app = FastAPI()
    app.middleware("http")(retry_on_transient_db_errors)

    call_count = {"n": 0}

    @app.post("/webhook")
    def webhook():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OperationalError("x", {}, Exception("server closed"))
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/webhook")
    assert r.status_code == 200
    assert call_count["n"] == 2


def test_middleware_returns_503_after_retry_also_fails():
    app = FastAPI()
    app.middleware("http")(retry_on_transient_db_errors)

    @app.post("/webhook")
    def webhook():
        raise OperationalError("x", {}, Exception("server closed"))

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/webhook")
    assert r.status_code == 503
```

**Step 2: Run test, expect ImportError**

Run: `cd api && pytest tests/test_whatsapp_retry_middleware.py -v`

**Step 3: Implement**

```python
# api/app/services/whatsapp/reliability.py
"""Transient-error retry middleware for webhook routes.

A Cloud SQL connection can die mid-query (network blip, idle reaping,
maintenance failover). Without this middleware, FastAPI raises an
OperationalError, Cloud Run logs a 503, and Gupshup gives up after a
handful of retries — losing the inbound forward.

Strategy: catch transient SQLAlchemy/psycopg2 errors once, invalidate
the engine pool, sleep 50ms, replay the request. If retry also fails
we surface the 503 (Gupshup will still retry; at least we tried).
"""
import asyncio
import logging
from sqlalchemy.exc import OperationalError, DBAPIError
from fastapi import Request, Response

log = logging.getLogger("whatsapp.reliability")

_TRANSIENT_HINTS = (
    "server closed the connection",
    "connection reset",
    "ssl syscall error",
    "no message from the libpq",
    "could not connect to server",
    "connection refused",
    "PGRES_TUPLES_OK",
)


def is_transient_db_error(exc: BaseException) -> bool:
    """True for connection-death style errors that warrant a retry.
    False for logical errors (unique violation, FK violation, etc.) that
    a retry would never resolve.
    """
    if not isinstance(exc, (OperationalError, DBAPIError)):
        return False
    msg = str(exc).lower()
    return any(h.lower() in msg for h in _TRANSIENT_HINTS)


async def retry_on_transient_db_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except (OperationalError, DBAPIError) as exc:
        if not is_transient_db_error(exc):
            raise
        log.warning(
            "transient DB error on %s %s — invalidating pool + retrying once: %r",
            request.method, request.url.path, exc,
        )
        # Invalidate pool; next checkout opens a fresh connection
        from app.database import engine
        engine.dispose(close=False)
        await asyncio.sleep(0.05)
        try:
            return await call_next(request)
        except Exception as exc2:
            log.error(
                "retry also failed on %s %s: %r",
                request.method, request.url.path, exc2,
            )
            return Response(
                content='{"error":"transient db error"}',
                status_code=503,
                media_type="application/json",
            )
```

**Step 4: Wire into main.py — webhook routes only**

In `api/app/main.py`, add a route-scoped middleware. FastAPI doesn't have built-in path-scoped middleware, so use a small dispatch wrapper:

```python
# Near the existing middleware registrations
from app.services.whatsapp.reliability import retry_on_transient_db_errors

@app.middleware("http")
async def _whatsapp_retry_wrapper(request: Request, call_next):
    if request.url.path.startswith("/webhooks/whatsapp"):
        return await retry_on_transient_db_errors(request, call_next)
    return await call_next(request)
```

**Step 5: Run tests**

Run: `cd api && pytest tests/test_whatsapp_retry_middleware.py -v`
Expected: 4 tests pass.

**Step 6: Commit**

```bash
git add api/app/services/whatsapp/__init__.py api/app/services/whatsapp/reliability.py api/app/main.py api/tests/test_whatsapp_retry_middleware.py
git commit -m "feat(api): retry middleware for transient DB errors on /webhooks/whatsapp/*"
```

---

## Phase 2 — i18n catalog

### Task 5: i18n module skeleton + resolver

**Files:**
- Create: `api/app/services/whatsapp/i18n.py`
- Create: `api/tests/test_whatsapp_i18n.py`

**Step 1: Write failing test**

```python
# api/tests/test_whatsapp_i18n.py
import pytest
from app.services.whatsapp.i18n import t, resolve_lang


def test_t_returns_odia_when_lang_is_or():
    assert "ବାର୍ତ୍ତା" in t("thread.first", "or")


def test_t_returns_english_when_lang_is_en():
    assert "Got 1 message" in t("thread.first", "en")


def test_t_falls_back_to_english_for_unknown_lang():
    assert "Got 1 message" in t("thread.first", "xx")


def test_t_substitutes_vars():
    s = t("thread.update", "en", count=3, text=1, media=2)
    assert "3 messages" in s
    assert "1 text" in s
    assert "2 media" in s


def test_resolve_lang_uses_org_default(db):
    from app.models.organization import Organization
    from app.models.user import User
    org = Organization(id="o1", name="X", slug="x", default_language="hi")
    user = User(id="u1", phone="+91", name="N", organization="X", organization_id="o1", user_type="reporter")
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    assert resolve_lang(user) == "hi"


def test_resolve_lang_defaults_to_or_when_no_org():
    assert resolve_lang(None) == "or"
```

**Step 2: Run test, expect ImportError**

Run: `cd api && pytest tests/test_whatsapp_i18n.py -v`

**Step 3: Implement skeleton**

```python
# api/app/services/whatsapp/i18n.py
"""WhatsApp reply localisation.

One catalog, three locales (or/hi/en). Lookup falls back to English
on missing keys or unknown locales. Variable substitution via .format().
"""
from __future__ import annotations
from typing import Optional

# Catalog populated incrementally during implementation. Keys use dot.notation.
STRINGS: dict[str, dict[str, str]] = {
    "thread.first": {
        "or": "📥 ୧ଟି ବାର୍ତ୍ତା ପାଇଲି।\nଆଉ ଫରୱାର୍ଡ କରନ୍ତୁ କିମ୍ବା ସରିଲେ ଟ୍ୟାପ କରନ୍ତୁ।",
        "hi": "📥 1 संदेश मिला।\nऔर भेजें या समाप्त हो जाने पर टैप करें।",
        "en": "📥 Got 1 message.\nForward more, or tap when finished.",
    },
    "thread.update": {
        "or": "📥 {count}ଟି ବାର୍ତ୍ତା ପାଇଲି ({text} ଲେଖା + {media} ମିଡିଆ)।\nଆଉ ଫରୱାର୍ଡ କରନ୍ତୁ କିମ୍ବା ସରିଲେ ଟ୍ୟାପ କରନ୍ତୁ।",
        "hi": "📥 {count} संदेश मिले ({text} पाठ + {media} मीडिया)।\nऔर भेजें या समाप्त हो जाने पर टैप करें।",
        "en": "📥 Got {count} messages ({text} text + {media} media).\nForward more, or tap when finished.",
    },
    # Buttons
    "btn.submit":  {"or": "✓ ଖବର ଦାଖଲ କରନ୍ତୁ", "hi": "✓ खबर जमा करें", "en": "✓ Submit Story"},
    "btn.cancel":  {"or": "✕ ବାତିଲ କରନ୍ତୁ",     "hi": "✕ रद्द करें",       "en": "✕ Cancel"},
    "btn.add":     {"or": "➕ ଅଧିକ ଯୋଡ଼ନ୍ତୁ",   "hi": "➕ और जोड़ें",       "en": "➕ Add more"},
    "btn.today":   {"or": "📋 ଆଜିର ଖବର",       "hi": "📋 आज की खबरें",   "en": "📋 Today"},
    "btn.openApp": {"or": "📱 ଆପରେ ଦେଖନ୍ତୁ",  "hi": "📱 ऐप में खोलें",   "en": "📱 Open in app"},
    "btn.saveAdd": {"or": "✓ ଯୋଡ଼ାଣ ସଞ୍ଚୟ",   "hi": "✓ जोड़ सहेजें",      "en": "✓ Save additions"},
    "btn.discard": {"or": "✕ ତ୍ୟାଗ କରନ୍ତୁ",     "hi": "✕ छोड़ें",           "en": "✕ Discard"},
    "btn.menu":    {"or": "☰ ମେନୁ ଖୋଲନ୍ତୁ",    "hi": "☰ मेनू खोलें",       "en": "☰ Open menu"},

    # Story saved
    "saved.header": {"or": "✓ ଖବର ସଞ୍ଚୟ ହୋଇଛି", "hi": "✓ खबर सहेजी गई",   "en": "✓ Story saved"},
    "saved.id":     {"or": "ID: {display_id}",   "hi": "ID: {display_id}", "en": "ID: {display_id}"},

    # Add-to-story
    "adding.header": {
        "or": "➕ {display_id}ରେ ଯୋଡ଼ୁଛି",
        "hi": "➕ {display_id} में जोड़ रहे हैं",
        "en": "➕ Adding to {display_id}",
    },
    "adding.update": {
        "or": "ଆଉ {count}ଟି ପାଇଲି ({text} ଲେଖା + {media} ମିଡିଆ)।",
        "hi": "और {count} मिले ({text} पाठ + {media} मीडिया)।",
        "en": "Got {count} more ({text} text + {media} media).",
    },

    # Today list
    "today.header": {
        "or": "📋 ଆଜିର ଆପଣଙ୍କର ଖବର ({count}):",
        "hi": "📋 आज की आपकी खबरें ({count}):",
        "en": "📋 Your stories today ({count}):",
    },
    "today.empty": {
        "or": "📭 ଆଜି କିଛି ଖବର ଦାଖଲ ହୋଇନାହିଁ। ଏକ ଖବର ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "📭 आज कोई खबर जमा नहीं हुई। एक खबर भेजें।",
        "en": "📭 No stories filed today. Forward a story to submit.",
    },
    "today.overflow": {
        "or": "(+{n}ଟି ଅଧିକ — ଆପରେ ଦେଖନ୍ତୁ)",
        "hi": "(+{n} और — ऐप में देखें)",
        "en": "(+{n} more — tap below to see all)",
    },

    # Edge-case replies
    "err.unregistered": {
        "or": "ଆପଣଙ୍କ ନମ୍ବର ବ୍ରତ୍ତାନ୍ତର ସାମ୍ବାଦିକ ରୂପେ ପଞ୍ଜିକୃତ ନୁହେଁ। ସମ୍ପାଦକଙ୍କ ସହ ଯୋଗାଯୋଗ କରନ୍ତୁ।",
        "hi": "आपका नंबर वृत्तांत के संवाददाता के रूप में पंजीकृत नहीं है। संपादक से संपर्क करें।",
        "en": "Your number isn't registered. Please contact your editor.",
    },
    "err.tooShort": {
        "or": "ଯଥେଷ୍ଟ ବିଷୟବସ୍ତୁ ଖୋଜା ଗଲା ନାହିଁ (୨୦+ ଶବ୍ଦ ଦରକାର)। ଅଧିକ ବିବରଣୀ ସହ ପୁନଃ ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "पर्याप्त सामग्री नहीं मिली (20+ शब्द चाहिए)। अधिक विवरण के साथ दोबारा भेजें।",
        "en": "Couldn't read enough content (need 20+ words). Please re-forward with more detail.",
    },
    "err.sticker": {
        "or": "ଷ୍ଟିକର/ସ୍ଥାନ ସଞ୍ଚୟ ହୋଇନାହିଁ। ଖବର ଦାଖଲ ପାଇଁ ଲେଖା କିମ୍ବା ଫଟୋ ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "स्टिकर/स्थान सहेजा नहीं गया। खबर जमा करने के लिए पाठ या फोटो भेजें।",
        "en": "Sticker/location not saved. Forward text or photos to submit a story.",
    },
    "err.locked": {
        "or": "ଖବର {display_id} ଲକ୍ କରାଯାଇଛି। ନୂଆ ବିଷୟବସ୍ତୁ ଏକ ନୂଆ ଖବର ଭାବେ ସଞ୍ଚୟ ହେବ।",
        "hi": "खबर {display_id} लॉक हो चुकी है। नई सामग्री एक नई खबर के रूप में सहेजी जाएगी।",
        "en": "Story {display_id} is locked. New content will be saved as a fresh story.",
    },
    "err.crossReporter": {
        "or": "ଅନ୍ୟ ସାମ୍ବାଦିକଙ୍କ ଖବରକୁ ସମ୍ପାଦନ କରିହେବ ନାହିଁ।",
        "hi": "अन्य संवाददाता की खबर संपादित नहीं की जा सकती।",
        "en": "Cannot edit another reporter's story.",
    },
    "err.empty": {
        "or": "ଦାଖଲ କରିବାକୁ କିଛି ନାହିଁ। ପ୍ରଥମେ ଆପଣଙ୍କ ଖବର ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "जमा करने के लिए कुछ नहीं है। पहले अपनी खबर भेजें।",
        "en": "Nothing to submit yet. Forward your story first.",
    },
    "err.cancelled": {
        "or": "ବାତିଲ ହୋଇଛି। ଆପଣଙ୍କ ଫରୱାର୍ଡ ସଞ୍ଚୟ ହୋଇନାହିଁ।",
        "hi": "रद्द किया गया। आपकी फॉरवर्ड सहेजी नहीं गईं।",
        "en": "Cancelled. Your forwards were not saved.",
    },
    "err.tooOld": {
        "or": "ଏହି ଖବରଟି ୱାଟସ୍ଆପରୁ ସମ୍ପାଦନ କରିବାକୁ ବହୁତ ପୁରୁଣା। ମୋବାଇଲ ଆପ ବ୍ୟବହାର କରନ୍ତୁ।",
        "hi": "यह खबर WhatsApp से संपादित करने के लिए बहुत पुरानी है। मोबाइल ऐप का उपयोग करें।",
        "en": "This story is too old to edit from WhatsApp. Use the mobile app.",
    },
    "hint.audio": {
        "or": "ଓଡ଼ିଆ ଡିକ୍ଟେସନ ପାଇଁ, ବ୍ରତ୍ତାନ୍ତ ମୋବାଇଲ ଆପ ଲାଇଭ୍ ଟ୍ରାନ୍ସକ୍ରିପସନ ଦିଏ।",
        "hi": "ओडिया डिक्टेशन के लिए, वृत्तांत मोबाइल ऐप लाइव ट्रांसक्रिप्शन देता है।",
        "en": "For Odia dictation, the Vrittant mobile app gives you live transcription.",
    },

    # Menu
    "menu.prompt": {
        "or": "☰ ଆପଣ କ'ଣ କରିବାକୁ ଚାହାଁନ୍ତି?",
        "hi": "☰ आप क्या करना चाहते हैं?",
        "en": "☰ What would you like to do?",
    },
}


def t(key: str, lang: str, **vars) -> str:
    """Translate `key` into `lang`, falling back to English on miss.
    Substitutes `vars` via str.format if any are provided.
    """
    bucket = STRINGS.get(key, {})
    s = bucket.get(lang) or bucket.get("en") or key
    return s.format(**vars) if vars else s


def resolve_lang(user) -> str:
    """Resolve a User to their org's WhatsApp reply language.

    Returns 'or' (Odia) by default — appropriate for the existing
    Pragativadi/Sambad orgs. Org admins flip to 'hi' or 'en' via the
    Settings panel (UI dropdown TBD; for now seeded via SQL per org).
    """
    if user is None:
        return "or"
    org = getattr(user, "org", None)
    if org is None:
        return "or"
    return getattr(org, "default_language", None) or "or"
```

**Step 4: Run tests**

Run: `cd api && pytest tests/test_whatsapp_i18n.py -v`
Expected: 6 tests pass.

**Step 5: Commit**

```bash
git add api/app/services/whatsapp/i18n.py api/tests/test_whatsapp_i18n.py
git commit -m "feat(api): WhatsApp i18n catalog (or/hi/en) + lang resolver"
```

---

## Phase 3 — Dispatcher refactor (no behavior change)

### Task 6: Inbound message classifier

**Files:**
- Create: `api/app/services/whatsapp/classifier.py`
- Create: `api/tests/test_whatsapp_classifier_v2.py`

**Step 1: Write failing tests covering each classification**

```python
# api/tests/test_whatsapp_classifier_v2.py
from app.services.whatsapp.classifier import classify, MessageKind


def test_classify_button_reply():
    payload = {"type": "interactive", "interactive": {"type": "button_reply",
        "button_reply": {"id": "submit_thread"}}}
    assert classify(payload) == MessageKind.BUTTON


def test_classify_quoted_reply():
    payload = {"type": "text", "context": {"id": "wamid.HBgM..."},
               "text": {"body": "correction: BJP won 4"}}
    assert classify(payload) == MessageKind.QUOTED_REPLY


def test_classify_text_forward():
    payload = {"type": "text", "text": {"body": "Bypoll results announced..."}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_image_forward():
    payload = {"type": "image", "image": {"id": "media123"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_document_forward():
    payload = {"type": "document", "document": {"id": "doc123", "filename": "report.pdf"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_audio_forward():
    payload = {"type": "audio", "audio": {"id": "aud123"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_sticker_skip():
    payload = {"type": "sticker"}
    assert classify(payload) == MessageKind.SKIP_STICKER


def test_classify_location_skip():
    payload = {"type": "location"}
    assert classify(payload) == MessageKind.SKIP_LOCATION


def test_classify_contact_skip():
    payload = {"type": "contacts"}
    assert classify(payload) == MessageKind.SKIP_CONTACT


def test_classify_unknown_skip():
    assert classify({"type": "video_note"}) == MessageKind.SKIP_OTHER
```

**Step 2: Run, expect ImportError**

Run: `cd api && pytest tests/test_whatsapp_classifier_v2.py -v`

**Step 3: Implement**

```python
# api/app/services/whatsapp/classifier.py
"""Classify a Gupshup inbound payload into one of a small set of kinds.

The dispatcher in webhooks_whatsapp uses the result to delegate to the
right handler. Keeping classification pure-functional + payload-shaped
makes the dispatcher trivially testable.
"""
from enum import Enum


class MessageKind(str, Enum):
    BUTTON = "button"            # interactive button reply (submit/cancel/add/today/menu)
    QUOTED_REPLY = "quoted"      # text or media replying to a previous outbound
    FORWARD = "forward"          # standard text / image / document / audio / video
    SKIP_STICKER = "sticker"
    SKIP_LOCATION = "location"
    SKIP_CONTACT = "contact"
    SKIP_OTHER = "skip_other"    # any unclassified/uninteresting type


_FORWARD_TYPES = {"text", "image", "document", "audio", "video"}


def classify(payload: dict) -> MessageKind:
    """Pure function. `payload` is the inner message dict from Gupshup,
    not the outer envelope. Caller must extract `payload['payload']` or
    equivalent before calling.
    """
    t = payload.get("type")
    if t == "interactive":
        return MessageKind.BUTTON
    if payload.get("context"):
        return MessageKind.QUOTED_REPLY
    if t in _FORWARD_TYPES:
        return MessageKind.FORWARD
    if t == "sticker":
        return MessageKind.SKIP_STICKER
    if t == "location":
        return MessageKind.SKIP_LOCATION
    if t == "contacts":
        return MessageKind.SKIP_CONTACT
    return MessageKind.SKIP_OTHER
```

**Step 4: Run tests**

Run: `cd api && pytest tests/test_whatsapp_classifier_v2.py -v`
Expected: all 10 pass.

**Step 5: Commit**

```bash
git add api/app/services/whatsapp/classifier.py api/tests/test_whatsapp_classifier_v2.py
git commit -m "feat(api): WhatsApp message-kind classifier"
```

---

### Task 7: Content hash + dedup helpers

**Files:**
- Create: `api/app/services/whatsapp/dedup.py`
- Create: `api/tests/test_whatsapp_dedup.py`

**Step 1: Write failing test**

```python
# api/tests/test_whatsapp_dedup.py
from datetime import datetime, timedelta, timezone
from app.services.whatsapp.dedup import (
    hash_text, hash_bytes, is_duplicate, mark_seen,
)
from app.models.whatsapp_buffer import WhatsAppContentDedup


def test_hash_text_is_deterministic():
    h1 = hash_text("hello world")
    h2 = hash_text("hello world")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_hash_text_normalises_whitespace():
    assert hash_text("hello  world\n") == hash_text("hello world")


def test_hash_bytes_is_deterministic():
    assert hash_bytes(b"abc") == hash_bytes(b"abc")
    assert hash_bytes(b"abc") != hash_bytes(b"abd")


def test_is_duplicate_returns_false_when_unseen(db):
    assert is_duplicate(db, "+91", "deadbeef") is False


def test_is_duplicate_returns_true_after_mark_seen(db):
    mark_seen(db, "+91", "deadbeef"); db.commit()
    assert is_duplicate(db, "+91", "deadbeef") is True


def test_mark_seen_idempotent(db):
    mark_seen(db, "+91", "x"); db.commit()
    mark_seen(db, "+91", "x"); db.commit()  # second call should not raise
```

**Step 2: Run, expect ImportError**

**Step 3: Implement**

```python
# api/app/services/whatsapp/dedup.py
"""Content-level dedup for WhatsApp inbound payloads.

Catches the case where a reporter forwards the same image/text twice
in the same session (intentional or accidental WhatsApp re-send).
Distinct from `whatsapp_inbound_dedup` which keys on Gupshup's
message_id (only catches retries of the *same* webhook delivery).
"""
import hashlib
import re
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppContentDedup


_WS_RE = re.compile(r"\s+")


def hash_text(text: str) -> str:
    """SHA256 of whitespace-normalised text. So 'a  b\\n' == 'a b'."""
    norm = _WS_RE.sub(" ", text).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_duplicate(db: Session, sender_phone: str, content_hash: str) -> bool:
    return db.query(WhatsAppContentDedup).filter_by(
        sender_phone=sender_phone, content_hash=content_hash,
    ).first() is not None


def mark_seen(db: Session, sender_phone: str, content_hash: str) -> None:
    """Idempotent. Postgres upsert; on SQLite (tests) try-except."""
    if db.bind.dialect.name == "postgresql":
        stmt = pg_insert(WhatsAppContentDedup).values(
            sender_phone=sender_phone, content_hash=content_hash,
        ).on_conflict_do_nothing()
        db.execute(stmt)
        return
    # SQLite (tests)
    if not is_duplicate(db, sender_phone, content_hash):
        db.add(WhatsAppContentDedup(sender_phone=sender_phone, content_hash=content_hash))
```

**Step 4: Run tests; commit**

```bash
cd api && pytest tests/test_whatsapp_dedup.py -v
git add api/app/services/whatsapp/dedup.py api/tests/test_whatsapp_dedup.py
git commit -m "feat(api): content-level dedup helpers for WhatsApp"
```

---

### Task 8: Pending media buffer service

**Files:**
- Create: `api/app/services/whatsapp/buffer.py`
- Create: `api/tests/test_whatsapp_buffer.py`

**Step 1: Write failing tests**

```python
# api/tests/test_whatsapp_buffer.py
from datetime import datetime, timedelta, timezone
from app.services.whatsapp.buffer import (
    add_to_buffer, drain_for_sender, count_pending, expire_old,
)
from app.models.whatsapp_buffer import WhatsAppPendingMedia


def test_add_to_buffer_inserts_row(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="https://gupshup/abc", content_hash="h1")
    db.commit()
    rows = db.query(WhatsAppPendingMedia).all()
    assert len(rows) == 1
    assert rows[0].media_type == "image"
    assert rows[0].drained_at is None


def test_drain_for_sender_marks_drained_and_returns_rows(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="u1", content_hash="h1")
    add_to_buffer(db, sender_phone="+91", media_type="document",
                  gupshup_url="u2", content_hash="h2")
    add_to_buffer(db, sender_phone="+92", media_type="image",  # other sender
                  gupshup_url="u3", content_hash="h3")
    db.commit()

    drained = drain_for_sender(db, "+91", story_id=None)
    db.commit()

    assert len(drained) == 2
    assert all(r.drained_at is not None for r in drained)
    # Other sender unaffected
    other = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+92").first()
    assert other.drained_at is None


def test_count_pending_excludes_drained(db):
    add_to_buffer(db, sender_phone="+91", media_type="image", gupshup_url="u", content_hash="h")
    db.commit()
    assert count_pending(db, "+91") == 1
    drain_for_sender(db, "+91", story_id=None); db.commit()
    assert count_pending(db, "+91") == 0


def test_expire_old_finalizes_orphans(db):
    """Media older than the idle window with no companion text is force-drained."""
    old = WhatsAppPendingMedia(
        sender_phone="+91", media_type="image", gupshup_media_url="u", content_hash="h",
        received_at=datetime.now(timezone.utc) - timedelta(seconds=120),
    )
    db.add(old); db.commit()
    expired = expire_old(db, idle_seconds=60)
    db.commit()
    assert len(expired) == 1
    assert expired[0].sender_phone == "+91"
```

**Step 2: Run; expect failure**

**Step 3: Implement**

```python
# api/app/services/whatsapp/buffer.py
"""Universal media buffer.

Photos/PDFs/audio/video that arrive before their text companion are
stashed here so a multi-message forward thread doesn't split into N
separate stories. Drained on Submit, or auto-finalized after a 60s
idle window if no text ever arrives.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppPendingMedia


def add_to_buffer(
    db: Session,
    *,
    sender_phone: str,
    media_type: str,
    gupshup_url: str,
    content_hash: Optional[str] = None,
    caption: Optional[str] = None,
    storage_url: Optional[str] = None,
) -> WhatsAppPendingMedia:
    row = WhatsAppPendingMedia(
        sender_phone=sender_phone,
        media_type=media_type,
        gupshup_media_url=gupshup_url,
        storage_url=storage_url,
        content_hash=content_hash,
        caption=caption,
    )
    db.add(row)
    return row


def count_pending(db: Session, sender_phone: str) -> int:
    return db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.sender_phone == sender_phone,
        WhatsAppPendingMedia.drained_at.is_(None),
    ).count()


def drain_for_sender(
    db: Session,
    sender_phone: str,
    *,
    story_id: Optional[UUID],
) -> List[WhatsAppPendingMedia]:
    """Mark all pending media for `sender_phone` as drained into `story_id`
    (which can be None when we're discarding via Cancel). Returns the rows
    that were drained, in receipt order.
    """
    rows = db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.sender_phone == sender_phone,
        WhatsAppPendingMedia.drained_at.is_(None),
    ).order_by(WhatsAppPendingMedia.received_at).all()
    now = datetime.now(timezone.utc)
    for r in rows:
        r.drained_at = now
        r.drained_into_story_id = story_id
    return rows


def expire_old(db: Session, idle_seconds: int = 60) -> List[WhatsAppPendingMedia]:
    """Find pending media older than `idle_seconds` and return them.
    Caller is responsible for finalizing as media-only stories.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
    return db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.drained_at.is_(None),
        WhatsAppPendingMedia.received_at < cutoff,
    ).all()
```

**Step 4: Run tests; commit**

```bash
cd api && pytest tests/test_whatsapp_buffer.py -v
git add api/app/services/whatsapp/buffer.py api/tests/test_whatsapp_buffer.py
git commit -m "feat(api): pending-media buffer (insert/drain/expire)"
```

---

### Task 9: Thread state service

**Files:**
- Create: `api/app/services/whatsapp/thread_state.py`
- Create: `api/tests/test_whatsapp_thread_state.py`

**Step 1: Tests cover open/append/close/idle-expiry**

```python
# api/tests/test_whatsapp_thread_state.py
from datetime import datetime, timedelta, timezone
from app.services.whatsapp.thread_state import (
    open_or_get, increment_text, increment_media, close, is_idle,
)
from app.models.whatsapp_buffer import WhatsAppThreadState


def test_open_or_get_creates_new(db):
    ts = open_or_get(db, "+91"); db.commit()
    assert ts.thread_kind == "new"
    assert ts.pending_text_count == 0


def test_open_or_get_reuses_existing(db):
    ts1 = open_or_get(db, "+91"); db.commit()
    ts2 = open_or_get(db, "+91"); db.commit()
    assert ts1.thread_started_at == ts2.thread_started_at


def test_increment_counts(db):
    open_or_get(db, "+91")
    increment_text(db, "+91", "hello world")
    increment_media(db, "+91")
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    assert ts.pending_text_count == 1
    assert ts.pending_media_count == 1
    assert "hello world" in ts.pending_text_concat


def test_close_deletes_row(db):
    open_or_get(db, "+91"); db.commit()
    close(db, "+91"); db.commit()
    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first() is None


def test_is_idle_for_old_thread(db):
    open_or_get(db, "+91")
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    ts.last_message_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db.commit()
    assert is_idle(db, "+91", idle_seconds=60) is True


def test_is_idle_for_active_thread(db):
    open_or_get(db, "+91"); db.commit()
    assert is_idle(db, "+91", idle_seconds=60) is False
```

**Step 2: Run, fail**

**Step 3: Implement**

```python
# api/app/services/whatsapp/thread_state.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppThreadState


def open_or_get(
    db: Session,
    sender_phone: str,
    *,
    thread_kind: str = "new",
    target_story_id: Optional[UUID] = None,
) -> WhatsAppThreadState:
    """Return existing state or create a fresh one. Caller commits."""
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
    if ts is None:
        ts = WhatsAppThreadState(
            sender_phone=sender_phone,
            thread_kind=thread_kind,
            target_story_id=target_story_id,
        )
        db.add(ts)
    return ts


def increment_text(db: Session, sender_phone: str, text: str) -> None:
    ts = open_or_get(db, sender_phone)
    ts.pending_text_count += 1
    ts.pending_text_concat = (ts.pending_text_concat + "\n\n" + text).strip()
    ts.last_message_at = datetime.now(timezone.utc)


def increment_media(db: Session, sender_phone: str) -> None:
    ts = open_or_get(db, sender_phone)
    ts.pending_media_count += 1
    ts.last_message_at = datetime.now(timezone.utc)


def close(db: Session, sender_phone: str) -> None:
    db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).delete()


def is_idle(db: Session, sender_phone: str, idle_seconds: int = 60) -> bool:
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
    if ts is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
    return ts.last_message_at < cutoff
```

**Step 4: Run tests; commit**

```bash
cd api && pytest tests/test_whatsapp_thread_state.py -v
git add api/app/services/whatsapp/thread_state.py api/tests/test_whatsapp_thread_state.py
git commit -m "feat(api): WhatsApp thread state service (open/increment/close/idle)"
```

---

## Phase 4 — Outbound Gupshup wrapper

### Task 10: Outbound message API (text, interactive buttons, edit-in-place)

**Files:**
- Create: `api/app/services/whatsapp/outbound.py`
- Create: `api/tests/test_whatsapp_outbound.py`

**Step 1: Tests use httpx-mock or unittest.mock to capture the HTTP call**

```python
# api/tests/test_whatsapp_outbound.py
from unittest.mock import patch, MagicMock
import httpx
from app.services.whatsapp import outbound


@patch("app.services.whatsapp.outbound.httpx.AsyncClient")
def test_send_text(mock_client):
    instance = MagicMock()
    instance.__aenter__.return_value = instance
    instance.post.return_value = MagicMock(status_code=200, json=lambda: {"messageId": "wamid.X"})
    mock_client.return_value = instance

    import asyncio
    msg_id = asyncio.run(outbound.send_text(to="+91", body="hello"))
    assert msg_id == "wamid.X"
    args, kwargs = instance.post.call_args
    assert "https://api.gupshup.io" in args[0]
    assert "hello" in str(kwargs.get("data", {}))


@patch("app.services.whatsapp.outbound.httpx.AsyncClient")
def test_send_interactive_buttons(mock_client):
    instance = MagicMock()
    instance.__aenter__.return_value = instance
    instance.post.return_value = MagicMock(status_code=200, json=lambda: {"messageId": "wamid.Y"})
    mock_client.return_value = instance

    import asyncio
    msg_id = asyncio.run(outbound.send_interactive_buttons(
        to="+91", body="Got 1.", buttons=[("submit_thread", "Submit"), ("cancel_thread", "Cancel")],
    ))
    assert msg_id == "wamid.Y"


@patch("app.services.whatsapp.outbound.httpx.AsyncClient")
def test_edit_interactive_falls_back_to_new_message_on_error(mock_client):
    """If edit fails (e.g. 5min window expired), we send a fresh interactive."""
    instance = MagicMock()
    instance.__aenter__.return_value = instance
    # First call (edit) returns 400; second call (new send) returns 200
    instance.post.side_effect = [
        MagicMock(status_code=400, json=lambda: {"error": "edit window expired"}),
        MagicMock(status_code=200, json=lambda: {"messageId": "wamid.NEW"}),
    ]
    mock_client.return_value = instance

    import asyncio
    msg_id = asyncio.run(outbound.edit_or_send_interactive(
        to="+91", existing_msg_id="wamid.OLD", body="updated",
        buttons=[("submit", "S"), ("cancel", "C")],
    ))
    assert msg_id == "wamid.NEW"
```

**Step 2: Run; fail**

**Step 3: Implement**

```python
# api/app/services/whatsapp/outbound.py
"""Gupshup outbound message API wrapper.

We use the v1 partner API with auth via GUPSHUP_APIKEY (already configured
in the environment for inbound webhook signature verification).

Three primitives:
- send_text(): plain text reply
- send_interactive_buttons(): text body + up to 3 reply buttons
- send_interactive_list(): text body + a List CTA opening rows (used for menu)
- edit_or_send_interactive(): tries to edit an existing interactive message;
  falls back to a fresh send if Gupshup rejects the edit (edit window is
  ~5min for interactives). Caller stores the returned msg_id back into
  thread_state.interactive_msg_id either way.
"""
from __future__ import annotations
import json
import logging
from typing import Optional, Sequence

import httpx

from app.config import settings


log = logging.getLogger("whatsapp.outbound")

_BASE = "https://api.gupshup.io/wa/api/v1"


def _headers() -> dict:
    return {
        "apikey": settings.GUPSHUP_APIKEY,
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def send_text(*, to: str, body: str) -> Optional[str]:
    payload = {
        "channel": "whatsapp",
        "source": settings.GUPSHUP_SOURCE_NUMBER,
        "destination": to.lstrip("+"),
        "src.name": settings.GUPSHUP_APP_NAME,
        "message": json.dumps({"type": "text", "text": body}),
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{_BASE}/msg", data=payload, headers=_headers())
    if r.status_code != 200:
        log.warning("send_text failed: %s %s", r.status_code, r.text[:200])
        return None
    return r.json().get("messageId")


async def send_interactive_buttons(
    *, to: str, body: str, buttons: Sequence[tuple[str, str]],
    header: Optional[str] = None,
) -> Optional[str]:
    """`buttons` is a sequence of (button_id, label). Up to 3."""
    msg = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                for bid, label in buttons[:3]
            ]},
        },
    }
    if header:
        msg["interactive"]["header"] = {"type": "text", "text": header}
    payload = {
        "channel": "whatsapp",
        "source": settings.GUPSHUP_SOURCE_NUMBER,
        "destination": to.lstrip("+"),
        "src.name": settings.GUPSHUP_APP_NAME,
        "message": json.dumps(msg),
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{_BASE}/msg", data=payload, headers=_headers())
    if r.status_code != 200:
        log.warning("send_interactive_buttons failed: %s %s", r.status_code, r.text[:200])
        return None
    return r.json().get("messageId")


async def send_interactive_list(
    *, to: str, body: str, button_label: str,
    sections: Sequence[tuple[str, Sequence[tuple[str, str, Optional[str]]]]],
    header: Optional[str] = None,
) -> Optional[str]:
    """`sections` = [(section_title, [(row_id, row_title, row_description), ...]), ...]"""
    msg_sections = []
    for title, rows in sections:
        msg_sections.append({
            "title": title[:24],
            "rows": [
                {"id": rid, "title": rtitle[:24], **({"description": rdesc[:72]} if rdesc else {})}
                for rid, rtitle, rdesc in rows[:10]
            ],
        })
    msg = {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {"button": button_label[:20], "sections": msg_sections[:10]},
        },
    }
    if header:
        msg["interactive"]["header"] = {"type": "text", "text": header}
    payload = {
        "channel": "whatsapp",
        "source": settings.GUPSHUP_SOURCE_NUMBER,
        "destination": to.lstrip("+"),
        "src.name": settings.GUPSHUP_APP_NAME,
        "message": json.dumps(msg),
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{_BASE}/msg", data=payload, headers=_headers())
    if r.status_code != 200:
        log.warning("send_interactive_list failed: %s %s", r.status_code, r.text[:200])
        return None
    return r.json().get("messageId")


async def edit_or_send_interactive(
    *, to: str, existing_msg_id: Optional[str],
    body: str, buttons: Sequence[tuple[str, str]],
) -> Optional[str]:
    """Try to edit `existing_msg_id` in place; on failure, send a fresh
    interactive message and return its new id. Caller persists the returned
    id back to thread_state.interactive_msg_id.
    """
    if existing_msg_id:
        try:
            edit_payload = {
                "channel": "whatsapp",
                "source": settings.GUPSHUP_SOURCE_NUMBER,
                "destination": to.lstrip("+"),
                "src.name": settings.GUPSHUP_APP_NAME,
                "messageId": existing_msg_id,
                "message": json.dumps({
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": body},
                        "action": {"buttons": [
                            {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                            for bid, label in buttons[:3]
                        ]},
                    },
                }),
            }
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/msg/edit", data=edit_payload, headers=_headers())
            if r.status_code == 200:
                return existing_msg_id  # edit succeeded, id unchanged
            log.info("edit failed (%s), sending fresh interactive", r.status_code)
        except Exception as e:
            log.info("edit raised (%r), sending fresh interactive", e)
    return await send_interactive_buttons(to=to, body=body, buttons=buttons)
```

**Step 4: Run tests; commit**

```bash
cd api && pytest tests/test_whatsapp_outbound.py -v
git add api/app/services/whatsapp/outbound.py api/tests/test_whatsapp_outbound.py
git commit -m "feat(api): Gupshup outbound — text + interactive buttons + edit-in-place"
```

---

## Phase 5 — New webhook dispatcher

### Task 11: Replace existing webhook with dispatcher (no behavior change yet)

**Files:**
- Modify: `api/app/routers/webhooks_whatsapp.py:276-533` — replace handler body with dispatch
- Move existing logic into `api/app/services/whatsapp/legacy_ingest.py` temporarily (we'll replace step-by-step in subsequent tasks)
- Create: `api/tests/test_whatsapp_dispatcher.py`

**Step 1: Tests assert that each MessageKind dispatches to the right handler**

```python
# api/tests/test_whatsapp_dispatcher.py
from unittest.mock import patch, AsyncMock
from app.services.whatsapp.classifier import MessageKind


@patch("app.services.whatsapp.dispatcher.handle_button", new=AsyncMock())
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new=AsyncMock())
@patch("app.services.whatsapp.dispatcher.handle_forward", new=AsyncMock())
@patch("app.services.whatsapp.dispatcher.handle_skip", new=AsyncMock())
def test_dispatch_routes_button(_skip, _fwd, _qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    import asyncio
    payload = {"type": "interactive", "interactive": {"type": "button_reply",
        "button_reply": {"id": "submit_thread"}}}
    asyncio.run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert btn.called
```

(Repeat shape for each MessageKind — tests are mostly identical, just the patched name + payload differ.)

**Step 2: Implement dispatcher**

```python
# api/app/services/whatsapp/dispatcher.py
"""Single entry point. Classifies inbound, delegates to a handler.
Each handler is responsible for its own outbound replies, buffer
writes, and dedup checks.
"""
from sqlalchemy.orm import Session
from app.models.user import User
from app.services.whatsapp.classifier import classify, MessageKind


async def dispatch(*, db: Session, sender_phone: str, user: User | None, payload: dict) -> None:
    kind = classify(payload)
    if kind == MessageKind.BUTTON:
        await handle_button(db=db, sender_phone=sender_phone, user=user, payload=payload)
    elif kind == MessageKind.QUOTED_REPLY:
        await handle_quoted_reply(db=db, sender_phone=sender_phone, user=user, payload=payload)
    elif kind == MessageKind.FORWARD:
        await handle_forward(db=db, sender_phone=sender_phone, user=user, payload=payload)
    else:
        await handle_skip(db=db, sender_phone=sender_phone, user=user, kind=kind)


# Stubs (implemented in subsequent tasks)
async def handle_button(*, db, sender_phone, user, payload): raise NotImplementedError
async def handle_quoted_reply(*, db, sender_phone, user, payload): raise NotImplementedError
async def handle_forward(*, db, sender_phone, user, payload): raise NotImplementedError
async def handle_skip(*, db, sender_phone, user, kind): raise NotImplementedError
```

**Step 3: Wire into the existing router behind a feature flag**

In `api/app/routers/webhooks_whatsapp.py`, near the top of `gupshup_inbound`:

```python
from app.config import settings
from app.services.whatsapp.dispatcher import dispatch as new_dispatch

# … existing dedup + payload extraction …

if settings.WHATSAPP_SELF_SERVICE_ENABLED:
    user = _resolve_user_for_phone(db, sender_phone)  # may be None for unregistered
    await new_dispatch(db=db, sender_phone=sender_phone, user=user, payload=inner)
    return JSONResponse({"status": "ok"})

# … rest of existing handler unchanged …
```

Add `WHATSAPP_SELF_SERVICE_ENABLED: bool = False` to `api/app/config.py`.

**Step 4: Run dispatcher tests; commit**

```bash
cd api && pytest tests/test_whatsapp_dispatcher.py -v
git add api/app/services/whatsapp/dispatcher.py api/app/routers/webhooks_whatsapp.py api/app/config.py api/tests/test_whatsapp_dispatcher.py
git commit -m "feat(api): WhatsApp dispatcher skeleton behind WHATSAPP_SELF_SERVICE_ENABLED flag"
```

---

### Task 12: handle_skip — sticker / location / contact / unknown

**Files:**
- Modify: `api/app/services/whatsapp/dispatcher.py` — fill in `handle_skip`
- Create: `api/tests/test_whatsapp_handle_skip.py`

**Step 1: Test**

```python
from unittest.mock import patch, AsyncMock
from app.services.whatsapp.classifier import MessageKind


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_sticker_sends_polite_decline(mock_send):
    from app.services.whatsapp.dispatcher import handle_skip
    import asyncio
    asyncio.run(handle_skip(db=None, sender_phone="+91", user=None, kind=MessageKind.SKIP_STICKER))
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "Sticker" in body or "Forward text" in body  # English fallback
```

**Step 2-5: Implement, run, commit**

In dispatcher.py:
```python
from app.services.whatsapp import outbound, i18n

async def handle_skip(*, db, sender_phone, user, kind):
    if kind == MessageKind.SKIP_OTHER:
        return  # silent — unknown types shouldn't talk back
    lang = i18n.resolve_lang(user)
    await outbound.send_text(to=sender_phone, body=i18n.t("err.sticker", lang))
```

Test, commit.

---

### Task 13: handle_forward — the meat

**Files:**
- Modify: `api/app/services/whatsapp/dispatcher.py` — fill in `handle_forward`
- Create: `api/app/services/whatsapp/ingest.py` — extracted helpers
- Create: `api/tests/test_whatsapp_ingest.py`

This is the largest task. Test cases:
- 20-word minimum rejection
- Unregistered sender rejection
- Photo before text → buffered, no story yet
- Text after photo → drained, thread state updated
- Duplicate text → dedup skip
- Buttons message edited in place on subsequent forwards
- Audio buffered, one-time hint shown on submit only

**Step 1: Tests** (one test per scenario)

```python
# api/tests/test_whatsapp_ingest.py
import pytest
from unittest.mock import patch, AsyncMock
import asyncio


@patch("app.services.whatsapp.dispatcher.outbound", autospec=True)
def test_unregistered_sender_gets_rejection(mock_out, db):
    from app.services.whatsapp.dispatcher import handle_forward
    payload = {"type": "text", "text": {"body": "Some news content goes here right now."}}
    mock_out.send_text = AsyncMock()

    asyncio.run(handle_forward(db=db, sender_phone="+91999", user=None, payload=payload))
    db.commit()

    mock_out.send_text.assert_called_once()
    assert "isn't registered" in mock_out.send_text.call_args.kwargs["body"]


@patch("app.services.whatsapp.dispatcher.outbound", autospec=True)
def test_under_20_words_rejected(mock_out, db, _make_reporter):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _make_reporter(db, "+919")
    payload = {"type": "text", "text": {"body": "too short"}}
    mock_out.send_text = AsyncMock()
    asyncio.run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    assert "20+" in mock_out.send_text.call_args.kwargs["body"]


@patch("app.services.whatsapp.dispatcher.outbound", autospec=True)
def test_photo_first_buffers_without_creating_story(mock_out, db, _make_reporter):
    from app.services.whatsapp.dispatcher import handle_forward
    from app.models.whatsapp_buffer import WhatsAppPendingMedia
    user = _make_reporter(db, "+919")
    payload = {"type": "image", "image": {"id": "media123", "url": "https://gupshup/x"}}
    mock_out.edit_or_send_interactive = AsyncMock(return_value="wamid.X")
    asyncio.run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()
    pending = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").all()
    assert len(pending) == 1
    # No story created
    from app.models.story import Story
    assert db.query(Story).count() == 0


# … additional tests for each scenario …
```

**Step 2-5: Implement, run, commit**

Implementation maps each test to behavior:

```python
# Inside dispatcher.py

async def handle_forward(*, db, sender_phone, user, payload):
    lang = i18n.resolve_lang(user)
    if user is None:
        await outbound.send_text(to=sender_phone, body=i18n.t("err.unregistered", lang))
        return

    inner_type = payload.get("type")

    if inner_type == "text":
        text = payload.get("text", {}).get("body", "").strip()
        # Strip "Forwarded from:" boilerplate
        text = ingest.strip_forward_boilerplate(text)
        if ingest.word_count(text) < 20:
            await outbound.send_text(to=sender_phone, body=i18n.t("err.tooShort", lang))
            return
        h = dedup.hash_text(text)
        if dedup.is_duplicate(db, sender_phone, h):
            return  # silent skip
        dedup.mark_seen(db, sender_phone, h)
        thread_state.increment_text(db, sender_phone, text)
    elif inner_type in ("image", "document", "audio", "video"):
        # … buffer media, dedup by content_hash …
        pass

    # Edit / send the [Submit][Cancel] interactive
    ts = thread_state.open_or_get(db, sender_phone)
    body = render_thread_progress(ts, lang)
    new_msg_id = await outbound.edit_or_send_interactive(
        to=sender_phone, existing_msg_id=ts.interactive_msg_id,
        body=body,
        buttons=[("submit_thread", i18n.t("btn.submit", lang)),
                 ("cancel_thread", i18n.t("btn.cancel", lang))],
    )
    ts.interactive_msg_id = new_msg_id
    db.commit()
```

(Full implementation handles every case; structure shown above. Test list grows to ~15 cases. Each test is one Step in the TDD sequence; total task is ~30 minutes once the helpers from Phase 3 are in place.)

**Commit**

```bash
git add api/app/services/whatsapp/ingest.py api/app/services/whatsapp/dispatcher.py api/tests/test_whatsapp_ingest.py
git commit -m "feat(api): handle_forward — buffer media, dedup, 20-word check, edit-in-place buttons"
```

---

### Task 14: handle_button — Submit, Cancel, Add more, Today, Menu

**Files:**
- Modify: `api/app/services/whatsapp/dispatcher.py` — fill in `handle_button`
- Create: `api/app/services/whatsapp/finalize.py` — drain + create story
- Create: `api/tests/test_whatsapp_finalize.py`

**Step 1: Tests for each button id**

- `submit_thread` → drains buffer, calls existing story-creation path, sends saved-confirmation with action buttons, stores `whatsapp_confirm_message_id`
- `cancel_thread` → drops thread state + pending media, sends "Cancelled"
- `add_to_<story_id>` → opens an `add` thread targeting that story
- `today_list` → renders today's list (Task 15)
- `open_menu` → renders menu list

**Step 2-5:** Implement each, test, commit incrementally — one button id per commit ideally.

```bash
git commit -m "feat(api): submit_thread button — drain buffer, create story, send confirmation"
git commit -m "feat(api): cancel_thread button — drop pending, ack"
git commit -m "feat(api): add_to_X button — open add-to thread"
git commit -m "feat(api): open_menu button — list message"
```

---

### Task 15: handle today's stories — list, plain text, overflow

**Files:**
- Create: `api/app/services/whatsapp/today.py`
- Create: `api/tests/test_whatsapp_today.py`

**Step 1: Test cases**

- 0 stories → empty-state message
- 5 stories → plain list, no overflow
- 30 stories → first 25 + "(+5 more)" + CTA URL button

**Step 2-5: Implement, test, commit**

```python
# api/app/services/whatsapp/today.py
from datetime import date
from sqlalchemy.orm import Session
from app.models.story import Story


def list_today_for_reporter(db: Session, reporter_id) -> list[Story]:
    today = date.today()
    return db.query(Story).filter(
        Story.reporter_id == reporter_id,
        Story.deleted_at.is_(None),
        # use submitted_at::date = today via a func cast
    ).order_by(Story.created_at.desc()).all()


def render_today_message(stories: list[Story], lang: str) -> str:
    """Plain text body for the today's-stories reply."""
    n = len(stories)
    if n == 0:
        return i18n.t("today.empty", lang)
    header = i18n.t("today.header", lang, count=n)
    visible = stories[:25]
    lines = [f"• {s.display_id or s.id} — {(s.headline or '')[:50]}" for s in visible]
    body = header + "\n\n" + "\n".join(lines)
    if n > 25:
        body += "\n\n" + i18n.t("today.overflow", lang, n=n-25)
    return body
```

```bash
git add api/app/services/whatsapp/today.py api/tests/test_whatsapp_today.py
git commit -m "feat(api): today's-stories handler with overflow + plain-text rendering"
```

---

### Task 16: handle_quoted_reply — add to existing story

**Files:**
- Create: `api/app/services/whatsapp/add_to_story.py`
- Create: `api/tests/test_whatsapp_add_to_story.py`

**Step 1: Tests**

- Reply-quote of saved-confirmation → opens add thread to that story
- Reply-quote of any other message → falls through to forward handler
- Cross-reporter (story belongs to another reporter) → reject
- Locked story (status=approved/published) → reject + treat as fresh

**Step 2-5: Implement, test, commit**

---

## Phase 6 — Universal Links (mobile + panel)

### Task 17: Panel fallback page at /r/:id and /r/today

**Files:**
- Create: `reviewer-panel/src/pages/AppRedirectPage.jsx`
- Modify: `reviewer-panel/src/App.jsx` — add `<Route path="/r/:id" element={<AppRedirectPage />} />` and `/r/today`
- Create: `reviewer-panel/public/.well-known/apple-app-site-association` (no extension, application/json)
- Create: `reviewer-panel/public/.well-known/assetlinks.json`
- Modify: `reviewer-panel/firebase.json` — add headers / rewrites for `.well-known/*` files

**Step 1: AppRedirectPage shows install badges only**

```jsx
// reviewer-panel/src/pages/AppRedirectPage.jsx
import { useEffect } from 'react';

const APP_STORE_URL = "https://apps.apple.com/in/app/vrittant/id<TBD>";
const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.attentionstack.vrittant";

export default function AppRedirectPage() {
  useEffect(() => {
    // On iOS/Android the Universal Link should already have intercepted
    // and opened the app; if we got here, the app isn't installed.
    // (No JS-side redirect — let the user pick their store.)
  }, []);
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 p-6 bg-background text-foreground">
      <h1 className="text-2xl font-semibold">Open in Vrittant</h1>
      <p className="text-muted-foreground text-center max-w-sm">
        Install Vrittant to open this story.
      </p>
      <div className="flex flex-col gap-3 w-full max-w-xs">
        <a href={APP_STORE_URL} className="rounded-md border border-border px-4 py-2 text-center">
          Download on App Store
        </a>
        <a href={PLAY_STORE_URL} className="rounded-md border border-border px-4 py-2 text-center">
          Get it on Google Play
        </a>
      </div>
    </div>
  );
}
```

**Step 2: AASA + assetlinks.json**

```json
// reviewer-panel/public/.well-known/apple-app-site-association
{
  "applinks": {
    "apps": [],
    "details": [
      {
        "appID": "STV4JYX8TT.com.attentionstack.vrittant",
        "paths": ["/r/*"]
      }
    ]
  }
}
```

```json
// reviewer-panel/public/.well-known/assetlinks.json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.attentionstack.vrittant",
    "sha256_cert_fingerprints": ["<FILL IN FROM upload-keystore.jks>"]
  }
}]
```

The Android SHA256 fingerprint comes from:
```bash
keytool -list -v -keystore mobile/android/upload-keystore.jks -alias upload | grep SHA256
```

**Step 3: Firebase config to serve AASA correctly**

Modify `reviewer-panel/firebase.json`:

```json
{
  "hosting": {
    "public": "dist",
    "headers": [
      {
        "source": "/.well-known/apple-app-site-association",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }
    ],
    "rewrites": [
      {"source": "/r/**", "destination": "/index.html"},
      {"source": "**", "destination": "/index.html"}
    ]
  }
}
```

**Step 4: Build + deploy + verify**

```bash
cd reviewer-panel && npx vite build
firebase deploy --only hosting:uat
# Verify
curl -i https://vrittant-uat.web.app/.well-known/apple-app-site-association
# Expected: 200, Content-Type: application/json, body matches the file
```

**Step 5: Commit**

```bash
git add reviewer-panel/src/pages/AppRedirectPage.jsx reviewer-panel/src/App.jsx reviewer-panel/public/.well-known reviewer-panel/firebase.json
git commit -m "feat(panel): /r/* fallback page + AASA + assetlinks for Universal Links"
```

---

### Task 18: iOS Associated Domains entitlement

**Files:**
- Modify: `mobile/ios/Runner/Runner.entitlements` (create if absent)
- Modify: `mobile/ios/Runner.xcodeproj/project.pbxproj` (add entitlements file reference)

**Step 1: Entitlements file**

```xml
<!-- mobile/ios/Runner/Runner.entitlements -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.developer.associated-domains</key>
  <array>
    <string>applinks:vrittant.in</string>
  </array>
</dict>
</plist>
```

**Step 2: Xcode pbxproj**

Add `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;` to the Runner target's build settings (3 occurrences across configurations).

**Step 3: Build IPA, verify**

```bash
cd mobile && flutter build ipa --release --build-number=7 --export-options-plist=ios/ExportOptions.plist
# Install on a real iPhone, tap a vrittant.in/r/<id> link in any iMessage,
# expect the app to open directly (or fallback page if entitlement not yet propagated)
```

**Step 4: Commit**

```bash
git add mobile/ios/Runner/Runner.entitlements mobile/ios/Runner.xcodeproj/project.pbxproj
git commit -m "build(ios): Associated Domains entitlement for vrittant.in Universal Links"
```

---

### Task 19: Android intent-filter for App Links

**Files:**
- Modify: `mobile/android/app/src/main/AndroidManifest.xml`

**Step 1: Add intent filter**

Inside the `<activity android:name=".MainActivity">` block, add:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data
        android:scheme="https"
        android:host="vrittant.in"
        android:pathPrefix="/r/" />
</intent-filter>
```

**Step 2: Verify**

```bash
cd mobile && flutter build apk --release
adb install build/app/outputs/flutter-apk/app-release.apk
adb shell am start -a android.intent.action.VIEW -d "https://vrittant.in/r/abc-123"
# Expect Vrittant to open
```

**Step 3: Commit**

```bash
git add mobile/android/app/src/main/AndroidManifest.xml
git commit -m "build(android): App Link intent-filter for vrittant.in/r/*"
```

---

### Task 20: Flutter route handler

**Files:**
- Add `app_links: ^6.x` to `mobile/pubspec.yaml`
- Modify: `mobile/lib/main.dart` (or wherever the root MaterialApp lives) — listen for incoming links

**Step 1: Add dependency, run pub get**

**Step 2: Wire app_links listener**

```dart
// mobile/lib/main.dart (excerpt)
import 'package:app_links/app_links.dart';

class _MyAppState extends State<MyApp> {
  final _appLinks = AppLinks();
  StreamSubscription<Uri>? _sub;

  @override
  void initState() {
    super.initState();
    _initDeepLinks();
  }

  Future<void> _initDeepLinks() async {
    final initialUri = await _appLinks.getInitialAppLink();
    if (initialUri != null) _handleUri(initialUri);
    _sub = _appLinks.uriLinkStream.listen(_handleUri);
  }

  void _handleUri(Uri uri) {
    if (uri.host != 'vrittant.in') return;
    final segments = uri.pathSegments;
    if (segments.length >= 2 && segments[0] == 'r') {
      final tail = segments[1];
      if (tail == 'today') {
        navigatorKey.currentState?.pushNamed('/today');
      } else {
        navigatorKey.currentState?.pushNamed('/review/$tail');
      }
    }
  }

  @override
  void dispose() { _sub?.cancel(); super.dispose(); }
}
```

**Step 3: Test on simulator**

```bash
xcrun simctl openurl booted https://vrittant.in/r/abc-123
# Expect navigation to /review/abc-123 in the running app
```

**Step 4: Commit**

```bash
git add mobile/pubspec.yaml mobile/lib/main.dart
git commit -m "feat(mobile): handle vrittant.in/r/* Universal Links"
```

---

## Phase 7 — Org default_language seeding & migration

### Task 21: Seed Pragativadi + Sambad to 'or' (already default)

The migration sets `default_language = 'or'` for all existing rows. Verify:

```bash
PW=...; PGPASSWORD="$PW" psql -h localhost -p 5433 -U postgres -d vrittant \
  -c "SELECT id, name, default_language FROM organizations;"
# Expect every row shows 'or'
```

No code change needed for this task — covered by Task 1 migration.

---

## Phase 8 — UAT smoke + rollout

### Task 22: UAT smoke checklist

Manual checklist run on UAT after all backend code is deployed and `WHATSAPP_SELF_SERVICE_ENABLED=true`:

1. Forward a 50-word Odia text from a registered reporter phone — expect `[✓ Submit Story][✕ Cancel]` interactive in Odia within 2s.
2. Forward 2 photos in same session — expect the buttons message edits in place to "Got 3 messages (1 text + 2 photos)".
3. Tap Submit — expect "Story saved" confirmation with `[➕ Add more][📋 Today][📱 Open in app]`.
4. Tap `[📋 Today]` — expect plain-text list with 1+ stories.
5. Long-press the Saved confirmation → Reply → forward more — expect "Adding to PNS-..." flow.
6. Forward a sticker — expect single-line decline.
7. Forward a 5-word message — expect "20+ words" rejection.
8. Test from an unregistered phone — expect "not registered" reply.
9. Cause a transient DB error (kill Cloud SQL connection during a query) — expect transparent retry.
10. Forward 26 stories in a day, then `[📋 Today]` — expect first 25 + "(+1 more)" + CTA.
11. Tap `[📱 Open in app]` from the saved confirmation — expect app to open at `/review/<id>` (only on devices with the new IPA installed).

If any item fails, file a bug, fix, redeploy, re-run from #1.

---

### Task 23: Prod enablement

After UAT smoke passes:

1. Run the SQL migration on prod (Task 1, prod variant)
2. Push code to `main` (auto-deploys via existing pipeline)
3. Set `WHATSAPP_SELF_SERVICE_ENABLED=true` via Cloud Run env var:
   ```bash
   gcloud run services update vrittant-api \
     --region=asia-south1 --project=vrittant-f5ef2 \
     --update-env-vars=WHATSAPP_SELF_SERVICE_ENABLED=true
   ```
4. Watch Cloud Run logs for the first 30 min:
   ```bash
   gcloud logging tail 'resource.labels.service_name=vrittant-api AND "whatsapp"' \
     --project=vrittant-f5ef2
   ```

If errors > 1% of inbound forwards, set the flag to `false` to revert to legacy ingest. The dispatcher route is fully reversible.

---

## Notes for the executor

- Follow @superpowers:test-driven-development on every behavior change
- After each task, follow @superpowers:verification-before-completion before marking done
- Keep commits small (one task = 1-3 commits); push to develop after every passing test
- Phases 1-4 can ship independently and deliver value (reliability + dedup + buffer foundation)
- Phases 5-6 build the user-facing UX
- Phase 6 (Universal Links) requires a paired mobile-app release; backend can ship first
- The legacy ingest path stays in place as a fallback until prod has been on the new dispatcher for 1 week with no rollback
