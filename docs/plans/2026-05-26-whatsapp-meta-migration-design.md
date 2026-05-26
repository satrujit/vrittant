# WhatsApp: Gupshup → Meta Cloud API Migration

## Goal

Replace Gupshup as the WhatsApp Business API middleware and connect directly to Meta's WhatsApp Cloud API, eliminating per-message platform markup (~₹15,000–25,000/month at current volume).

## Current Architecture

```
Reporter → WhatsApp → Meta → Gupshup → POST /webhooks/whatsapp/gupshup → Vrittant API
Vrittant API → POST api.gupshup.io/wa/api/v1/msg → Gupshup → Meta → WhatsApp → Reporter
```

## Target Architecture

```
Reporter → WhatsApp → Meta → POST /webhooks/whatsapp/meta → Vrittant API
Vrittant API → POST graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages → Meta → WhatsApp → Reporter
```

## Cost Impact

| Item | Gupshup (current) | Meta Direct |
|------|-------------------|-------------|
| Inbound messages | Free (Meta) + markup (Gupshup) | **Free** |
| Service replies (within 24h of user msg) | Free (Meta) + markup (Gupshup) | **Free** |
| Business-initiated (you msg first) | ₹0.30–0.70 (Meta) + markup | ₹0.30–0.70 (Meta only) |
| Monthly platform fee | Varies by plan | **Free** |
| **Estimated monthly savings** | | **₹15,000–25,000** |

## Pre-requisites (Manual — Meta Business Manager)

Before any code changes, these steps must be done in Facebook Business Manager:

1. **Meta Business Account** — verify the Vrittant business (if not already)
2. **WhatsApp Business App** — create in Meta Developer Console (developers.facebook.com)
3. **Port the phone number** — request Gupshup to release `+91 89843 36534` from their WABA → register on Vrittant's own WABA. Takes 2–7 days. OR use a new number (faster, but reporters need updating).
4. **Generate permanent access token** — System User → Generate Token with `whatsapp_business_messaging` permission
5. **Configure webhook** — Point to `https://api.vrittant.in/webhooks/whatsapp/meta` with a verify token
6. **Subscribe to fields** — `messages` field on the WhatsApp Business Account

**Credentials you'll get:**
- `WHATSAPP_PHONE_NUMBER_ID` — numeric ID of your phone number (not the phone number itself)
- `WHATSAPP_ACCESS_TOKEN` — permanent system user token
- `WHATSAPP_APP_SECRET` — for webhook signature verification (HMAC-SHA256)
- `WHATSAPP_VERIFY_TOKEN` — arbitrary string for webhook URL verification challenge

---

## Implementation Plan

### Task 1: Add Meta Cloud API config + env vars

**Files:**
- Modify: `api/app/config.py`
- Modify: Server `.env` files (on Hetzner)

**Changes:**

Add to Settings class in `config.py`:
```python
# WhatsApp Cloud API (Meta direct)
WHATSAPP_PHONE_NUMBER_ID: str = ""
WHATSAPP_ACCESS_TOKEN: str = ""
WHATSAPP_APP_SECRET: str = ""      # HMAC-SHA256 webhook verification
WHATSAPP_VERIFY_TOKEN: str = ""    # GET challenge verify token
```

Remove (after full cutover):
```python
GUPSHUP_WEBHOOK_SECRET: str = ""
```

Add to `/opt/vrittant/.env` on Hetzner:
```
WHATSAPP_PHONE_NUMBER_ID=<from Meta>
WHATSAPP_ACCESS_TOKEN=<from Meta>
WHATSAPP_APP_SECRET=<from Meta>
WHATSAPP_VERIFY_TOKEN=<random string>
```

---

### Task 2: Rewrite outbound.py for Meta Cloud API

**Files:**
- Modify: `api/app/services/whatsapp/outbound.py`

**Key differences from Gupshup:**

| Gupshup | Meta Cloud API |
|---------|---------------|
| `POST api.gupshup.io/wa/api/v1/msg` | `POST graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages` |
| `Content-Type: x-www-form-urlencoded` | `Content-Type: application/json` |
| `apikey` header | `Authorization: Bearer {TOKEN}` |
| `quick_reply` type for buttons | `interactive` type with `button` action |
| `list` type for lists | `interactive` type with `list` action |
| `postbackText` for button IDs | `id` field in button/row |
| Edit endpoint exists | **No edit support** — send new message |

**New outbound.py structure:**

```python
META_API_BASE = "https://graph.facebook.com/v21.0"

def _url():
    return f"{META_API_BASE}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

def _headers():
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

async def send_text(*, to: str, body: str) -> Optional[str]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "text",
        "text": {"body": body},
    }
    # POST → extract messages[0].id

async def send_interactive_buttons(*, to, body, buttons, header=None) -> Optional[str]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": header} if header else None,
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                    for bid, label in buttons[:3]
                ]
            }
        }
    }

async def send_interactive_list(*, to, body, button_label, sections, header=None) -> Optional[str]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header} if header else None,
            "body": {"text": body},
            "action": {
                "button": button_label[:20],
                "sections": [
                    {
                        "title": title[:24],
                        "rows": [
                            {"id": rid, "title": rtitle[:24], "description": (rdesc or "")[:72]}
                            for rid, rtitle, rdesc in rows[:10]
                        ]
                    }
                    for title, rows in sections[:10]
                ]
            }
        }
    }

async def edit_or_send_interactive(...) -> Optional[str]:
    # Meta doesn't support editing — always send a fresh message
    return await send_interactive_buttons(to=to, body=body, buttons=buttons)
```

**Response format change:**
- Gupshup returns `{"messageId": "..."}`
- Meta returns `{"messages": [{"id": "wamid.xxx"}]}`

---

### Task 3: Rewrite webhook auth for Meta signature verification

**Files:**
- Modify: `api/app/services/whatsapp/auth.py`

**Meta's webhook security:**

1. **Verification challenge** (GET request when you register the webhook URL):
   ```
   GET /webhooks/whatsapp/meta?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=CHALLENGE
   → Return hub.challenge as plain text if hub.verify_token matches
   ```

2. **Payload signature** (on every POST):
   - Header: `X-Hub-Signature-256: sha256=<hex>`
   - Computed: `HMAC-SHA256(app_secret, raw_body)`
   - This is proper HMAC (unlike Gupshup's shared-secret token)

```python
import hashlib, hmac

def verify_meta_signature(*, body: bytes, headers: dict, secret: str) -> bool:
    sig_header = headers.get("x-hub-signature-256", "")
    if not sig_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = sig_header[7:]  # strip "sha256="
    return hmac.compare_digest(expected, received)
```

---

### Task 4: New webhook endpoint + payload parser

**Files:**
- Modify: `api/app/routers/webhooks_whatsapp.py`

**Add two new endpoints:**

```python
@router.get("/meta")
async def meta_verify(request: Request):
    """Meta webhook verification challenge (one-time on registration)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return Response(status_code=403)

@router.post("/meta")
async def meta_inbound(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    # Meta wraps everything in entry[].changes[].value
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value.get("messaging_product") != "whatsapp":
                continue
            for message in value.get("messages", []):
                await _process_meta_message(message, value, db)
            for status in value.get("statuses", []):
                pass  # delivery receipts — ignore
    return {"ok": True}
```

**Meta message payload → normalized format:**

| Meta field | Maps to |
|-----------|---------|
| `message.id` | `msg_id` (dedup) |
| `message.from` | `sender_phone` |
| `message.type` | `inner_type` (text/image/document/audio/video/interactive/button) |
| `message.text.body` | text content |
| `message.image.id` / `.video.id` / etc. | media_id (need 2nd API call to get URL) |
| `message.interactive.button_reply.id` | button postback |
| `message.interactive.list_reply.id` | list row postback |
| `message.context.id` | quoted message ID |

**Critical difference — media handling:**

Gupshup gives you a direct download URL. Meta gives you a `media_id`. You need two API calls:
1. `GET graph.facebook.com/v21.0/{media_id}` → returns `{"url": "https://lookaside.fbsbx.com/..."}`
2. `GET <that URL>` with Bearer token → downloads the file

```python
async def _download_meta_media(media_id: str) -> tuple[bytes, str]:
    """Two-step media download from Meta Cloud API."""
    # Step 1: get the URL
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{META_API_BASE}/{media_id}",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
        )
        media_url = r.json()["url"]
    # Step 2: download the file
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            media_url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
        )
        return r.content, r.headers.get("content-type", "")
```

**SSRF update:** Change `_GUPSHUP_MEDIA_HOST_SUFFIXES` to allow Meta's media domains:
```python
_META_MEDIA_HOST_SUFFIXES = (
    ".fbsbx.com",
    ".fbcdn.net",
    ".whatsapp.net",
)
```

---

### Task 5: Update classifier.py for Meta payload shapes

**Files:**
- Modify: `api/app/services/whatsapp/classifier.py`

Meta sends button replies differently:
- Button tap: `message.type = "interactive"`, `message.interactive.type = "button_reply"`, ID in `message.interactive.button_reply.id`
- List tap: `message.type = "interactive"`, `message.interactive.type = "list_reply"`, ID in `message.interactive.list_reply.id`

The classifier needs to handle BOTH Gupshup and Meta shapes during the transition period (both endpoints alive until Gupshup is fully decommissioned).

---

### Task 6: Update dispatcher.py button extraction

**Files:**
- Modify: `api/app/services/whatsapp/dispatcher.py`

`_extract_button_id()` already has a WhatsApp Cloud API branch:
```python
interactive = payload.get("interactive") or {}
for sub in ("button_reply", "list_reply"):
    ref = interactive.get(sub) or {}
    if ref.get("id"):
        return ref["id"]
```

This will work with Meta's format. Just need to ensure the normalized payload passed from the new webhook endpoint includes the `interactive` field at the right level.

---

### Task 7: Normalize Meta payload → existing internal format

**Files:**
- Create: `api/app/services/whatsapp/meta_adapter.py`

The cleanest approach: write a thin adapter that converts Meta's message format into the same shape the existing dispatcher/classifier/handlers expect. This way we change **zero handler code** — only the inbound parsing and outbound sending change.

```python
def meta_to_internal(message: dict, value: dict) -> dict:
    """Convert a Meta Cloud API message to Gupshup-compatible internal format."""
    msg_type = message.get("type")
    
    result = {
        "id": message["id"],
        "sender": {"phone": message["from"]},
        "type": _map_type(msg_type, message),
        "payload": _map_payload(msg_type, message),
    }
    
    # Quoted reply context
    if "context" in message:
        result["context"] = {"id": message["context"].get("id")}
    
    return result
```

Type mapping:
- `"text"` → `"text"`, payload: `{"text": message["text"]["body"]}`
- `"image"` → `"image"`, payload: `{"url": <downloaded>, "caption": message["image"].get("caption")}`
- `"interactive"` with `button_reply` → `"button_reply"`, payload: `{"postbackText": message["interactive"]["button_reply"]["id"]}`
- `"interactive"` with `list_reply` → `"list_reply"`, payload: `{"postbackText": message["interactive"]["list_reply"]["id"]}`

---

### Task 8: Migration execution + testing

**Sequence:**

1. Deploy code with BOTH `/webhooks/whatsapp/gupshup` and `/webhooks/whatsapp/meta` endpoints live
2. Complete Meta Business Manager setup (pre-requisites above)
3. Port the phone number (or register new one)
4. Configure webhook URL on Meta → `https://api.vrittant.in/webhooks/whatsapp/meta`
5. Set env vars on Hetzner (`WHATSAPP_PHONE_NUMBER_ID`, etc.)
6. Test with a single reporter
7. Confirm messages flow correctly
8. Remove Gupshup env vars and old endpoint (cleanup commit)

**Rollback plan:** If Meta integration has issues, re-register the number with Gupshup and flip the webhook URL back. The old `/gupshup` endpoint stays deployed until confirmed working.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `api/app/config.py` | Add 4 new Meta env vars |
| `api/app/services/whatsapp/outbound.py` | Full rewrite: Gupshup → Meta Graph API |
| `api/app/services/whatsapp/auth.py` | HMAC-SHA256 body signature (replaces shared-secret) |
| `api/app/services/whatsapp/classifier.py` | Accept Meta interactive shapes alongside Gupshup |
| `api/app/services/whatsapp/dispatcher.py` | Minor — `_extract_button_id` already handles both |
| `api/app/routers/webhooks_whatsapp.py` | New `/meta` GET+POST endpoints, media download helper |
| `api/app/services/whatsapp/meta_adapter.py` | **New** — payload normalizer (Meta → internal format) |

**Zero changes needed in:**
- `dispatcher.py` handlers (handle_button, handle_forward, handle_quoted_reply, handle_skip)
- `i18n.py`, `buffer.py`, `thread_state.py`, `finalize.py`, `dedup.py`, `ingest.py`, `today.py`
- All models (whatsapp_buffer.py, webhook_dedup.py, story.py)

## Timeline

- **Pre-requisites (manual):** 1–2 hours in Meta Business Manager + 2–7 days for number porting
- **Code changes:** 2–3 days of development
- **Testing:** 1 day with a single reporter before full cutover
