"""Inbound email webhook (SendGrid Inbound Parse → Story).

POST /internal/email/inbound?token=<secret>

SendGrid POSTs multipart/form-data with the parsed message:
  * to, from, subject       — header values (raw, may include display names)
  * text, html              — body parts
  * headers                 — full raw header dump as a single string
  * envelope                — JSON {"to": [...], "from": "..."}
  * spam_score              — SpamAssassin float
  * attachments             — int (count); files arrive as
                               attachment1, attachment2, …

We always return 200 to SendGrid so it doesn't retry on drops we
made on purpose. The actual outcome (accepted / dropped / error) is
recorded in email_intake_log for forensics.
"""
from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.org_config import OrgConfig
from ..models.story import Story
from ..services.email_intake import (
    MAX_ATTACHMENTS_PER_STORY,
    SPAM_THRESHOLD,
    already_processed,
    candidate_destinations,
    clean_subject,
    extract_forwarder,
    extract_message_id,
    find_org_by_slug,
    is_accepted_image,
    log_intake,
    org_slug_from_to,
    parse_address,
    resolve_sender,
    split_paragraphs,
)
from ..services.storage import save_file
from ..utils.tz import now_ist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/email", tags=["email-intake"])


def _require_internal_token(token: Optional[str]) -> None:
    """Mirrors internal.py's auth check. Reused so SendGrid can hit
    the same secret as the Cloud Scheduler jobs do."""
    if not settings.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoints disabled (no INTERNAL_TOKEN set)",
        )
    if not token or token != settings.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal token",
        )


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@router.post("/inbound")
async def email_inbound(
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_internal_token(token)

    # SendGrid posts multipart/form-data. Read everything into form
    # so attachments are available alongside the named fields.
    form = await request.form()
    to_header     = (form.get("to") or "").strip()
    envelope_raw  = (form.get("envelope") or "").strip()
    from_value    = (form.get("from") or "").strip()
    subject_value = (form.get("subject") or "").strip()
    text_body     = (form.get("text") or "").strip()
    headers       = (form.get("headers") or "").strip()
    spam_score    = _safe_float(form.get("spam_score"))

    from_name, from_email = parse_address(from_value)
    message_id = extract_message_id(headers)
    forwarder  = extract_forwarder(headers, settings.INBOUND_EMAIL_DOMAIN)

    # Walk envelope.to → To: header in that order. SendGrid's `to`
    # header for forwarded mail still says satrujitm5@gmail.com (the
    # original recipient), but the SMTP envelope carries the real
    # destination pragativadi@desk.vrittant.in. We need the envelope
    # to route this to Pragativadi.
    org_slug = None
    to_value = to_header  # default for logging
    for cand in candidate_destinations(envelope_raw, to_header):
        slug = org_slug_from_to(cand, settings.INBOUND_EMAIL_DOMAIN)
        if slug:
            org_slug = slug
            to_value = cand
            break

    log_kwargs = dict(
        message_id=message_id,
        from_addr=from_email or None,
        to_addr=to_value or None,
        forwarder_addr=forwarder,
        subject=subject_value,
        spam_score=str(spam_score) if spam_score is not None else None,
    )

    # ── 1. Org by local part of To ────────────────────────────────────
    org = find_org_by_slug(db, org_slug) if org_slug else None
    if org is None:
        log_intake(db, organization_id=None, status="dropped_org", **log_kwargs)
        db.commit()
        return {"detail": "ok"}

    log_kwargs["organization_id"] = org.id

    # ── 1b. Gmail forwarding verification ───────────────────────────────
    # When an admin adds a new forwarding address in Gmail, Google
    # mails forwarding-noreply@google.com → <new-address> with a
    # 9-digit confirmation code (and a clickable URL). Without this
    # branch the email would fail the forwarder/sender allowlists and
    # silently drop, leaving the admin no way to complete the setup
    # except through a temporary webhook.site detour. We capture the
    # body in error_msg so the code can be grepped from the audit
    # table:
    #   SELECT created_at, subject, error_msg
    #   FROM email_intake_log
    #   WHERE status = 'forwarding_verification'
    #   ORDER BY created_at DESC LIMIT 1;
    if from_email == "forwarding-noreply@google.com":
        log_intake(
            db,
            status="forwarding_verification",
            # Truncate generously — the verification body is ~1.5KB
            # of plain text. Cap protects us against pathological
            # payloads.
            error_msg=(text_body or "(empty body)")[:8000],
            **log_kwargs,
        )
        db.commit()
        return {"detail": "ok"}

    # ── 2. Dedup early — we may already have this Message-ID even if
    #      the row was a drop. Skip on retries so we don't double-log.
    if message_id and already_processed(db, org.id, message_id):
        return {"detail": "ok"}

    # ── 3. Spam ────────────────────────────────────────────────────────
    if spam_score is not None and spam_score > SPAM_THRESHOLD:
        log_intake(db, status="dropped_spam", **log_kwargs)
        db.commit()
        return {"detail": "ok"}

    # ── 4. Forwarder allowlist ────────────────────────────────────────
    cfg = db.query(OrgConfig).filter(OrgConfig.organization_id == org.id).first()
    forwarders = (cfg.email_forwarders if cfg and isinstance(cfg.email_forwarders, list) else []) or []
    forwarder_lower = (forwarder or "").lower()
    if not forwarder_lower or forwarder_lower not in {(f or "").lower() for f in forwarders}:
        log_intake(
            db,
            status="dropped_fwd",
            error_msg=f"forwarder {forwarder!r} not in allowlist",
            **log_kwargs,
        )
        db.commit()
        return {"detail": "ok"}

    # ── 5. Sender resolution (reporter or whitelisted contributor) ────
    sender = resolve_sender(db, org.id, from_email, from_name, cfg)
    if sender is None:
        log_intake(db, status="dropped_sender", **log_kwargs)
        db.commit()
        return {"detail": "ok"}

    # ── 6. Build the Story ─────────────────────────────────────────────
    paragraphs = split_paragraphs(text_body)

    # Walk attachments. SendGrid posts a count under `attachments` and
    # the actual files as `attachment1`, `attachment2`, …. We also
    # scan ALL form keys for anything matching the attachment pattern
    # — defence in depth in case SendGrid ever switches naming
    # conventions or Gmail forwards inline images differently. The
    # full list of attachment-shaped keys is logged for forensics.
    try:
        attach_count_advertised = int(form.get("attachments") or 0)
    except (TypeError, ValueError):
        attach_count_advertised = 0

    # Discover attachment-shaped form keys ourselves rather than
    # trusting the count alone — handles attachment-1, attachment_1,
    # and inline-image renames.
    attachment_keys = [
        k for k in form.keys()
        if k.startswith("attachment") and k != "attachments" and k != "attachment-info"
    ]
    log_kwargs["attachment_count_received"] = attach_count_advertised or len(attachment_keys)
    log_kwargs["attachment_keys"] = ",".join(sorted(attachment_keys))

    image_paragraphs: list[dict] = []
    rejected_kinds: list[str] = []
    for key in sorted(attachment_keys):
        if len(image_paragraphs) >= MAX_ATTACHMENTS_PER_STORY:
            break
        upload = form.get(key)
        if upload is None or not hasattr(upload, "read"):
            rejected_kinds.append(f"{key}:not-file")
            continue
        filename = (getattr(upload, "filename", "") or "").strip() or key
        content_type = getattr(upload, "content_type", "") or ""
        if not is_accepted_image(filename, content_type):
            rejected_kinds.append(f"{filename}:{content_type}")
            logger.info(
                "email-intake rejecting non-image attachment: key=%s name=%s type=%s",
                key, filename, content_type,
            )
            continue
        try:
            blob = await upload.read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("email-intake attachment read failed: %s", exc)
            continue
        if not blob:
            continue
        media_url = save_file(blob, filename, subfolder="story-media")
        image_paragraphs.append({
            "id": str(uuid_mod.uuid4()),
            "text": "",
            "media_path": media_url,
            "media_type": "photo",
            "media_name": filename,
        })

    log_kwargs["attachment_count_accepted"] = len(image_paragraphs)

    # Surface rejection reasons in the audit log so future debugging
    # ("why didn't my photo come through?") doesn't need Cloud Run
    # log-grepping. Rejections aren't errors — they're expected for
    # videos / PDFs / signature image footers — but we want to see
    # them.
    rejection_msg = "; ".join(rejected_kinds) if rejected_kinds else None

    paragraphs.extend(image_paragraphs)

    headline = clean_subject(subject_value) or (
        # Fall back to the first non-empty paragraph if there's no
        # usable subject — avoids inserting empty-headline stories
        # that the dashboard later filters out.
        next(
            (p["text"][:200] for p in paragraphs if (p.get("text") or "").strip()),
            "(No subject)",
        )
    )

    now = now_ist()
    story = Story(
        id=str(uuid_mod.uuid4()),
        reporter_id=sender.id,
        organization_id=org.id,
        headline=headline,
        paragraphs=paragraphs,
        category="",
        priority="normal",
        status="submitted",
        submitted_at=now,
        # Source string is human-facing in the side panel: "Email · X"
        # makes it obvious where the story originated. Includes the
        # contributor's email so an editor can quickly see the
        # attribution chain when investigating an odd submission.
        source=f"Email · {from_email}",
        assigned_to=None,  # let existing routing kick in via assignment service
        created_at=now,
        updated_at=now,
    )
    story.refresh_search_text()
    db.add(story)
    db.flush()

    log_intake(
        db,
        status="accepted",
        story_id=story.id,
        error_msg=rejection_msg,
        **log_kwargs,
    )
    db.commit()

    return {"detail": "ok", "story_id": story.id}
