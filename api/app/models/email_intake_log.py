"""Audit log of every inbound email SendGrid forwarded to us.

One row per delivery — created or rejected. Used for:
  * Idempotency: we dedupe by (organization_id, message_id) so SendGrid
    retries don't double-create stories.
  * Forensics: when a reporter says "I emailed it but no story
    appeared", an admin can search the log by from_addr or subject and
    see the exact reason it was dropped.

Status vocabulary:
  * accepted      — story created. story_id points at it.
  * dropped_org   — local part didn't match any org slug.
  * dropped_fwd   — forwarding gateway not in OrgConfig.email_forwarders.
  * dropped_sender — no active reporter in the org with that email.
  * dropped_spam  — SendGrid spam score over threshold.
  * dropped_dup   — duplicate Message-ID.
  * error         — unexpected failure during processing (see error_msg).
"""
from __future__ import annotations

import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


class EmailIntakeLog(Base):
    __tablename__ = "email_intake_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Optional — not every drop happens inside an org context (e.g. the
    # local part didn't match any slug). Nullable so we can still log
    # the drop for forensics.
    organization_id = Column(
        String, ForeignKey("organizations.id"), nullable=True, index=True
    )
    # Email Message-ID header. Together with org_id this is the dedupe
    # key. Not unique on its own because different orgs *could* (in
    # theory) receive the same Message-ID from upstream weirdness.
    message_id = Column(String, nullable=True, index=True)
    from_addr = Column(String, nullable=True)
    to_addr = Column(String, nullable=True)
    forwarder_addr = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    spam_score = Column(String, nullable=True)
    status = Column(String, nullable=False)
    story_id = Column(String, ForeignKey("stories.id"), nullable=True, index=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_ist, nullable=False)

    story = relationship("Story", foreign_keys=[story_id])

    __table_args__ = (
        # The dedupe lookup. Composite index because we always filter
        # by (org_id, message_id) together.
        Index("ix_email_intake_org_msgid", "organization_id", "message_id"),
    )
