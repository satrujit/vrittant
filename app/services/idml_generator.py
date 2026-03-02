"""IDML generator: builds a valid InDesign IDML package from story content.

Generates a clean, professional single-article layout automatically.
No zone configuration needed — derives layout from story content directly.
"""

import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

MM_TO_PT = 2.8346
_IDPKG_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
_DOM_VERSION = "7.5"

# Page dimensions (tabloid-ish, good for single articles)
PAGE_W_MM = 280
PAGE_H_MM = 430
MARGIN_MM = 15


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _hex_to_cmyk(hex_color: str) -> tuple[float, float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0.0, 0.0, 0.0, 1.0)
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 1.0)
    c = (1.0 - r - k) / (1.0 - k)
    m = (1.0 - g - k) / (1.0 - k)
    y = (1.0 - b - k) / (1.0 - k)
    return (round(c, 4), round(m, 4), round(y, 4), round(k, 4))


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _xml_str(root: ET.Element) -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
        root, encoding="unicode", xml_declaration=False
    )


def _add_path(parent: ET.Element, w_pt: float, h_pt: float):
    props = ET.SubElement(parent, "Properties")
    pg = ET.SubElement(props, "PathGeometry")
    gpc = ET.SubElement(pg, "GeometryPathType", PathOpen="false")
    ppa = ET.SubElement(gpc, "PathPointArray")
    for cx, cy in [(0, 0), (w_pt, 0), (w_pt, h_pt), (0, h_pt)]:
        ET.SubElement(ppa, "PathPointType", {
            "Anchor": f"{cx:.4f} {cy:.4f}",
            "LeftDirection": f"{cx:.4f} {cy:.4f}",
            "RightDirection": f"{cx:.4f} {cy:.4f}",
        })


# ---------------------------------------------------------------------------
# IDML structure builders
# ---------------------------------------------------------------------------

def _designmap(story_ids: list[str], pw: float, ph: float) -> str:
    root = ET.Element("Document", {
        "DOMVersion": _DOM_VERSION, "Self": "d",
        "xmlns:idPkg": _IDPKG_NS,
        "StoryList": " ".join(f"u_{s}" for s in story_ids),
    })
    ET.SubElement(root, "DocumentPreference", {
        "PageWidth": f"{pw:.4f}", "PageHeight": f"{ph:.4f}",
        "PagesPerDocument": "1", "FacingPages": "false",
    })
    ET.SubElement(root, "idPkg:Graphic", src="Resources/Graphic.xml")
    ET.SubElement(root, "idPkg:Fonts", src="Resources/Fonts.xml")
    ET.SubElement(root, "idPkg:Styles", src="Resources/Styles.xml")
    ET.SubElement(root, "idPkg:Preferences", src="Resources/Preferences.xml")
    ET.SubElement(root, "idPkg:Spread", src="Spreads/Spread_1.xml")
    for s in story_ids:
        ET.SubElement(root, "idPkg:Story", src=f"Stories/Story_{s}.xml")
    return _xml_str(root)


def _styles() -> str:
    root = ET.Element("idPkg:Styles", {"xmlns:idPkg": _IDPKG_NS, "DOMVersion": _DOM_VERSION})
    rpsg = ET.SubElement(root, "RootParagraphStyleGroup", Self="u_rps")
    ET.SubElement(rpsg, "ParagraphStyle", {
        "Self": "ParagraphStyle/$ID/NormalParagraphStyle",
        "Name": "$ID/NormalParagraphStyle",
    })
    for name, attrs in {
        "Headline": {"FontStyle": "Bold", "PointSize": "36", "Justification": "LeftAlign"},
        "Subheader": {"FontStyle": "Regular", "PointSize": "16", "Justification": "LeftAlign"},
        "Byline": {"FontStyle": "Regular", "PointSize": "9", "Justification": "LeftAlign"},
        "BodyText": {"FontStyle": "Regular", "PointSize": "10", "Justification": "LeftJustified"},
        "BulletText": {"FontStyle": "Regular", "PointSize": "10", "LeftIndent": "14", "FirstLineIndent": "-14"},
        "Pullquote": {"FontStyle": "Italic", "PointSize": "14", "Justification": "CenterAlign"},
    }.items():
        el = ET.SubElement(rpsg, "ParagraphStyle", {"Self": f"ParagraphStyle/{name}", "Name": name})
        props = ET.SubElement(el, "Properties")
        for k, v in attrs.items():
            sub = ET.SubElement(props, k)
            sub.text = v

    rcsg = ET.SubElement(root, "RootCharacterStyleGroup", Self="u_rcs")
    ET.SubElement(rcsg, "CharacterStyle", {
        "Self": "CharacterStyle/$ID/[No character style]",
        "Name": "$ID/[No character style]",
    })
    rosg = ET.SubElement(root, "RootObjectStyleGroup", Self="u_ros")
    ET.SubElement(rosg, "ObjectStyle", {"Self": "ObjectStyle/$ID/[None]", "Name": "$ID/[None]"})
    return _xml_str(root)


def _graphic() -> str:
    root = ET.Element("idPkg:Graphic", {"xmlns:idPkg": _IDPKG_NS, "DOMVersion": _DOM_VERSION})
    for name, vals in {"Black": "0 0 0 100", "Paper": "0 0 0 0"}.items():
        ET.SubElement(root, "Color", {"Self": f"Color/{name}", "Name": name,
                                       "Model": "Process", "Space": "CMYK", "ColorValue": vals})
    return _xml_str(root)


def _story_xml(story_id: str, style: str, text: str, font_size: float = 10, paragraphs_meta=None) -> str:
    root = ET.Element("idPkg:Story", {"xmlns:idPkg": _IDPKG_NS, "DOMVersion": _DOM_VERSION})
    story_el = ET.SubElement(root, "Story", {
        "Self": f"u_{story_id}", "AppliedTOCStyle": "n",
        "TrackChanges": "false", "StoryTitle": story_id,
    })
    paras = text.split("\n") if text else [""]
    for i, pt in enumerate(paras):
        is_bullet = False
        if paragraphs_meta and i < len(paragraphs_meta):
            is_bullet = paragraphs_meta[i].get("is_bullet", False)
        elif pt.startswith("• "):
            is_bullet = True
        pstyle = "ParagraphStyle/BulletText" if is_bullet else f"ParagraphStyle/{style}"
        ps = ET.SubElement(story_el, "ParagraphStyleRange", {"AppliedParagraphStyle": pstyle})
        cs = ET.SubElement(ps, "CharacterStyleRange", {
            "AppliedCharacterStyle": "CharacterStyle/$ID/[No character style]",
            "PointSize": str(font_size),
        })
        content_el = ET.SubElement(cs, "Content")
        content_el.text = pt
        if i < len(paras) - 1:
            ET.SubElement(cs, "Br")
    return _xml_str(root)


# ---------------------------------------------------------------------------
# Layout computation — simple stacking algorithm
# ---------------------------------------------------------------------------

def _compute_layout(story: dict) -> list[dict]:
    """Produce a list of frame dicts with positions computed from content."""
    margin = MARGIN_MM
    pw = PAGE_W_MM
    avail = pw - margin * 2
    y = margin
    gap = 5
    frames = []

    headline = story.get("headline", "")
    paragraphs = story.get("paragraphs", [])
    priority = (story.get("priority", "normal") or "normal").lower()

    # Separate text paragraphs, bullets, and images
    body_texts, bullet_meta, image_urls = [], [], []
    for p in paragraphs:
        if isinstance(p, dict):
            pt = p.get("type", "paragraph")
            txt = p.get("text", "")
            img = p.get("image_url", "")
            if pt == "image" or img:
                if img:
                    image_urls.append(img)
                continue
            body_texts.append(txt)
            bullet_meta.append({"is_bullet": pt == "bullet"})
        elif isinstance(p, str):
            body_texts.append(p)
            bullet_meta.append({"is_bullet": False})

    body_text = "\n".join(body_texts)
    total_chars = len(body_text)

    # -- Headline frame --
    headline_pt = 48 if priority in ("breaking", "urgent") else 36
    # Rough height: ~1.2 lines * font_size * chars/line
    h_lines = max(1, len(headline) // 30 + 1)
    h_height = max(20, h_lines * headline_pt * 0.4)
    frames.append({
        "id": "headline", "type": "text", "story_id": "headline",
        "x": margin, "y": y, "w": avail, "h": h_height,
        "style": "Headline", "font_size": headline_pt, "cols": 1,
        "content": headline, "meta": None,
    })
    y += h_height + gap

    # -- Byline --
    reporter = story.get("reporter", {}).get("name", "")
    location = story.get("location", "")
    byline = " | ".join(filter(None, [reporter, location]))
    if byline:
        frames.append({
            "id": "byline", "type": "text", "story_id": "byline",
            "x": margin, "y": y, "w": avail, "h": 10,
            "style": "Byline", "font_size": 9, "cols": 1,
            "content": byline, "meta": None,
        })
        y += 10 + gap

    # -- Image (if any, first image) --
    if image_urls:
        img_h = 120
        frames.append({
            "id": "image-1", "type": "image",
            "x": margin, "y": y, "w": avail, "h": img_h,
            "image_url": image_urls[0],
        })
        y += img_h + gap

    # -- Body --
    cols = 2 if total_chars > 1500 else 1
    body_pt = 10
    # Rough body height estimate: chars / (chars_per_line * cols) * line_height
    cpl = max(1, int(avail / cols / (body_pt * 0.25)))
    lines = max(1, total_chars // cpl)
    body_h = max(50, lines * body_pt * 0.5)
    frames.append({
        "id": "body", "type": "text", "story_id": "body",
        "x": margin, "y": y, "w": avail, "h": body_h,
        "style": "BodyText", "font_size": body_pt, "cols": cols,
        "content": body_text, "meta": bullet_meta,
    })
    y += body_h + gap

    return frames, y + margin, image_urls


# ---------------------------------------------------------------------------
# Spread builder
# ---------------------------------------------------------------------------

def _spread_xml(pw_pt: float, ph_pt: float, frames: list[dict],
                image_links: dict[str, str]) -> str:
    root = ET.Element("idPkg:Spread", {"xmlns:idPkg": _IDPKG_NS, "DOMVersion": _DOM_VERSION})
    spread = ET.SubElement(root, "Spread", {
        "Self": "u_spread_1", "PageCount": "1",
        "FlattenerOverride": "Default", "ShowMasterItems": "true",
    })
    ET.SubElement(spread, "Page", {
        "Self": "u_page_1", "AppliedMaster": "n",
        "GeometricBounds": f"0 0 {ph_pt:.4f} {pw_pt:.4f}",
        "ItemTransform": "1 0 0 1 0 0", "Name": "1",
    })

    for f in frames:
        x_pt = f["x"] * MM_TO_PT
        y_pt = f["y"] * MM_TO_PT
        w_pt = f["w"] * MM_TO_PT
        h_pt = f["h"] * MM_TO_PT

        if f.get("type") == "image" and f["id"] in image_links:
            rect = ET.SubElement(spread, "Rectangle", {
                "Self": f"u_rect_{f['id']}",
                "ItemTransform": f"1 0 0 1 {x_pt:.4f} {y_pt:.4f}",
                "ContentType": "GraphicType", "StrokeWeight": "0",
            })
            _add_path(rect, w_pt, h_pt)
            img_el = ET.SubElement(rect, "Image", {
                "Self": f"u_img_{f['id']}",
                "ItemTransform": "1 0 0 1 0 0",
            })
            ET.SubElement(img_el, "Link", {
                "Self": f"u_link_{f['id']}",
                "LinkResourceURI": f"Links/{image_links[f['id']]}",
                "StoredState": "Normal", "LinkClassID": "35906",
            })
        elif f.get("type") == "image":
            rect = ET.SubElement(spread, "Rectangle", {
                "Self": f"u_rect_{f['id']}",
                "ItemTransform": f"1 0 0 1 {x_pt:.4f} {y_pt:.4f}",
                "ContentType": "Unassigned", "StrokeWeight": "0",
            })
            _add_path(rect, w_pt, h_pt)
        else:
            tf = ET.SubElement(spread, "TextFrame", {
                "Self": f"u_tf_{f['id']}",
                "ParentStory": f"u_{f['story_id']}",
                "ContentType": "TextType",
                "ItemTransform": f"1 0 0 1 {x_pt:.4f} {y_pt:.4f}",
                "StrokeWeight": "0",
            })
            cols = f.get("cols", 1)
            ET.SubElement(tf, "TextFramePreference", {
                "TextColumnCount": str(cols),
                "TextColumnGutter": f"{(4 * MM_TO_PT):.4f}",
            })
            _add_path(tf, w_pt, h_pt)

    return _xml_str(root)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_idml(story: dict) -> bytes:
    """Generate a valid IDML package from story content."""
    frames, total_h, image_urls = _compute_layout(story)
    page_h = max(PAGE_H_MM, total_h)
    pw_pt = PAGE_W_MM * MM_TO_PT
    ph_pt = page_h * MM_TO_PT

    # Download images
    image_links: dict[str, str] = {}
    image_data: dict[str, bytes] = {}
    for i, f in enumerate(frames):
        if f.get("type") == "image" and f.get("image_url"):
            url = f["image_url"]
            ext = _guess_ext(url)
            fname = f"image_{i+1}.{ext}"
            data = await _download_image(url)
            if data:
                image_links[f["id"]] = fname
                image_data[fname] = data

    # Collect story XMLs
    story_ids = []
    story_xmls = {}
    for f in frames:
        if f.get("type") != "image":
            sid = f["story_id"]
            if sid not in story_xmls:
                story_ids.append(sid)
                story_xmls[sid] = _story_xml(
                    sid, f["style"], f["content"],
                    f.get("font_size", 10), f.get("meta"),
                )

    # Assemble ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"),
                     "application/vnd.adobe.indesign-idml-package",
                     compress_type=zipfile.ZIP_STORED)
        container = '<?xml version="1.0"?><container version="1.0"><rootfiles>' \
                    '<rootfile full-path="designmap.xml" media-type="text/xml"/></rootfiles></container>'
        zf.writestr("META-INF/container.xml", container, zipfile.ZIP_DEFLATED)
        zf.writestr("designmap.xml", _designmap(story_ids, pw_pt, ph_pt), zipfile.ZIP_DEFLATED)
        zf.writestr("Resources/Styles.xml", _styles(), zipfile.ZIP_DEFLATED)
        zf.writestr("Resources/Graphic.xml", _graphic(), zipfile.ZIP_DEFLATED)
        prefs = f'<?xml version="1.0"?><idPkg:Preferences xmlns:idPkg="{_IDPKG_NS}" DOMVersion="{_DOM_VERSION}"/>'
        zf.writestr("Resources/Preferences.xml", prefs, zipfile.ZIP_DEFLATED)
        fonts = f'<?xml version="1.0"?><idPkg:Fonts xmlns:idPkg="{_IDPKG_NS}" DOMVersion="{_DOM_VERSION}"/>'
        zf.writestr("Resources/Fonts.xml", fonts, zipfile.ZIP_DEFLATED)
        zf.writestr("Spreads/Spread_1.xml",
                     _spread_xml(pw_pt, ph_pt, frames, image_links), zipfile.ZIP_DEFLATED)
        for sid, xml in story_xmls.items():
            zf.writestr(f"Stories/Story_{sid}.xml", xml, zipfile.ZIP_DEFLATED)
        for fname, data in image_data.items():
            zf.writestr(f"Links/{fname}", data, zipfile.ZIP_DEFLATED)

    return buf.getvalue()
