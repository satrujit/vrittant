"""
Firebase Admin SDK initialization.
Uses Application Default Credentials when available (production),
falls back to project-ID-only init for ID token verification (development).
"""
import firebase_admin
from firebase_admin import auth as firebase_auth

from .config import settings


def init_firebase():
    """Initialize Firebase Admin SDK. Safe to call multiple times."""
    if firebase_admin._apps:
        return  # already initialized

    try:
        # Try ADC (works on GCP / with GOOGLE_APPLICATION_CREDENTIALS env var)
        cred = firebase_admin.credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            "projectId": settings.FIREBASE_PROJECT_ID,
        })
    except Exception:
        # Fallback: initialize with just project ID (sufficient for verify_id_token)
        firebase_admin.initialize_app(options={
            "projectId": settings.FIREBASE_PROJECT_ID,
        })


def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.
    Raises firebase_admin.auth.InvalidIdTokenError on failure.
    """
    return firebase_auth.verify_id_token(id_token)
