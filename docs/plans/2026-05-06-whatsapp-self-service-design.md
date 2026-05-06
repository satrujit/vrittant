# WhatsApp Self-Service & Edge-Case Hardening — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this once the writing-plans skill produces the task-by-task plan. Until that plan exists, do not begin implementation.

**Date:** 2026-05-06
**Status:** Approved (sections 1-5 + two refinements)
**Goal:** Add reporter self-service via WhatsApp (today's stories, add-to-existing-story, deep-link-to-app) without proactive push notifications. Replace brittle "type done" keyword with interactive buttons. Fix 18 known edge cases in the current webhook handler. All replies internationalized (default Odia).

---

## 1. Scope

### In scope

**Refinements to existing functionality**
- Replace the "done" keyword with `[Submit Story]` / `[Cancel]` reply buttons
- Auto-acknowledge inbound forwards
- Universal media buffer (photos, PDFs, audio, video) so multi-message threads don't split into separate stories
- Connection-pool retry middleware (the 503 class of error from 2026-05-05)
- 18 edge-case fixes (see §3)
- All outbound replies translated to the reporter's org default language (Odia / Hindi / English)

**New self-service capabilities**
- "📋 Today's stories" — list of stories filed today by this reporter
- "➕ Add to existing story" — append text + photos to an already-submitted story (via reply-quote or button)
- "📱 Open in Vrittant app" — Universal Link that opens the mobile app

### Explicitly out of scope

- Status / rejection-reason / resubmit functionality
- Daily morning digest pushes
- Status-change notifications (when editor approves / publishes)
- Editor approve/reject from WhatsApp
- Voice-to-text transcription via WhatsApp (mobile app retains exclusive STT)
- Mixed-language LLM prompt tuning
- Document content extraction (PDFs are stored as attachments, not parsed for story body)
- Web access for reporters (panel remains editor-only)

---

## 2. Architecture

### End-to-end flow

#### A. Reporter forwards content (fresh thread)

```
Reporter forwards a text message
    ↓
POST /webhooks/whatsapp/gupshup
    ↓
Dispatcher classifies: forward / button-reply / quoted-reply / menu / skip
    ↓
ingest_handler:
  - dedup by message_id (existing whatsapp_inbound_dedup)
  - resolve sender → User (unknown → polite reject)
  - content_hash → dedup against whatsapp_content_dedup
  - 20-word minimum check
  - For media: write to whatsapp_pending_media
  - For text: drain pending_media for this sender into the thread
  - Update whatsapp_thread_state for sender
    ↓
Send / edit-in-place interactive [Submit Story][Cancel] message
    ↓
Reporter taps [Submit Story]
    ↓
Button webhook → button_handler → finalize_thread:
  - Drain all pending_media for this sender
  - Build paragraphs (text + media references)
  - Single LLM call → headline / category / body (existing path)
  - INSERT into stories
  - Cache the WhatsApp confirmation msg ID into stories.whatsapp_confirm_message_id
    ↓
Send "✓ Story saved" confirmation with [➕ Add more] [📋 Today] [📱 Open in app] buttons
```

#### B. Reporter adds to an existing story (reply-quote path)

```
Reporter long-presses our "✓ Story saved" message → Reply with new content
    ↓
Inbound webhook includes context.id = our outbound msg ID
    ↓
quoted_reply_handler:
  - Look up stories WHERE whatsapp_confirm_message_id = context.id
  - Reject if story.reporter_id != sender's user_id (cross-reporter)
  - Reject if story.status not in ('submitted', 'flagged') (locked)
  - Open an "add-to" thread: same as fresh thread, but bound to existing story_id
    ↓
Send [Save additions] [Discard] interactive
    ↓
On Save: append paragraphs to existing story, ack
```

#### C. Reporter taps "📋 Today" or asks "show stories"

```
Free-text inbound that doesn't match a forward (no media, < 20 words)
    ↓
menu_handler: send "What would you like to do?" + [Open menu] button
    ↓
Reporter taps [Open menu] OR taps [📋 Today] from a saved-confirmation
    ↓
List Message sent / OR direct response to [📋 Today]:
  - SELECT FROM stories WHERE reporter_id = X AND submitted_at::date = today
  - Format as plain-text list (up to 25 items + "(+N more)" overflow)
  - Send with [📱 Open all in Vrittant app] CTA URL button → vrittant.in/r/today
```

### Data model changes

```sql
-- Universal media buffer (photos, PDFs, audio, video)
CREATE TABLE whatsapp_pending_media (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_phone             VARCHAR NOT NULL,
    media_type               VARCHAR NOT NULL,    -- 'image' | 'document' | 'audio' | 'video'
    gupshup_media_url        TEXT NOT NULL,
    storage_url              TEXT,                 -- our GCS URL after copy
    content_hash             VARCHAR,              -- SHA256 of bytes
    caption                  TEXT,
    received_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drained_at               TIMESTAMPTZ,
    drained_into_story_id    UUID REFERENCES stories(id) ON DELETE SET NULL
);
CREATE INDEX ix_pending_media_sender_received
    ON whatsapp_pending_media (sender_phone, received_at);
CREATE INDEX ix_pending_media_undrained
    ON whatsapp_pending_media (sender_phone)
    WHERE drained_at IS NULL;

-- Confirmation msg tracking (for reply-quote → add-to-story lookup)
ALTER TABLE stories
    ADD COLUMN whatsapp_confirm_message_id VARCHAR;
CREATE INDEX ix_stories_whatsapp_confirm
    ON stories (whatsapp_confirm_message_id)
    WHERE whatsapp_confirm_message_id IS NOT NULL;

-- Active thread state per sender (for in-place button-message editing)
CREATE TABLE whatsapp_thread_state (
    sender_phone           VARCHAR PRIMARY KEY,
    thread_kind            VARCHAR NOT NULL DEFAULT 'new',  -- 'new' | 'add'
    target_story_id        UUID REFERENCES stories(id) ON DELETE SET NULL,
    thread_started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pending_text_count     INT NOT NULL DEFAULT 0,
    pending_media_count    INT NOT NULL DEFAULT 0,
    pending_text_concat    TEXT NOT NULL DEFAULT '',
    interactive_msg_id     VARCHAR,
    audio_warning_shown    BOOLEAN NOT NULL DEFAULT FALSE
);

-- Content-level dedup (within a session window)
CREATE TABLE whatsapp_content_dedup (
    sender_phone   VARCHAR NOT NULL,
    content_hash   VARCHAR NOT NULL,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sender_phone, content_hash)
);
CREATE INDEX ix_content_dedup_received ON whatsapp_content_dedup (received_at);
-- Cron job (or on-write cleanup): DELETE WHERE received_at < NOW() - INTERVAL '24 hours';

-- Org default language (drives WhatsApp reply locale)
ALTER TABLE organizations
    ADD COLUMN default_language VARCHAR(2) NOT NULL DEFAULT 'or';
COMMENT ON COLUMN organizations.default_language IS
    'ISO 639-1 code: or=Odia (default), hi=Hindi, en=English. Drives WhatsApp reply locale and may drive other org-wide UX defaults later.';
```

### Handler decomposition

`api/app/routers/webhooks_whatsapp.py` becomes a thin dispatcher. New service module
`api/app/services/whatsapp/` with submodules:

```
whatsapp/
  __init__.py
  i18n.py            # STRINGS dict, t(key, lang, **vars) helper
  classifier.py      # decide: forward | button | quoted | menu | skip
  ingest.py          # buffer media, accumulate text, manage thread_state
  finalize.py        # drain buffer → create story → send confirmation
  add_to_story.py    # quoted-reply / [Add more] flow
  today.py           # list-today handler
  menu.py            # menu-fallback for unrecognized free-text
  outbound.py        # Gupshup send-message wrapper, edit-in-place support
  dedup.py           # content_hash compute + dedup-table check
  permissions.py     # cross-reporter / locked-story checks
  reliability.py     # connection-pool retry middleware
```

### Connection-pool retry middleware

FastAPI middleware that wraps the WhatsApp webhook routes (and any other write-heavy routes worth protecting):

```python
async def retry_on_transient_db_errors(request, call_next):
    try:
        return await call_next(request)
    except (OperationalError, DBAPIError, psycopg2.DatabaseError) as e:
        if not _is_transient(e):
            raise
        log.warning("Transient DB error, invalidating + retrying once: %s", e)
        # Invalidate the request-scoped session via the engine
        engine.dispose(close=False)
        await asyncio.sleep(0.05)
        return await call_next(request)
```

Plus engine `connect_args`:
```python
connect_args = {
    "keepalives": 1,
    "keepalives_idle": 60,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}
```

### Outbound message lifecycle (in-place edit)

When the first forward of a fresh thread arrives, we send a Gupshup interactive message and store the returned `message_id` in `whatsapp_thread_state.interactive_msg_id`. On every subsequent forward in the same thread, we **edit that message in place** with updated counts (Gupshup supports `edit-message` for interactive content within ~5min). This avoids spamming the chat with N progress lines.

If the edit window has closed or the edit fails, we send a new buttons message and update `interactive_msg_id`.

---

## 3. Edge-case behavior matrix

### Definite fixes (all in scope)

| # | Edge case | Behavior |
|---|-----------|----------|
| 1 | Photo / PDF / audio / video arrives before any text | Buffer to `whatsapp_pending_media`. Don't create a story yet. Send `[Submit][Cancel]` buttons. If text arrives in the same thread before the 60s idle window closes, it joins. If 60s elapse with no further messages, force-finalize as a media-only story (auto-submit). |
| 2 | Cloud SQL connection dies mid-query | Retry middleware catches `OperationalError` / `DBAPIError` → invalidate pool → retry once. Transparent to Gupshup. |
| 3 | Forward from unregistered phone | Reply: *"Your number isn't registered as a Vrittant reporter. Please contact your editor."* Webhook returns 200. |
| 4 | Empty / emoji-only / under-20-word forward | Reply: *"Couldn't read enough content (need 20+ words). Please re-forward with more detail."* No story, no thread. |
| 5 | Reply-quote of a non-confirmation message | Treat as fresh message; ignore the quote context. |
| 6 | Add-to-story when target is approved / rejected / published / has WP post | Reply: *"Story PNS-26-688 is locked. New content will be saved as a fresh story."* Then process as new thread. |
| 7 | Voice notes / audio | Buffer as `media_type='audio'`. On thread submit, audio is attached but not transcribed. The saved-confirmation appends a one-time hint about the mobile app for dictation (`audio_warning_shown=TRUE` thereafter). |
| 8 | Sticker / GIF / location / contact card | Single reply: *"Sticker/location not saved. Forward text or photos to submit a story."* No thread opened. |
| 9 | Two unrelated thread groups from same reporter (false-merge risk) | Thread auto-closes after 60s idle. Next forward starts a new thread. |
| 10 | Out-of-order Gupshup delivery | Pending-media buffer + 60s idle window handles this — order doesn't matter, only window membership. |
| 11 | "Forwarded from: ..." boilerplate at start of forwarded text | Strip leading quote-line in pre-processing before LLM call. |
| 12 | PDF attachment | Buffered → adopted into thread → stored in GCS → attached to story as a `document` paragraph type. Not parsed for content. |
| 13 | Same photo / PDF / audio sent twice in a session | Content hash matched in `whatsapp_content_dedup` → silently skip second. |
| 14 | Same text sent twice | Same — content hash dedup. |
| 15 | `[Submit]` clicked on empty thread | Reply: *"Nothing to submit yet. Forward your story first."* Buttons stay live. |
| 16 | `[Cancel]` clicked | Drain pending_media (delete buffer rows + GCS files), close thread state. Reply: *"Cancelled."* |
| 17 | Buttons tapped on confirmation > 24h old | WhatsApp won't deliver the click anyway; defensive: reply *"This story is too old to edit from WhatsApp. Use the mobile app."* |
| 18 | Cross-reporter add attempt (reply-quoting another reporter's confirmation) | Reject: *"Cannot edit another reporter's story."* |

### Deferred (out of scope this round)

| # | Edge case | Reason |
|---|-----------|--------|
| D1 | Mixed Odia + English LLM handling | Working acceptably; real fix is prompt tuning |
| D2 | Document content extraction (PDF body text into story) | Reporters use PDFs as supplementary; story body is the WhatsApp text |

---

## 4. Outbound message UX

All copy is the reporter's `org.default_language` (Odia for Pragativadi, Sambad). The catalog includes Odia, Hindi, English. Below shown in English for the spec; Odia/Hindi translations are produced as part of implementation.

### A. First forward in fresh session (interactive, in-place editable)
```
📥 Got 1 message (text).
Forward more, or tap when finished.

[✓ Submit Story]  [✕ Cancel]
```
On subsequent forwards: edits in place — *"Got 3 messages (1 text + 2 photos)"*.

### B. Story saved (interactive, anchors reply-quote)
```
✓ Story saved
ID: PNS-26-688
"<headline truncated to 80 chars>…"

[➕ Add more]  [📋 Today]  [📱 Open in app]
```

### C. Add-to-story progress (in-place editable)
```
➕ Adding to PNS-26-688
Got 2 more (1 text + 1 photo).

[✓ Save additions]  [✕ Discard]
```

### D. Today's stories list (plain text + CTA URL button)
```
📋 Your stories today (24):

• PNS-26-708 — Bypoll results announced; BJP w...
• PNS-26-707 — ବିଜେପିର ବିଜୟ ଉତ୍ସବ ପାଳନ
• PNS-26-706 — ଜନ ଶୁଣାଣିରେ ୧୧୫ ଅଭିଯୋଗ
… (up to 25 lines)

[📱 Open all in Vrittant app]
```
- 0 stories: *"📭 No stories filed today. Forward a story to submit."*
- 26+ stories: first 25 + line *"(+N more — tap below to see all)"*
- Headlines truncated to 50 chars
- CTA URL button targets `https://vrittant.in/r/today`

### E. Menu fallback (free-text that doesn't match a forward)
```
☰ What would you like to do?

[☰ Open menu]
```
Tap → List Message:
```
☰ Vrittant
Submit something
  📥 Just forward your message
View
  📋 My stories filed today
Help
  ❓ How to use Vrittant on WhatsApp
```

### F. Edge-case replies (terse, single line each)

| Trigger | Reply |
|---------|-------|
| Unregistered phone | "Your number isn't registered. Please contact your editor." |
| < 20 words | "Couldn't read enough content (need 20+ words). Please re-forward with more detail." |
| Sticker / GIF / location | "Sticker/location not saved. Forward text or photos to submit a story." |
| Locked story add attempt | "Story PNS-26-688 is locked. New content will be saved as a fresh story." |
| Cross-reporter add attempt | "Cannot edit another reporter's story." |
| Empty submit click | "Nothing to submit yet. Forward your story first." |
| Cancel click | "Cancelled. Your forwards were not saved." |
| Old buttons clicked | "This story is too old to edit from WhatsApp. Use the mobile app." |
| Audio buffered (one-time only) | "For Odia dictation, the Vrittant mobile app gives you live transcription." |

---

## 5. Internationalization

### Language resolution

```python
def resolve_lang(user: User) -> str:
    if user and user.org and user.org.default_language:
        return user.org.default_language
    return 'or'  # platform default
```

Per-reporter override deferred. Org-level setting covers all current orgs; future Hindi-language org admin sets `'hi'` via Settings panel (UI dropdown added later).

### Catalog

`api/app/services/whatsapp/i18n.py`:

```python
STRINGS = {
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
    "btn.submit":  {"or": "✓ ଖବର ଦାଖଲ କରନ୍ତୁ", "hi": "✓ खबर जमा करें", "en": "✓ Submit Story"},
    "btn.cancel":  {"or": "✕ ବାତିଲ କରନ୍ତୁ",     "hi": "✕ रद्द करें",       "en": "✕ Cancel"},
    "saved":       {"or": "✓ ଖବର ସଞ୍ଚୟ ହୋଇଛି", "hi": "✓ खबर सहेजी गई",   "en": "✓ Story saved"},
    "btn.add":     {"or": "➕ ଅଧିକ ଯୋଡ଼ନ୍ତୁ",   "hi": "➕ और जोड़ें",       "en": "➕ Add more"},
    "btn.today":   {"or": "📋 ଆଜିର ଖବର",       "hi": "📋 आज की खबरें",   "en": "📋 Today"},
    "btn.openApp": {"or": "📱 ଆପରେ ଦେଖନ୍ତୁ",  "hi": "📱 ऐप में खोलें",   "en": "📱 Open in app"},
    # …~35-40 keys total; full catalog produced during implementation
}

def t(key: str, lang: str, **vars) -> str:
    s = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("en") or key
    return s.format(**vars) if vars else s
```

### What stays in English regardless of locale

- Story display IDs (`PNS-26-688`)
- Universal-Link URLs (`vrittant.in/r/<id>`)
- Reporter-authored headlines (preserved as written)
- Brand name "Vrittant"

---

## 6. Universal Links (mobile app deep linking)

### URL scheme

| URL | Mobile app destination |
|-----|------------------------|
| `https://vrittant.in/r/<story_id>` | Story review screen for that ID |
| `https://vrittant.in/r/today` | Today-filtered stories list (reporter's own) |

### Behavior

- **App installed:** OS intercepts `https://vrittant.in/r/*` → opens Vrittant app → app routes to the right screen.
- **App not installed:** Browser opens fallback page at `vrittant.in/r/<id>`. The page renders only install-app badges; no story content, no login, no panel access. Pure redirect-to-store.

### Setup work (mobile + panel)

**Panel/static hosting (Firebase):**
- Serve `apple-app-site-association` JSON at `vrittant.in/.well-known/apple-app-site-association` with `Content-Type: application/json` and no extension.
- Serve `assetlinks.json` at `vrittant.in/.well-known/assetlinks.json`.
- Implement `/r/<id>` and `/r/today` fallback routes in the existing React panel — minimal page that detects `User-Agent` and shows store badges.

**iOS (Flutter mobile):**
- Add `Associated Domains` capability in Xcode → entitlements include `applinks:vrittant.in`.
- Implement `NSUserActivity` handler in `AppDelegate.swift` → forwards URL to Flutter via the `flutter_app_links` package (or equivalent).
- Flutter route handler maps `/r/<id>` → push `StoryReviewScreen(id)`, `/r/today` → push today-filtered list.

**Android (Flutter mobile):**
- Add `<intent-filter>` with `android:autoVerify="true"` for `https://vrittant.in/r/*` in `AndroidManifest.xml`.
- Same Flutter route handler.

**Verification:**
- iOS: `xcrun simctl openurl booted https://vrittant.in/r/abc-123` — should open app.
- Android: `adb shell am start -a android.intent.action.VIEW -d "https://vrittant.in/r/abc-123"` — should open app.

### Caveat

Universal Links can be flaky on first install (iOS sometimes opens Safari before the app handshake completes). The fallback page handles this transparently (it shows install badges for already-installed users too if iOS misroutes), so worst case is a one-time "tap again" hiccup. Documented but not engineered around.

---

## 7. Reliability & observability

### Retry middleware (the 503 fix)

- Wraps `/webhooks/whatsapp/*` and other Gupshup webhook routes
- Catches `OperationalError`, `DBAPIError`, `psycopg2.DatabaseError` (filtered for transient codes)
- Invalidates the engine connection (`engine.dispose(close=False)`)
- Sleeps 50ms, retries once
- If retry also fails → 503 to Gupshup (which will retry naturally)
- Logs every retry to a structured field for alerting

### TCP keepalives on the engine

```python
connect_args["keepalives"] = 1
connect_args["keepalives_idle"] = 60
connect_args["keepalives_interval"] = 10
connect_args["keepalives_count"] = 3
```

### Logging

Structured log line per webhook call:
```json
{
  "event": "whatsapp_webhook",
  "phone": "+919...",
  "kind": "forward|button|quoted|menu|skip",
  "thread_state": "new|continuing|add",
  "media_count": 0,
  "result": "buffered|created|appended|rejected|deduped",
  "story_id": "...",
  "duration_ms": 142,
  "retried": false
}
```

### Metrics (deferred, but logging is structured for easy extraction later)

- Webhook success rate
- Pending-media drain rate
- Content-dedup hit rate

---

## 8. Migration & rollout

### DB migrations
1. `migrations/2026-05-06-whatsapp-self-service.sql` — all four new tables + columns + indexes
2. Apply to UAT (`vrittant_uat`) first; smoke-test for 24h
3. Apply to prod (`vrittant`) before the corresponding code deploy

### Backend code
- Behind a config flag `WHATSAPP_SELF_SERVICE_ENABLED` (default `false` in prod for first deploy)
- Enable on UAT, run for 48h with internal testers
- Enable in prod once stable

### Mobile app
- Universal Link handlers shipped in next mobile release (1.0.10+19 or higher)
- Backend can deploy first — sending Universal Links to old app versions just opens the fallback web page, no breakage

### Translations
- All Odia and Hindi strings reviewed by a native speaker (Pragativadi editor) before prod enable
- English strings serve as the source of truth for any future locale

---

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Gupshup `edit-message` API doesn't support all interactive types or has tight time window | Implementation falls back to sending a fresh interactive message if edit fails; first-class behavior, not error |
| Universal Link `apple-app-site-association` requires HTTPS + correct MIME type — Firebase Hosting historically tricky | Test the file exactly as Apple's validator expects; serve via Firebase rewrite rule with explicit `Content-Type: application/json` |
| Reporter has multiple recent stories — "Add more" button on which one? | Button appears only on the most-recent saved confirmation; reply-quote handles older stories explicitly |
| Pending-media drain crosses an LLM call timeout | Drain is sync DB-only; LLM call happens after drain commits. Decouples buffer from inference |
| Two reporters share a phone (sub-stringer scenario) | Out of scope — phone is the unique key today |
| Org admin without Settings UI to change `default_language` | Initial value seeded via SQL per org; settings UI dropdown is a follow-up |

---

## 10. Acceptance criteria

A reporter on Pragativadi (org default `or`) can:

1. Forward a 50-word Odia text → see *"📥 ୧ଟି ବାର୍ତ୍ତା ପାଇଲି"* with `[✓ ଖବର ଦାଖଲ କରନ୍ତୁ]` button.
2. Forward 2 photos in the same WhatsApp session within 60s → see the buttons message edit in place to *"Got 3 messages (1 text + 2 photos)"*.
3. Tap `[✓ ଖବର ଦାଖଲ କରନ୍ତୁ]` → receive *"✓ ଖବର ସଞ୍ଚୟ ହୋଇଛି"* with `[➕ ଅଧିକ ଯୋଡ଼ନ୍ତୁ] [📋 ଆଜିର ଖବର] [📱 ଆପରେ ଦେଖନ୍ତୁ]`.
4. Tap `[📋 ଆଜିର ଖବର]` → receive a list of their today's stories.
5. Long-press the saved confirmation → Reply with *"correction: BJP won 4 seats"* → see "Adding to PNS-26-688" thread → tap save → text appended.
6. Forward a sticker → see polite single-line decline.
7. Forward a 5-word message → see "need 20+ words" rejection.
8. Receive an unregistered-phone reply if not in the User table.
9. Submit a forward exactly when Cloud SQL has a stale connection → request succeeds (retry middleware masked it).
10. Forward 26 stories in a day, then ask for "today" → see first 25 stories listed + *"(+1 more)"* + `[📱 Open all in Vrittant app]` button → tapping opens mobile app's today-filtered list.

---

## 11. Implementation order

When the writing-plans skill produces the task plan, tasks are ordered:

1. **DB migration + reliability layer** (foundation)
2. **i18n catalog + Odia strings** (so all subsequent UI is correctly localized)
3. **Refactor existing webhook into dispatcher + service modules** (no behavior change)
4. **Universal media buffer + content dedup** (fixes #1, #10, #12, #13, #14)
5. **Buttons replace "done" + thread state + ack messages** (UX foundation)
6. **Edge-case handlers** (#3, #4, #7, #8, #11, #15, #16, #17)
7. **"Today's stories" handler**
8. **Add-to-story (reply-quote + button)** (#5, #6, #18)
9. **Universal Link infrastructure** (panel fallback page + asset files + mobile app handlers)
10. **End-to-end smoke tests on UAT**
11. **Prod enablement behind feature flag**

Each task ships independently; tasks 1-4 deliver value (fixes and reliability) before any new user-facing feature lands.
