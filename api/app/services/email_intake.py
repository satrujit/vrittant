"""SendGrid Inbound Parse → Vrittant Story.

Pure parsing helpers + the orchestrator that turns a parsed SendGrid
payload into a Story (or a logged drop).

Wire:
    SendGrid POSTs multipart/form-data → /internal/email/inbound
    The router calls process_intake(...) with the parsed form.
    process_intake validates, dedupes, and persists.

Validation chain (any failure = silent drop with logged reason):
  1. Resolve org from local part of the To: address.
  2. Forwarder allowlist: gateway address (from Received chain or
     explicit headers) must be in OrgConfig.email_forwarders.
  3. Sender match:
       a. Existing User in this org with matching email + reporter +
          active → use them.
       b. Else email in OrgConfig.whitelisted_contributors → find or
          create a passive User row (no phone, can't log in, but
          appears in the reporter list for attribution).
       c. Else drop.
  4. Spam: SendGrid spam_score > SPAM_THRESHOLD → drop.
  5. Dedup: (org_id, message_id) already in email_intake_log → no-op.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from email.utils import getaddresses, parseaddr
from typing import Optional

from sqlalchemy.orm import Session

from ..models.email_intake_log import EmailIntakeLog
from ..models.organization import Organization
from ..models.org_config import OrgConfig
from ..models.story import Story
from ..models.user import User
from ..utils.tz import now_ist

logger = logging.getLogger(__name__)

# SendGrid's spam_score is a SpamAssassin-style float. Threshold of
# 5.0 matches Postfix/Amavis defaults — anything above this is
# universally considered "almost certainly spam".
SPAM_THRESHOLD = 5.0

# Cap on stored attachment count per Story. Reporters submitting 30
# photos in one email is operationally unusual and indicates a
# misconfigured forwarding rule; cap to keep storage and the placement
# matrix render time bounded.
MAX_ATTACHMENTS_PER_STORY = 8

# Image extensions we accept as paragraph media. Matches the existing
# storage._media_type_from_ext "photo" set.
ACCEPTED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "bmp"}

# Subject prefixes we strip when promoting subject → headline. Run
# repeatedly because forwards-of-forwards stack ("Fwd: Fwd: Re:").
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(re|fwd|fw)\s*:\s*", re.IGNORECASE)

# Pull "for <addr>" out of a Received: header. Gmail's auto-forward
# leaves a Received line shaped like:
#   Received: by 2002:... ; for <pragativadi@gmail.com>; Sat, 26 Apr ...
# That "for" address is the *original* mailbox before forwarding —
# i.e. the gateway address we want to match against the allowlist.
_RECEIVED_FOR_RE = re.compile(r"\bfor\s+<([^>]+)>", re.IGNORECASE)


# ── Pure helpers (no DB) ────────────────────────────────────────────────


def parse_address(raw: str) -> tuple[str, str]:
    """Return (display_name, email_lowercase) from a header value like
    "Subash Sahoo <subash.pragati@gmail.com>". Returns ("", "") on
    junk input. Email is always lower-cased to match how we store
    allowlists and User.email."""
    if not raw:
        return "", ""
    name, addr = parseaddr(raw)
    return (name or "").strip(), (addr or "").strip().lower()


def org_slug_from_to(to_value: str, expected_domain: str) -> Optional[str]:
    """Extract the org slug from the local part of the To: address.

    Accepts the raw header value SendGrid hands us — may contain
    multiple addresses, display names, or angle brackets. Returns the
    first slug whose domain matches expected_domain (e.g.
    "desk.vrittant.in"). Returns None when no recipient matches.
    """
    if not to_value or not expected_domain:
        return None
    expected = expected_domain.lower().lstrip("@")
    for _name, addr in getaddresses([to_value]):
        addr = (addr or "").lower()
        if "@" not in addr:
            continue
        local, _, domain = addr.partition("@")
        if domain == expected and local:
            return local
    return None


def candidate_destinations(envelope_raw: str, to_header: str) -> list[str]:
    """Return all plausible destination addresses for this delivery.

    SendGrid Inbound Parse exposes two recipient fields and they
    disagree on forwarded mail:

      * ``to`` form field — taken from the email's To: HEADER. For a
        forwarded message that's still the *original* recipient (e.g.
        satrujitm5@gmail.com), not the address SendGrid actually
        received it for.
      * ``envelope`` form field — JSON like ``{"to": ["x@y"], "from":
        "..."}``. The ``to`` array carries the real SMTP-envelope
        recipient — i.e. ``pragativadi@desk.vrittant.in`` for our
        forwarded case.

    For routing we MUST trust the envelope; the header was correct
    only for direct sends. We return envelope addresses first, then
    the header value, so the router can try each in order until it
    finds one whose domain matches our INBOUND_EMAIL_DOMAIN.
    """
    out: list[str] = []
    if envelope_raw:
        try:
            env = json.loads(envelope_raw)
            env_to = env.get("to") or []
            if isinstance(env_to, str):
                env_to = [env_to]
            for addr in env_to:
                if addr:
                    out.append(str(addr))
        except (json.JSONDecodeError, TypeError, ValueError):
            # Malformed envelope — fall through to the header-based
            # candidate. Don't crash the whole intake on bad JSON.
            pass
    if to_header:
        out.append(to_header)
    return out


def extract_forwarder(headers: str, our_domain: str = "") -> Optional[str]:
    """Find the gateway address from the Received: header chain.

    SendGrid stamps its own "Received: ... for <X@desk.vrittant.in>"
    at the top of the chain — that's our own hop and tells us
    nothing about the upstream forwarder. We skip any "for" address
    whose domain matches ``our_domain`` (the inbound subdomain we
    own) and return the next one we find. That's the address the
    upstream MTA delivered to *before* the forwarding rule kicked in
    — i.e. the gateway mailbox we want to allowlist.

    Returns None when no other "for" address exists, which the
    router treats as a silent drop. ``our_domain`` defaults to empty
    only so unit tests can exercise the bare matcher; production
    callers always pass settings.INBOUND_EMAIL_DOMAIN.
    """
    if not headers:
        return None
    suffix = ("@" + our_domain.lower().lstrip("@")) if our_domain else None
    for line in headers.splitlines():
        if not line.lower().startswith("received:"):
            continue
        m = _RECEIVED_FOR_RE.search(line)
        if not m:
            continue
        addr = (m.group(1) or "").strip().lower()
        if not addr or "@" not in addr:
            continue
        # Skip our own SendGrid hop. Keep walking — the next "for" is
        # the actual upstream forwarder.
        if suffix and addr.endswith(suffix):
            continue
        return addr
    return None


def extract_message_id(headers: str) -> Optional[str]:
    """Pull the Message-ID header value (with brackets) for dedupe."""
    if not headers:
        return None
    for line in headers.splitlines():
        # RFC 5322 makes the header name case-insensitive.
        if line.lower().startswith("message-id:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def clean_subject(raw: str) -> str:
    """Strip stacked Re:/Fwd: prefixes and trailing whitespace.

    Important for forwarded mail — without this every story's
    headline reads "Fwd: Fwd: ..."."""
    s = (raw or "").strip()
    while True:
        next_s = _SUBJECT_PREFIX_RE.sub("", s, count=1)
        if next_s == s:
            break
        s = next_s
    return s.strip()


def split_paragraphs(text_body: str) -> list[dict]:
    """Split a plain-text email body into paragraph dicts shaped the way
    Story.paragraphs expects (each row is {"id": uuid, "text": str}).

    Two-stage normalisation, important for email content:

      1. **Strip quoted-reply trailers and signatures** at the
         body level (before splitting). Catches "On <date>, X wrote:"
         openers, "Sent from my iPhone" sigs, and the RFC 3676 "-- "
         signature delimiter.
      2. **Paragraph split**: blank line(s) = paragraph break.
      3. **Soft-wrap join**: within each paragraph, single newlines
         are *soft wraps* added by the sender's email client at ~70
         characters. Join those lines with a single space so the
         editor renders one flowing paragraph instead of dozens of
         short broken ones (which is what the editor was showing
         after the first real test).
    """
    if not text_body:
        return []

    body = text_body
    # 1a. Trim quoted-reply trailer.
    body = re.split(r"\n\s*On\s+.+\s+wrote:\s*\n", body, maxsplit=1)[0]
    # 1b. Trim mobile signature trailers.
    body = re.sub(
        r"\n\s*Sent from my (iPhone|iPad|Android|mobile|phone).*$",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # 1c. Trim RFC 3676 "-- " sig delimiter (everything after).
    body = re.split(r"\n--\s*\n", body, maxsplit=1)[0]

    paragraphs = []
    for chunk in re.split(r"\n\s*\n", body):
        # Soft-wrap join: every non-empty line in the chunk becomes
        # a space-separated continuation of the same paragraph. Keeps
        # bullet-style content (lines that already look intentional
        # — eg start with •, -, *, or a digit followed by . or )) on
        # their own lines so a list reads as a list.
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        joined: list[str] = []
        for line in lines:
            looks_like_list_item = bool(
                re.match(r"^([-*•·]|\d+[.)]\s)", line)
            )
            if joined and not looks_like_list_item:
                joined[-1] = joined[-1] + " " + line
            else:
                joined.append(line)
        text = "\n".join(joined).strip()
        if not text:
            continue
        paragraphs.append({"id": str(uuid.uuid4()), "text": text})
    return paragraphs


def is_accepted_image(filename: str, content_type: str) -> bool:
    """Gate uploads to image attachments. Rejects videos, PDFs, and
    executables — none of these belong on a story page, and storing
    them invites legal/security headaches we don't need to underwrite."""
    if not filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ACCEPTED_IMAGE_EXTS:
        return True
    # Defense in depth: trust the MIME type only if the extension is
    # missing/odd. SendGrid sniffs and reports content_type from the
    # MIME part header.
    if not ext and (content_type or "").lower().startswith("image/"):
        return True
    return False


# ── DB-side orchestration ───────────────────────────────────────────────


def find_or_create_contributor(
    db: Session,
    org_id: str,
    email: str,
    name: str,
) -> Optional[User]:
    """Find an existing reporter User by email within the org, or create
    a passive one for a whitelisted contributor.

    Passive contributor users:
      * user_type = "reporter"  → bylines + leaderboard work normally
      * phone     = "email:<addr>" (synthetic) → can never log in via OTP
      * is_active = True        → appears in reporter lists

    The synthetic phone is required because User.phone has NOT NULL +
    UNIQUE constraints. Prefixing with "email:" guarantees no
    collision with a real phone number (which always starts with +)
    and makes the row obviously a contributor in the admin view.

    Returns None if email is empty/junk.
    """
    if not email or "@" not in email:
        return None
    existing = (
        db.query(User)
        .filter(User.organization_id == org_id, User.email == email)
        .first()
    )
    if existing:
        return existing
    user = User(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name=(name or email.split("@", 1)[0]).strip()[:200],
        email=email,
        phone=f"email:{email}",
        user_type="reporter",
        area_name="",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def resolve_sender(
    db: Session,
    org_id: str,
    from_email: str,
    from_name: str,
    cfg: Optional[OrgConfig],
) -> Optional[User]:
    """Map an inbound From: address to a real User row, creating a
    contributor on first match if the email is whitelisted.

    Returns None when neither path resolves — caller treats this as a
    silent drop.
    """
    if not from_email:
        return None

    # 1. Existing reporter on file.
    user = (
        db.query(User)
        .filter(
            User.organization_id == org_id,
            User.email == from_email,
            User.user_type == "reporter",
            User.is_active == True,  # noqa: E712 — SQL truth-comparison
        )
        .first()
    )
    if user:
        return user

    # 2. Whitelisted contributor → find-or-create.
    if cfg and isinstance(cfg.whitelisted_contributors, list):
        for entry in cfg.whitelisted_contributors:
            if not isinstance(entry, dict):
                continue
            entry_email = (entry.get("email") or "").strip().lower()
            if entry_email != from_email:
                continue
            display_name = entry.get("name") or from_name or ""
            return find_or_create_contributor(
                db, org_id, from_email, display_name,
            )
    return None


def already_processed(db: Session, org_id: str, message_id: Optional[str]) -> bool:
    """True if we've already accepted (or definitively logged) this
    Message-ID for this org. Treats earlier drops as terminal — if it
    was spam yesterday, it's spam today; SendGrid's retries shouldn't
    give it a second look."""
    if not message_id:
        return False
    exists = (
        db.query(EmailIntakeLog.id)
        .filter(
            EmailIntakeLog.organization_id == org_id,
            EmailIntakeLog.message_id == message_id,
        )
        .first()
    )
    return exists is not None


def log_intake(
    db: Session,
    *,
    organization_id: Optional[str],
    message_id: Optional[str],
    from_addr: Optional[str],
    to_addr: Optional[str],
    forwarder_addr: Optional[str],
    subject: Optional[str],
    spam_score: Optional[str],
    status: str,
    story_id: Optional[str] = None,
    error_msg: Optional[str] = None,
    attachment_count_received: Optional[int] = None,
    attachment_count_accepted: Optional[int] = None,
    attachment_keys: Optional[str] = None,
) -> EmailIntakeLog:
    row = EmailIntakeLog(
        organization_id=organization_id,
        message_id=message_id,
        from_addr=from_addr,
        to_addr=to_addr,
        forwarder_addr=forwarder_addr,
        subject=(subject or "")[:500],
        spam_score=str(spam_score) if spam_score is not None else None,
        status=status,
        story_id=story_id,
        error_msg=(error_msg or None) if error_msg else None,
        attachment_count_received=attachment_count_received,
        attachment_count_accepted=attachment_count_accepted,
        attachment_keys=(attachment_keys or None)[:500] if attachment_keys else None,
    )
    db.add(row)
    return row


def find_org_by_slug(db: Session, slug: str) -> Optional[Organization]:
    if not slug:
        return None
    return db.query(Organization).filter(Organization.slug == slug.lower()).first()
