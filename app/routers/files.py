"""File upload / list endpoints for Vrittant reporter attachments."""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.user import User
from ..models.story import Story

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mp3', '.wav', '.pdf'}

# ── Upload directory ──────────────────────────────────────────────────────────

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _media_type_from_ext(ext: str) -> str:
    """Map file extension to media type category."""
    ext = ext.lower().lstrip(".")
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "bmp", "svg"):
        return "photo"
    if ext in ("mp4", "mov", "avi", "mkv", "webm", "m4v"):
        return "video"
    if ext in ("mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"):
        return "audio"
    return "document"


# ── Upload a file ─────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload a file and return its server URL."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    file_size = len(contents)

    with open(file_path, "wb") as f:
        f.write(contents)

    media_type = _media_type_from_ext(ext)
    url = f"/uploads/{unique_name}"

    return {
        "url": url,
        "filename": file.filename,
        "media_type": media_type,
        "size": file_size,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


# ── List all files across stories ─────────────────────────────────────────────

@router.get("")
def list_files(
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Return all media files across all stories for this reporter."""
    stories = db.query(Story).filter(Story.reporter_id == user.id, Story.organization_id == org_id).all()

    files = []
    for story in stories:
        for para in (story.paragraphs or []):
            media_path = para.get("media_path") or para.get("photo_path")
            if not media_path:
                continue

            media_type = para.get("media_type", "photo")
            media_name = para.get("media_name") or "Untitled"
            created_at = para.get("created_at")

            # Calculate file size if file is on disk
            size = 0
            if media_path.startswith("/uploads/"):
                disk_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    media_path.lstrip("/"),
                )
                if os.path.exists(disk_path):
                    size = os.path.getsize(disk_path)

            files.append({
                "url": media_path,
                "filename": media_name,
                "media_type": media_type,
                "size": size,
                "story_id": story.id,
                "story_headline": story.headline,
                "created_at": created_at or (story.created_at.isoformat() if story.created_at else None),
            })

    return files
