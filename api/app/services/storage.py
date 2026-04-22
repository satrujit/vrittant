"""Unified file storage — local filesystem or Google Cloud Storage."""

import logging
import os
import uuid

from ..config import settings

logger = logging.getLogger(__name__)

# ── Local paths ──────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Loud warning if the deploy env asked for GCS but didn't supply a bucket.
# Without this the code silently fell back to the local filesystem branch
# and wrote to Cloud Run's ephemeral disk — uploaded photos then appeared
# "corrupted" once the container recycled. We don't crash because dev /
# tests deliberately run with STORAGE_BACKEND=local; we just make the
# misconfiguration impossible to miss in Cloud Run logs.
_GCS_MISCONFIGURED = settings.STORAGE_BACKEND == "gcs" and not settings.GCS_BUCKET
if _GCS_MISCONFIGURED:
    logger.critical(
        "STORAGE_BACKEND=gcs but GCS_BUCKET is empty — uploads will be "
        "written to ephemeral local disk and disappear when the container "
        "recycles. Set the GCS_BUCKET env var/secret and redeploy."
    )

# ── GCS client (lazy) ───────────────────────────────────────────────────────
_gcs_client = None
_gcs_bucket = None


def _get_bucket():
    global _gcs_client, _gcs_bucket
    if _gcs_bucket is None:
        from google.cloud import storage as gcs
        _gcs_client = gcs.Client()
        _gcs_bucket = _gcs_client.bucket(settings.GCS_BUCKET)
    return _gcs_bucket


def _media_type_from_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "bmp", "svg"):
        return "photo"
    if ext in ("mp4", "mov", "avi", "mkv", "webm", "m4v"):
        return "video"
    if ext in ("mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"):
        return "audio"
    return "document"


def save_file(contents: bytes, original_filename: str, subfolder: str = "") -> str:
    """Save file and return its public URL path.

    Returns:
        For local: ``/uploads/subfolder/filename``
        For GCS:   ``https://storage.googleapis.com/BUCKET/subfolder/filename``
    """
    ext = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"

    if subfolder:
        key = f"{subfolder}/{unique_name}"
    else:
        key = unique_name

    if settings.STORAGE_BACKEND == "gcs" and settings.GCS_BUCKET:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        content_type = _content_type_for_ext(ext)
        blob.upload_from_string(contents, content_type=content_type)
        return f"https://storage.googleapis.com/{settings.GCS_BUCKET}/{key}"
    else:
        dest_dir = os.path.join(UPLOAD_DIR, subfolder) if subfolder else UPLOAD_DIR
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, unique_name), "wb") as f:
            f.write(contents)
        return f"/uploads/{key}"


def save_logo(contents: bytes, slug: str, ext: str) -> str:
    """Save an org logo. Returns the public URL path."""
    filename = f"{slug}{ext}"
    key = f"org-logos/{filename}"

    if settings.STORAGE_BACKEND == "gcs" and settings.GCS_BUCKET:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        content_type = _content_type_for_ext(ext)
        blob.upload_from_string(contents, content_type=content_type)
        return f"https://storage.googleapis.com/{settings.GCS_BUCKET}/{key}"
    else:
        dest_dir = os.path.join(UPLOAD_DIR, "org-logos")
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, filename), "wb") as f:
            f.write(contents)
        return f"/uploads/org-logos/{filename}"


def delete_file(public_url: str) -> bool:
    """Best-effort delete by the public URL ``save_file`` returned.

    Returns True on success or "already gone"; False on a real error so
    callers can decide whether to log loudly. Never raises — used in
    fire-and-forget cleanup paths.
    """
    if not public_url:
        return True
    try:
        if public_url.startswith("https://storage.googleapis.com/"):
            # Strip the bucket prefix to get the GCS object key
            prefix = f"https://storage.googleapis.com/{settings.GCS_BUCKET}/"
            if not public_url.startswith(prefix):
                logger.warning("delete_file: URL %s not in expected bucket %s",
                               public_url, settings.GCS_BUCKET)
                return False
            key = public_url[len(prefix):]
            bucket = _get_bucket()
            bucket.blob(key).delete()
            return True
        if public_url.startswith("/uploads/"):
            rel = public_url[len("/uploads/"):]
            path = os.path.join(UPLOAD_DIR, rel)
            if os.path.exists(path):
                os.remove(path)
            return True
        # Unknown URL shape — nothing safe to do.
        logger.warning("delete_file: unrecognized URL shape %s", public_url)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_file failed for %s: %s", public_url, exc)
        return False


def _content_type_for_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    mapping = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
        "mp4": "video/mp4", "mp3": "audio/mpeg", "wav": "audio/wav",
        "pdf": "application/pdf",
    }
    return mapping.get(ext, "application/octet-stream")
