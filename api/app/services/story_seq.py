"""Per-org sequential story numbering for human-readable display IDs.

Reporters and editors see story IDs like ``PNS-26-1234`` instead of the
underlying UUID. The technical PK ``stories.id`` is still a UUID — this
module just allocates a per-org monotonic counter that drives the
display string.

Concurrency
-----------
Multiple WhatsApp inbounds + panel saves can land at the same instant.
We allocate via an UPSERT on ``org_story_seq`` so each call gets a
unique number even under race; no row locks on ``stories`` needed.
"""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def assign_next_seq(db: Session, organization_id: str) -> int:
    """Atomically allocate the next ``seq_no`` for ``organization_id``.

    Increments the per-org counter in one statement and returns the
    value to stamp onto the new story. The first call for an org seeds
    the counter at 1; the next bumps to 2; and so on.

    The caller is responsible for committing the transaction that wrote
    both the new story row and the bumped counter — they share the same
    session so a rollback rolls back both.
    """
    result = db.execute(
        text(
            """
            INSERT INTO org_story_seq (organization_id, next_seq)
            VALUES (:org, 2)
            ON CONFLICT (organization_id) DO UPDATE
                SET next_seq = org_story_seq.next_seq + 1
            RETURNING next_seq - 1
            """
        ),
        {"org": organization_id},
    ).scalar()
    return int(result)


def format_display_id(display_code: str | None, created_at: datetime | None, seq_no: int | None) -> str | None:
    """Format ``PNS-26-1234`` from the org code, year, and sequential number.

    Returns ``None`` when any input is missing — callers can fall back
    to the UUID or simply omit the field. We don't fabricate a partial
    ID because a half-formed display string is more confusing than no
    display string at all.
    """
    if not display_code or seq_no is None or created_at is None:
        return None
    yy = created_at.year % 100
    return f"{display_code}-{yy:02d}-{seq_no}"
