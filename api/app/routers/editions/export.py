"""Edition export endpoint: build a ZIP bundle of all stories + IDML."""
import io
import logging
import re
import zipfile

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import require_reviewer, get_current_org_id
from ...models.edition import Edition, EditionPage
from ...models.story import Story
from ...models.user import User
from ...services.idml import generate_idml
from . import router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /admin/editions/{edition_id}/export-zip
# Download all stories + IDML as a zip bundle for the edition
# ---------------------------------------------------------------------------

def _safe_filename(text: str, max_len: int = 50) -> str:
    """Strip filesystem-unsafe chars from a filename."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text or '')
    return cleaned.strip()[:max_len] or 'untitled'


@router.get("/{edition_id}/export-zip")
async def export_edition_zip(
    edition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    """Export the entire edition as a ZIP containing per-page folders,
    each with story text files and IDML layout files."""

    edition = (
        db.query(Edition)
        .options(
            joinedload(Edition.pages)
            .joinedload(EditionPage.story_assignments)
        )
        .filter(Edition.id == edition_id, Edition.organization_id == org_id)
        .first()
    )
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    # Gather all story IDs across pages
    all_story_ids = set()
    for page in edition.pages:
        for sa in page.story_assignments:
            all_story_ids.add(sa.story_id)

    if not all_story_ids:
        raise HTTPException(
            status_code=400,
            detail="No stories assigned to this edition",
        )

    # Bulk-load stories with revisions and reporters.
    # Defense-in-depth: scope to org_id even though the assign endpoints now
    # enforce this on write — protects against any pre-existing cross-org rows.
    stories = (
        db.query(Story)
        .options(joinedload(Story.revision), joinedload(Story.reporter))
        .filter(Story.id.in_(all_story_ids), Story.organization_id == org_id)
        .all()
    )
    story_map = {s.id: s for s in stories}

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page in sorted(edition.pages, key=lambda p: p.sort_order):
            page_name = page.page_name or f"Page {page.page_number}"
            folder = f"Page_{page.page_number:02d}_{_safe_filename(page_name)}"

            assignments = sorted(
                page.story_assignments, key=lambda a: a.sort_order
            )
            for idx, sa in enumerate(assignments, 1):
                story = story_map.get(sa.story_id)
                if not story:
                    continue

                # Use revision (edited) content if available
                rev = story.revision
                headline = (
                    (rev.headline if rev and rev.headline else story.headline)
                    or "Untitled"
                )
                paragraphs = (
                    (rev.paragraphs if rev and rev.paragraphs else story.paragraphs)
                    or []
                )
                reporter_name = (
                    story.reporter.name if story.reporter else "Unknown"
                )

                safe_headline = _safe_filename(headline, 40)
                base_name = f"{idx:02d}_{safe_headline}"

                # -- Story text file --
                body_parts = []
                for p in paragraphs:
                    if p.get("type") == "text" and p.get("text"):
                        body_parts.append(p["text"])
                body_text = "\n\n".join(body_parts)

                txt_content = (
                    f"Headline: {headline}\n"
                    f"Category: {story.category or ''}\n"
                    f"Location: {story.location or ''}\n"
                    f"Reporter: {reporter_name}\n"
                    f"Priority: {story.priority or 'normal'}\n"
                    f"{'=' * 60}\n\n"
                    f"{body_text}\n"
                )
                zf.writestr(
                    f"{folder}/{base_name}.txt",
                    txt_content.encode("utf-8"),
                )

                # -- IDML layout file --
                try:
                    story_data = {
                        "headline": headline,
                        "paragraphs": paragraphs,
                        "category": story.category or "",
                        "priority": story.priority or "normal",
                        "reporter": {"name": reporter_name},
                        "location": story.location or "",
                    }
                    idml_bytes = await generate_idml(story_data)
                    zf.writestr(f"{folder}/{base_name}.idml", idml_bytes)
                except Exception as exc:
                    logger.error(
                        "IDML generation failed for story %s: %s",
                        story.id, exc,
                    )
                    zf.writestr(
                        f"{folder}/{base_name}_IDML_ERROR.txt",
                        f"IDML generation failed: {str(exc)}\n",
                    )

    buf.seek(0)
    zip_bytes = buf.getvalue()

    # Build filename
    date_str = edition.publication_date.strftime("%Y-%m-%d") if edition.publication_date else "edition"
    zip_filename = f"{_safe_filename(edition.title or date_str)}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
