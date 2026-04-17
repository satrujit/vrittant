"""Helpers shared across edition sub-modules."""
from ...models.edition import Edition, EditionPage


PAPER_TYPE_LABELS = {
    "daily": "Daily",
    "weekend": "Weekend",
    "evening": "Evening",
    "special": "Special",
}


def _generate_title(publication_date, paper_type: str) -> str:
    label = PAPER_TYPE_LABELS.get(paper_type, paper_type.capitalize())
    return f"{label} - {publication_date.strftime('%d %b %Y')}"


def _edition_to_response(edition: Edition) -> dict:
    """Convert an Edition ORM object to a dict with computed counts."""
    page_count = len(edition.pages) if edition.pages else 0
    story_count = sum(
        len(p.story_assignments) for p in edition.pages
    ) if edition.pages else 0
    return {
        "id": edition.id,
        "publication_date": edition.publication_date,
        "paper_type": edition.paper_type,
        "title": edition.title,
        "status": edition.status,
        "page_count": page_count,
        "story_count": story_count,
        "created_at": edition.created_at,
        "updated_at": edition.updated_at,
    }


def _page_to_response(page: EditionPage) -> dict:
    """Convert an EditionPage ORM object to a dict with computed counts."""
    story_count = len(page.story_assignments) if page.story_assignments else 0
    return {
        "id": page.id,
        "page_number": page.page_number,
        "page_name": page.page_name,
        "sort_order": page.sort_order,
        "story_count": story_count,
        "story_assignments": page.story_assignments,
    }
