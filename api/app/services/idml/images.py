"""Image download helpers and image-frame XML builder."""

import base64
import io
import logging

import httpx

logger = logging.getLogger(__name__)


async def _download_image(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", url, exc)
        return None


def _guess_ext(url: str) -> str:
    lower = url.lower()
    for ext in (".png", ".gif", ".webp"):
        if ext in lower:
            return ext.lstrip(".")
    return "jpg"


def _read_image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return (width_px, height_px) using Pillow; None on failure."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        logger.warning("Pillow not installed; cannot read image dimensions")
        return None
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            return int(im.width), int(im.height)
    except Exception as exc:
        logger.warning("Failed to read image dimensions: %s", exc)
        return None


def _image_frame_xml(frame_id: str, cx: float, cy: float,
                     hw: float, hh: float,
                     image_bytes: bytes | None = None,
                     link_name: str | None = None) -> str:
    """Build a Rectangle (image frame) XML element for the spread.

    If ``image_bytes`` is provided, the image is EMBEDDED inside the
    Rectangle as a base64 ``<Contents>`` element so InDesign does not
    need an external file to resolve the link. If absent, the frame is
    emitted with ``ContentType="Unassigned"``.
    """
    has_image = bool(image_bytes)
    content_type = "GraphicType" if has_image else "Unassigned"
    image_xml = ""

    if has_image:
        dims = _read_image_dimensions(image_bytes)
        if dims is None:
            # Fall back: drop the image rather than emit a broken frame.
            content_type = "Unassigned"
        else:
            w_px, h_px = dims
            frame_w_pt = hw * 2
            frame_h_pt = hh * 2
            scale_x = frame_w_pt / w_px if w_px else 1.0
            scale_y = frame_h_pt / h_px if h_px else 1.0
            # Inner Image is positioned in the Rectangle's local coord space
            # (center-based). Scale intrinsic px -> frame pt and translate so
            # the image's top-left maps to the frame's top-left (-hw, -hh).
            tx = -hw
            ty = -hh
            b64 = base64.b64encode(image_bytes).decode("ascii")
            img_id = f"u_img_{frame_id}"
            link_id = f"u_link_{frame_id}"
            link_uri = link_name or f"{frame_id}.embed"
            image_xml = (
                f'\n\t\t\t<Image Self="{img_id}" '
                f'ItemTransform="{scale_x} 0 0 {scale_y} {tx} {ty}" '
                f'Visible="true" Name="$ID/" ItemLayer="uce" Locked="false" '
                f'LocalDisplaySetting="Default" '
                f'AppliedObjectStyle="ObjectStyle/$ID/[None]" '
                f'ImageTypeName="$ID/Photoshop image" '
                f'ImageRenderingIntent="UseColorSettings" '
                f'GradientFillStart="0 0" GradientFillLength="0" '
                f'GradientFillAngle="0" GradientStrokeStart="0 0" '
                f'GradientStrokeLength="0" GradientStrokeAngle="0">\n'
                f"\t\t\t\t<Properties>\n"
                f'\t\t\t\t\t<Profile type="string">$ID/Embedded</Profile>\n'
                f'\t\t\t\t\t<GraphicBounds Left="0" Top="0" '
                f'Right="{w_px}" Bottom="{h_px}" />\n'
                f"\t\t\t\t</Properties>\n"
                f'\t\t\t\t<Link Self="{link_id}" '
                f'LinkResourceURI="{link_uri}" StoredState="Embedded" '
                f'LinkClassID="35906" CanEmbed="true" CanUnembed="false" '
                f'CanPackage="false" ImportPolicy="NoAutoImport" />\n'
                f"\t\t\t\t<Contents>{b64}</Contents>\n"
                f"\t\t\t</Image>"
            )

    return f"""\
\t\t<Rectangle Self="{frame_id}" ContentType="{content_type}" OverriddenPageItemProps="" Visible="true" Name="$ID/" ItemLayer="uce" Locked="false" LocalDisplaySetting="Default" AppliedObjectStyle="ObjectStyle/$ID/[Normal Graphics Frame]" ItemTransform="1 0 0 1 {cx} {cy}" StrokeWeight="0" GradientFillStart="0 0" GradientFillLength="0" GradientFillAngle="0" GradientStrokeStart="0 0" GradientStrokeLength="0" GradientStrokeAngle="0">
\t\t\t<Properties>
\t\t\t\t<PathGeometry>
\t\t\t\t\t<GeometryPathType PathOpen="false">
\t\t\t\t\t\t<PathPointArray>
\t\t\t\t\t\t\t<PathPointType Anchor="{-hw} {-hh}" LeftDirection="{-hw} {-hh}" RightDirection="{-hw} {-hh}" />
\t\t\t\t\t\t\t<PathPointType Anchor="{-hw} {hh}" LeftDirection="{-hw} {hh}" RightDirection="{-hw} {hh}" />
\t\t\t\t\t\t\t<PathPointType Anchor="{hw} {hh}" LeftDirection="{hw} {hh}" RightDirection="{hw} {hh}" />
\t\t\t\t\t\t\t<PathPointType Anchor="{hw} {-hh}" LeftDirection="{hw} {-hh}" RightDirection="{hw} {-hh}" />
\t\t\t\t\t\t</PathPointArray>
\t\t\t\t\t</GeometryPathType>
\t\t\t\t</PathGeometry>
\t\t\t</Properties>{image_xml}
\t\t</Rectangle>"""
