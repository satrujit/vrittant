from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.user import User
from ..models.story import Story
from ..schemas.story import StoryCreate, StoryResponse, StoryUpdate

router = APIRouter()

@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def create_story(
    body: StoryCreate,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    story = Story(
        reporter_id=user.id,
        organization_id=org_id,
        headline=body.headline,
        category=body.category,
        location=body.location,
        paragraphs=[p.model_dump() for p in body.paragraphs],
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story

@router.get("", response_model=list[StoryResponse])
def list_stories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: draft, submitted, approved, published, rejected"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search in headline text"),
    date_from: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
):
    query = db.query(Story).filter(Story.reporter_id == user.id, Story.organization_id == org_id)

    if status_filter:
        query = query.filter(Story.status == status_filter)
    if category:
        query = query.filter(Story.category == category)
    if search:
        query = query.filter(Story.headline.ilike(f"%{search}%"))
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Story.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Story.created_at <= dt)
        except ValueError:
            pass

    stories = (
        query
        .order_by(Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return stories

@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: str,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == user.id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return story

@router.put("/{story_id}", response_model=StoryResponse)
def update_story(
    story_id: str,
    body: StoryUpdate,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == user.id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    if body.headline is not None:
        story.headline = body.headline
    if body.category is not None:
        story.category = body.category
    if body.location is not None:
        story.location = body.location
    if body.paragraphs is not None:
        story.paragraphs = [p.model_dump() for p in body.paragraphs]

    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story

@router.post("/{story_id}/submit", response_model=StoryResponse)
def submit_story(
    story_id: str,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == user.id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if story.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be submitted")

    story.status = "submitted"
    story.submitted_at = datetime.now(timezone.utc)
    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story

@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(
    story_id: str,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == user.id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if story.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be deleted")

    db.delete(story)
    db.commit()
