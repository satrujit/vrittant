"""Speaker enrollment sync endpoints.

Enrollment embeddings are extracted on-device (Flutter app) using the
CAM++ model via sherpa-onnx.  These endpoints simply store / retrieve
the embedding so it survives app reinstall or device migration.

No ML processing happens on the backend.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.voice_enrollment import VoiceEnrollment

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class EnrollmentUpsertRequest(BaseModel):
    embedding: list[float] = Field(
        ..., min_length=64, max_length=1024,
        description="Speaker embedding vector from CAM++ model",
    )
    sample_count: int = Field(
        ..., ge=1, le=10,
        description="Number of enrollment samples averaged",
    )


class EnrollmentResponse(BaseModel):
    embedding: list[float]
    sample_count: int
    is_active: bool
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.put("/api/speaker/enrollment", response_model=EnrollmentResponse)
def upsert_enrollment(
    body: EnrollmentUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the speaker enrollment for the authenticated user."""
    enrollment = (
        db.query(VoiceEnrollment)
        .filter(VoiceEnrollment.user_id == user.id)
        .first()
    )

    embedding_json = json.dumps(body.embedding)

    if enrollment is None:
        enrollment = VoiceEnrollment(
            user_id=user.id,
            embedding=embedding_json,
            sample_count=body.sample_count,
        )
        db.add(enrollment)
    else:
        enrollment.embedding = embedding_json
        enrollment.sample_count = body.sample_count

    db.commit()
    db.refresh(enrollment)
    logger.info(f"Speaker enrollment synced for user {user.id} ({body.sample_count} samples)")

    return _to_response(enrollment)


@router.get("/api/speaker/enrollment", response_model=EnrollmentResponse)
def get_enrollment(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the stored speaker enrollment for the authenticated user."""
    enrollment = (
        db.query(VoiceEnrollment)
        .filter(VoiceEnrollment.user_id == user.id)
        .first()
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No voice enrollment found",
        )
    return _to_response(enrollment)


@router.delete("/api/speaker/enrollment", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the speaker enrollment for the authenticated user."""
    enrollment = (
        db.query(VoiceEnrollment)
        .filter(VoiceEnrollment.user_id == user.id)
        .first()
    )
    if enrollment is not None:
        db.delete(enrollment)
        db.commit()
        logger.info(f"Speaker enrollment deleted for user {user.id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(enrollment: VoiceEnrollment) -> EnrollmentResponse:
    return EnrollmentResponse(
        embedding=json.loads(enrollment.embedding),
        sample_count=enrollment.sample_count,
        is_active=enrollment.is_active,
        created_at=enrollment.created_at.isoformat() if enrollment.created_at else "",
        updated_at=enrollment.updated_at.isoformat() if enrollment.updated_at else "",
    )
