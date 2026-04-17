"""Image download helpers and image-frame XML builder."""

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


def _image_frame_xml(frame_id: str, cx: float, cy: float,
                     hw: float, hh: float,
                     link_name: str | None = None) -> str:
    """Build a Rectangle (image frame) XML element for the spread."""
    content_type = "GraphicType" if link_name else "Unassigned"
    image_xml = ""
    if link_name:
        img_id = f"u_img_{frame_id}"
        link_id = f"u_link_{frame_id}"
        image_xml = f"""
\t\t\t<Image Self="{img_id}" ItemTransform="1 0 0 1 0 0">
\t\t\t\t<Link Self="{link_id}" LinkResourceURI="Links/{link_name}" StoredState="Normal" LinkClassID="35906" />
\t\t\t</Image>"""

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
