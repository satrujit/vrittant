"""Layout computation, spread assembly, and IDML zip packaging — orchestrator."""

import io
import re
import zipfile

from ._constants import (
    COL_GAP_PT,
    CONTENT_H,
    CONTENT_W,
    MARGIN_PT,
    PAGE_H_PT,
    PAGE_W_PT,
)
from .header import (
    BACKING_STORY_XML,
    CONTAINER_XML,
    FONTS_XML,
    GRAPHIC_XML,
    MIMETYPE,
    STYLES_XML,
    TAGS_XML,
    _designmap_xml,
    _master_spread_xml,
    _metadata_xml,
    _preferences_xml,
)
from .images import _download_image, _guess_ext, _image_frame_xml
from .paragraphs import _story_xml, _text_frame_xml


# ---------------------------------------------------------------------------
# Frame position helpers (center-based coordinate system)
# ---------------------------------------------------------------------------

def _frame_coords(page_x: float, page_y: float, w: float, h: float,
                  ph: float = PAGE_H_PT) -> tuple[float, float, float, float]:
    """Convert page coords (top-left origin) to IDML center-based coords.

    Returns (center_x, center_y, half_w, half_h) for ItemTransform and PathGeometry.
    In IDML spread coords, the page is shifted up by half its height.
    """
    center_x = page_x + w / 2
    center_y = page_y + h / 2 - ph / 2
    return center_x, center_y, w / 2, h / 2


# ---------------------------------------------------------------------------
# Spread builder
# ---------------------------------------------------------------------------

def _spread_xml(frames_xml: str, pw: float = PAGE_W_PT, ph: float = PAGE_H_PT) -> str:
    half_ph = ph / 2
    content_w = pw - 2 * MARGIN_PT

    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<Spread Self="ud1" PageTransitionType="None" PageTransitionDirection="NotApplicable" PageTransitionDuration="Medium" ShowMasterItems="true" PageCount="1" BindingLocation="0" SpreadHidden="false" AllowPageShuffle="true" ItemTransform="1 0 0 1 0 0" FlattenerOverride="Default">
\t\t<FlattenerPreference LineArtAndTextResolution="300" GradientAndMeshResolution="150" ClipComplexRegions="false" ConvertAllStrokesToOutlines="false" ConvertAllTextToOutlines="false">
\t\t\t<Properties>
\t\t\t\t<RasterVectorBalance type="double">50</RasterVectorBalance>
\t\t\t</Properties>
\t\t</FlattenerPreference>
\t\t<Page Self="ud6" TabOrder="" AppliedMaster="ud8" OverrideList="" MasterPageTransform="1 0 0 1 0 0" Name="1" AppliedTrapPreset="TrapPreset/$ID/kDefaultTrapStyleName" GeometricBounds="0 0 {ph} {pw}" ItemTransform="1 0 0 1 0 {-half_ph}" AppliedAlternateLayout="ud7" LayoutRule="UseMaster" SnapshotBlendingMode="IgnoreLayoutSnapshots" OptionalPage="false" GridStartingPoint="TopOutside" UseMasterGrid="true">
\t\t\t<Properties>
\t\t\t\t<PageColor type="enumeration">UseMasterColor</PageColor>
\t\t\t</Properties>
\t\t\t<MarginPreference ColumnCount="1" ColumnGutter="12" Top="36" Bottom="36" Left="36" Right="36" ColumnDirection="Horizontal" ColumnsPositions="0 {content_w}" />
\t\t</Page>
{frames_xml}
\t</Spread>
</idPkg:Spread>"""


# ---------------------------------------------------------------------------
# Layout computation
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text or "")


def _compute_layout(story: dict) -> dict:
    """Compute frame positions and story content from article data.

    Returns a dict with:
        stories: {story_id: [paragraph_dicts]}
        frames: [(frame_id, story_id|None, page_x, page_y, w, h, cols, v_just, is_image, link_name)]
        image_urls: [url]
    """
    headline = _strip_html(story.get("headline", "Untitled"))
    paragraphs = story.get("paragraphs", [])
    reporter_name = (story.get("reporter") or {}).get("name", "")
    location = story.get("location", "")
    priority = (story.get("priority", "normal") or "normal").lower()

    # Separate body text and images
    body_texts = []
    image_urls = []
    for p in paragraphs:
        if isinstance(p, dict):
            pt = p.get("type", "paragraph")
            txt = _strip_html(p.get("text", ""))
            img = p.get("image_url", "")
            if pt == "image" or (img and not txt):
                if img:
                    image_urls.append(img)
                continue
            if txt:
                body_texts.append(txt)
        elif isinstance(p, str):
            txt = _strip_html(p)
            if txt:
                body_texts.append(txt)

    body_text = "\n".join(body_texts)
    byline = " | ".join(filter(None, [reporter_name, location]))

    # Layout parameters
    x = MARGIN_PT
    y = MARGIN_PT
    w = CONTENT_W
    gap = 12.0
    frames = []
    stories = {}
    id_counter = [0]

    def next_id():
        id_counter[0] += 1
        return f"u{200 + id_counter[0]}"

    # --- Headline ---
    headline_pt = 48 if priority in ("breaking", "urgent", "high") else 36
    h_lines = max(1, len(headline) // 25 + 1)
    h_height = max(48, h_lines * headline_pt * 1.4)
    sid = next_id()
    fid = next_id()
    stories[sid] = [{"text": headline, "point_size": headline_pt,
                     "justification": "CenterAlign",
                     "fill_color": "Color/C=15 M=100 Y=100 K=0",
                     "font_style": "Bold"}]
    frames.append((fid, sid, x, y, w, h_height, 1, "CenterAlign", False, None))
    y += h_height + gap

    # --- Byline / sub-header ---
    if byline:
        sid = next_id()
        fid = next_id()
        byline_h = 30
        stories[sid] = [{"text": byline, "point_size": 14,
                         "justification": "CenterAlign",
                         "fill_color": "Color/C=100 M=90 Y=10 K=0",
                         "font_style": "Regular"}]
        frames.append((fid, sid, x, y, w, byline_h, 1, "CenterAlign", False, None))
        y += byline_h + gap

    # --- Image (first image, if any) ---
    if image_urls:
        fid = next_id()
        img_h = min(200, CONTENT_H * 0.3)
        frames.append((fid, None, x, y, w, img_h, 1, "TopAlign", True, None))
        y += img_h + gap

    # --- Body text ---
    remaining_h = PAGE_H_PT - MARGIN_PT - y
    if remaining_h < 100:
        remaining_h = 300  # extend page if needed

    total_chars = len(body_text)
    use_two_cols = total_chars > 800

    if use_two_cols:
        col_w = (w - COL_GAP_PT) / 2
        # Left column
        sid_left = next_id()
        fid_left = next_id()
        # Right column
        sid_right = next_id()
        fid_right = next_id()

        # Split body text roughly in half by paragraphs
        mid = len(body_texts) // 2 or 1
        left_text = "\n".join(body_texts[:mid])
        right_text = "\n".join(body_texts[mid:])

        stories[sid_left] = [{"text": left_text, "point_size": 11,
                              "justification": "LeftAlign",
                              "fill_color": "Color/Black",
                              "font_style": "Regular"}]
        stories[sid_right] = [{"text": right_text, "point_size": 11,
                               "justification": "LeftAlign",
                               "fill_color": "Color/Black",
                               "font_style": "Regular"}]

        frames.append((fid_left, sid_left, x, y, col_w, remaining_h, 1, "TopAlign", False, None))
        frames.append((fid_right, sid_right, x + col_w + COL_GAP_PT, y, col_w, remaining_h, 1, "TopAlign", False, None))
    else:
        sid = next_id()
        fid = next_id()
        stories[sid] = [{"text": body_text, "point_size": 11,
                         "justification": "LeftAlign",
                         "fill_color": "Color/Black",
                         "font_style": "Regular"}]
        frames.append((fid, sid, x, y, w, remaining_h, 1, "TopAlign", False, None))

    return {
        "stories": stories,
        "frames": frames,
        "image_urls": image_urls,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_idml(story: dict) -> bytes:
    """Generate a valid IDML package from story content.

    Produces InDesign 2025-compatible IDML (DOMVersion 21.2) with
    proper structure matching a real InDesign export.
    """
    layout = _compute_layout(story)
    stories = layout["stories"]
    frames = layout["frames"]
    image_urls = layout["image_urls"]

    # Download images
    image_data: dict[str, bytes] = {}
    image_links: dict[str, str] = {}
    for i, url in enumerate(image_urls):
        ext = _guess_ext(url)
        fname = f"image_{i + 1}.{ext}"
        data = await _download_image(url)
        if data:
            image_data[fname] = data
            # Find the image frame and assign the link
            for j, f in enumerate(frames):
                if f[8] and f[9] is None:  # is_image and no link yet
                    frames[j] = (*f[:9], fname)
                    break
            image_links[fname] = url

    # Build story IDs list
    story_ids = list(stories.keys())

    # Build story XML files
    story_xmls = {}
    for sid, paras in stories.items():
        story_xmls[sid] = _story_xml(sid, paras)

    # Build spread XML with all frames
    frames_xml_parts = []
    for fid, sid, px, py, fw, fh, cols, vjust, is_image, link_name in frames:
        cx, cy, hw, hh = _frame_coords(px, py, fw, fh)
        if is_image:
            frames_xml_parts.append(_image_frame_xml(fid, cx, cy, hw, hh, link_name))
        else:
            frames_xml_parts.append(_text_frame_xml(fid, sid, cx, cy, hw, hh, cols, vjust))

    spread = _spread_xml("\n".join(frames_xml_parts))

    # Assemble IDML ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype must be first entry, stored uncompressed
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, MIMETYPE)

        # META-INF
        zf.writestr("META-INF/container.xml", CONTAINER_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("META-INF/metadata.xml", _metadata_xml(), zipfile.ZIP_DEFLATED)

        # designmap
        zf.writestr("designmap.xml", _designmap_xml(story_ids), zipfile.ZIP_DEFLATED)

        # Resources
        zf.writestr("Resources/Graphic.xml", GRAPHIC_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("Resources/Fonts.xml", FONTS_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("Resources/Styles.xml", STYLES_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("Resources/Preferences.xml", _preferences_xml(), zipfile.ZIP_DEFLATED)

        # XML structure
        zf.writestr("XML/Tags.xml", TAGS_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("XML/BackingStory.xml", BACKING_STORY_XML, zipfile.ZIP_DEFLATED)

        # MasterSpread
        zf.writestr("MasterSpreads/MasterSpread_ud8.xml", _master_spread_xml(), zipfile.ZIP_DEFLATED)

        # Spread
        zf.writestr("Spreads/Spread_ud1.xml", spread, zipfile.ZIP_DEFLATED)

        # Stories
        for sid, xml in story_xmls.items():
            zf.writestr(f"Stories/Story_{sid}.xml", xml, zipfile.ZIP_DEFLATED)

        # Linked images
        for fname, data in image_data.items():
            zf.writestr(f"Links/{fname}", data, zipfile.ZIP_DEFLATED)

    return buf.getvalue()
