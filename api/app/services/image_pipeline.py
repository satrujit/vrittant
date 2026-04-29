"""Generate web + thumbnail variants alongside the original on upload.

Phone cameras produce 12-24 MP JPEGs (1-4 MB). The reviewer panel and
WordPress only need ~250 KB for display, and list cards only need
~40 KB thumbnails. We keep the original for print-quality archive and
publish two derived sizes:

    orig/<uuid>.jpg     untouched              ~1.3 MB
    web/<uuid>.jpg      ≤2000 px wide, q=85    ~250 KB   (review + WP)
    thumb/<uuid>.jpg    ≤400 px wide,  q=78    ~40 KB    (list cards)

All three URLs are returned and stored on the paragraph as
``media_path`` (orig — primary, also what print uses), ``media_path_web``,
and ``media_path_thumb``. Old clients that only read ``media_path``
keep working with the original.

Failures are non-fatal: if Pillow can't decode (e.g. it's actually a
PDF in disguise) we return only ``orig`` and the panel falls back to
the original everywhere — no upload is rejected.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from .storage import _content_type_for_ext, _get_bucket
from ..config import settings

logger = logging.getLogger(__name__)

# Sizes are caps — Pillow's thumbnail() only shrinks, never enlarges,
# so a 1024px-wide phone shot stays at 1024 in the "web" variant.
WEB_MAX_LONG_EDGE = 2000
THUMB_MAX_LONG_EDGE = 400

# JPEG quality. 85 is the conventional "indistinguishable from
# uncompressed at normal viewing distance" mark; 78 is fine for
# 400px-wide thumbnails where pixel-peeping isn't possible.
WEB_QUALITY = 85
THUMB_QUALITY = 78

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def is_image(filename: str) -> bool:
    return os.path.splitext(filename or "")[1].lower() in _IMAGE_EXTS


def process_image(contents: bytes, original_filename: str) -> dict:
    """Return ``{media_path, media_path_web, media_path_thumb}``.

    ``media_path`` is always set (the original, untouched, for print +
    backwards compat). ``media_path_web`` and ``media_path_thumb`` are
    set only when Pillow can decode the input — non-image bytes uploaded
    with a `.jpg` extension still upload as the original.
    """
    if not contents:
        raise ValueError("Empty image upload")

    ext = os.path.splitext(original_filename or "")[1].lower() or ".jpg"
    base_uuid = uuid.uuid4().hex

    # Always upload the original, even if Pillow chokes — print needs it.
    orig_url = _upload(contents, key=f"orig/{base_uuid}{ext}", ext=ext)

    web_url: Optional[str] = None
    thumb_url: Optional[str] = None
    try:
        img = Image.open(io.BytesIO(contents))
        # EXIF orientation rotates ~80% of phone shots correctly without
        # changing apparent pixel dimensions; do this BEFORE measuring
        # so portrait photos resize to the right aspect.
        img = ImageOps.exif_transpose(img)
        # Convert to RGB — JPEG can't carry alpha, and PNG/HEIC inputs
        # often have one. Pillow's default conversion handles this.
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("image_pipeline: could not decode %s: %s", original_filename, exc)
        return {"media_path": orig_url, "media_path_web": None, "media_path_thumb": None}

    web_bytes = _resize_jpeg(img, WEB_MAX_LONG_EDGE, WEB_QUALITY)
    web_url = _upload(web_bytes, key=f"web/{base_uuid}.jpg", ext=".jpg")

    thumb_bytes = _resize_jpeg(img, THUMB_MAX_LONG_EDGE, THUMB_QUALITY)
    thumb_url = _upload(thumb_bytes, key=f"thumb/{base_uuid}.jpg", ext=".jpg")

    return {
        "media_path": orig_url,
        "media_path_web": web_url,
        "media_path_thumb": thumb_url,
    }


def _resize_jpeg(img: Image.Image, max_long_edge: int, quality: int) -> bytes:
    """Resize ``img`` so its long edge ≤ max_long_edge, then JPEG-encode."""
    out = img.copy()
    out.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    # progressive=True helps for the web-large variant (faster perceived
    # load on slow connections); harmless for the thumbnail.
    out.save(
        buf,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return buf.getvalue()


def _upload(contents: bytes, *, key: str, ext: str) -> str:
    """Write to GCS or local disk; return the public URL.

    Mirrors ``services.storage.save_file`` but takes a pre-built key so
    we can group orig/, web/, thumb/ into stable subfolders. Reusing
    ``save_file`` directly would put everything in the bucket root.
    """
    if settings.STORAGE_BACKEND == "gcs" and settings.GCS_BUCKET:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        blob.upload_from_string(contents, content_type=_content_type_for_ext(ext))
        return f"https://storage.googleapis.com/{settings.GCS_BUCKET}/{key}"

    # Local backend — mirror save_file's shape.
    from .storage import UPLOAD_DIR
    full = os.path.join(UPLOAD_DIR, key)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(contents)
    return f"/uploads/{key}"
