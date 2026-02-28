"""IDML generator: builds a valid InDesign IDML package (.idml) as a ZIP file.

Uses only Python stdlib: zipfile, xml.etree, io, re.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MM_TO_PT = 2.8346  # 1 mm = 2.8346 points (InDesign)
_IDPKG_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
_DOM_VERSION = "7.5"

ZONE_STYLE_MAP = {
    "masthead": "Masthead",
    "headline": "Headline",
    "body": "BodyText",
    "pullquote": "Pullquote",
    "highlight": "Highlight",
    "sidebar": "Sidebar",
}

# Zone types that should become Rectangle elements instead of TextFrame
_NON_TEXT_ZONE_TYPES = {"divider", "image"}


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def hex_to_cmyk(hex_color: str) -> tuple[float, float, float, float]:
    """Convert a hex colour string (#RRGGBB) to a (C, M, Y, K) tuple of floats 0..1."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0.0, 0.0, 0.0, 1.0)

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 1.0)

    c = (1.0 - r - k) / (1.0 - k)
    m = (1.0 - g - k) / (1.0 - k)
    y = (1.0 - b - k) / (1.0 - k)
    return (round(c, 4), round(m, 4), round(y, 4), round(k, 4))


# ---------------------------------------------------------------------------
# XML serialisation helper
# ---------------------------------------------------------------------------

def _xml_to_string(root: ET.Element) -> str:
    """Serialize an ElementTree element to a UTF-8 XML string with declaration."""
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
        root, encoding="unicode", xml_declaration=False
    )


# ---------------------------------------------------------------------------
# Private XML builders
# ---------------------------------------------------------------------------

def _mimetype() -> str:
    return "application/vnd.adobe.indesign-idml-package"


def _container_xml() -> str:
    root = ET.Element("container", version="1.0")
    rootfiles = ET.SubElement(root, "rootfiles")
    ET.SubElement(rootfiles, "rootfile", {
        "full-path": "designmap.xml",
        "media-type": "text/xml",
    })
    return _xml_to_string(root)


def _designmap_xml(story_ids: list[str], page_w_pt: float, page_h_pt: float) -> str:
    root = ET.Element("Document", {
        "DOMVersion": _DOM_VERSION,
        "Self": "d",
        "xmlns:idPkg": _IDPKG_NS,
        "StoryList": " ".join(f"u_{sid}" for sid in story_ids),
    })

    # Document preferences
    dp = ET.SubElement(root, "DocumentPreference", {
        "PageWidth": f"{page_w_pt:.4f}",
        "PageHeight": f"{page_h_pt:.4f}",
        "PagesPerDocument": "1",
        "FacingPages": "false",
        "DocumentBleedTopOffset": "0",
        "DocumentBleedBottomOffset": "0",
        "DocumentBleedInsideOrLeftOffset": "0",
        "DocumentBleedOutsideOrRightOffset": "0",
    })

    # Language (required for text composition)
    ET.SubElement(root, "Language", {
        "Self": "Language/$ID/English",
        "Name": "$ID/English",
        "SingleQuotes": "\u2018\u2019",
        "DoubleQuotes": "\u201c\u201d",
        "ICULocaleName": "en",
    })

    # Package references
    ET.SubElement(root, "idPkg:Graphic", src="Resources/Graphic.xml")
    ET.SubElement(root, "idPkg:Fonts", src="Resources/Fonts.xml")
    ET.SubElement(root, "idPkg:Styles", src="Resources/Styles.xml")
    ET.SubElement(root, "idPkg:Preferences", src="Resources/Preferences.xml")
    ET.SubElement(root, "idPkg:Spread", src="Spreads/Spread_1.xml")

    for sid in story_ids:
        ET.SubElement(root, "idPkg:Story", src=f"Stories/Story_{sid}.xml")

    return _xml_to_string(root)


def _preferences_xml(page_w_pt: float, page_h_pt: float) -> str:
    root = ET.Element("idPkg:Preferences", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })

    # Text default
    ET.SubElement(root, "TextDefault", {
        "Self": "u_text_default",
        "AppliedParagraphStyle": "ParagraphStyle/$ID/NormalParagraphStyle",
        "AppliedCharacterStyle": "CharacterStyle/$ID/[No character style]",
    })

    return _xml_to_string(root)


def _fonts_xml() -> str:
    root = ET.Element("idPkg:Fonts", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })
    return _xml_to_string(root)


def _styles_xml() -> str:
    root = ET.Element("idPkg:Styles", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })

    # --- Root Paragraph Style Group ---
    rpsg = ET.SubElement(root, "RootParagraphStyleGroup", Self="u_root_para_styles")

    # Default [No paragraph style]
    ET.SubElement(rpsg, "ParagraphStyle", {
        "Self": "ParagraphStyle/$ID/NormalParagraphStyle",
        "Name": "$ID/NormalParagraphStyle",
    })

    style_defs = {
        "Masthead":  {"FontStyle": "Bold", "PointSize": "36", "Justification": "CenterAlign"},
        "Headline":  {"FontStyle": "Bold", "PointSize": "28", "Justification": "LeftAlign"},
        "BodyText":  {"FontStyle": "Regular", "PointSize": "10", "Justification": "LeftJustified"},
        "Pullquote": {"FontStyle": "Italic", "PointSize": "14", "Justification": "CenterAlign"},
        "Highlight": {"FontStyle": "Bold", "PointSize": "12", "Justification": "LeftAlign"},
        "Sidebar":   {"FontStyle": "Regular", "PointSize": "9", "Justification": "LeftAlign"},
    }

    for name, attrs in style_defs.items():
        style_el = ET.SubElement(rpsg, "ParagraphStyle", {
            "Self": f"ParagraphStyle/{name}",
            "Name": name,
        })
        props = ET.SubElement(style_el, "Properties")
        for prop_name, prop_val in attrs.items():
            el = ET.SubElement(props, prop_name)
            el.text = prop_val

    # --- Root Character Style Group ---
    rcsg = ET.SubElement(root, "RootCharacterStyleGroup", Self="u_root_char_styles")
    ET.SubElement(rcsg, "CharacterStyle", {
        "Self": "CharacterStyle/$ID/[No character style]",
        "Name": "$ID/[No character style]",
    })

    # --- Root Object Style Group ---
    rosg = ET.SubElement(root, "RootObjectStyleGroup", Self="u_root_obj_styles")
    ET.SubElement(rosg, "ObjectStyle", {
        "Self": "ObjectStyle/$ID/[None]",
        "Name": "$ID/[None]",
    })

    return _xml_to_string(root)


def _graphic_xml(swatches: dict[str, str]) -> str:
    root = ET.Element("idPkg:Graphic", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })

    # Default swatches that InDesign expects
    default_colors = {
        "Black": (0.0, 0.0, 0.0, 100.0),
        "Paper": (0.0, 0.0, 0.0, 0.0),
        "Registration": (100.0, 100.0, 100.0, 100.0),
    }

    for name, (c, m, y, k) in default_colors.items():
        ET.SubElement(root, "Color", {
            "Self": f"Color/{name}",
            "Name": name,
            "Model": "Process",
            "Space": "CMYK",
            "ColorValue": f"{c:.2f} {m:.2f} {y:.2f} {k:.2f}",
        })

    # Default swatch group
    ET.SubElement(root, "Swatch", {
        "Self": "Swatch/None",
        "Name": "None",
        "ColorValue": "0 0 0 0",
    })

    # Custom swatches from zones
    for name, hex_val in swatches.items():
        c, m, y, k = hex_to_cmyk(hex_val)
        ET.SubElement(root, "Color", {
            "Self": f"Color/{name}",
            "Name": name,
            "Model": "Process",
            "Space": "CMYK",
            "ColorValue": f"{c * 100:.2f} {m * 100:.2f} {y * 100:.2f} {k * 100:.2f}",
        })

    return _xml_to_string(root)


def _spread_xml(
    page_w_pt: float,
    page_h_pt: float,
    zones: list[dict],
    story_map: dict[str, str],
) -> str:
    root = ET.Element("idPkg:Spread", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })

    spread = ET.SubElement(root, "Spread", {
        "Self": "u_spread_1",
        "PageCount": "1",
        "BindingLocation": "0",
        "AllowPageShuffle": "true",
        "FlattenerOverride": "Default",
        "ShowMasterItems": "true",
        "PageTransitionType": "None",
    })

    # Flattener preference (required by InDesign)
    ET.SubElement(spread, "FlattenerPreference", {
        "Self": "u_spread_1_flattener",
        "LineArtAndTextResolution": "300",
        "GradientAndMeshResolution": "150",
        "ClipComplexRegions": "false",
        "ConvertAllStrokesToOutlines": "false",
        "ConvertAllTextToOutlines": "false",
    })

    # Page element with proper attributes
    page = ET.SubElement(spread, "Page", {
        "Self": "u_page_1",
        "AppliedMaster": "n",
        "GeometricBounds": f"0 0 {page_h_pt:.4f} {page_w_pt:.4f}",
        "ItemTransform": "1 0 0 1 0 0",
        "Name": "1",
        "OverrideList": "",
        "TabOrder": "",
    })

    # Margin preference on page
    ET.SubElement(page, "MarginPreference", {
        "ColumnCount": "1",
        "ColumnGutter": "12",
        "Top": "28",
        "Bottom": "28",
        "Left": "28",
        "Right": "28",
        "ColumnDirection": "Horizontal",
    })

    for zone in zones:
        zone_id = zone.get("id", "")
        zone_type = zone.get("type", "")
        x_pt = zone.get("x_mm", 0) * MM_TO_PT
        y_pt = zone.get("y_mm", 0) * MM_TO_PT
        w_pt = zone.get("width_mm", 0) * MM_TO_PT
        h_pt = zone.get("height_mm", 0) * MM_TO_PT
        cols = zone.get("columns", 1)
        gap_pt = zone.get("column_gap_mm", 4) * MM_TO_PT

        if zone_type in _NON_TEXT_ZONE_TYPES:
            rect_el = ET.SubElement(spread, "Rectangle", {
                "Self": f"u_rect_{zone_id}",
                "ItemTransform": f"1 0 0 1 {x_pt:.4f} {y_pt:.4f}",
                "ContentType": "Unassigned",
                "StrokeWeight": "0",
            })

            bg_color = zone.get("bg_color", "")
            if bg_color and bg_color != "#FFFFFF":
                rect_el.set("FillColor", f"Color/{zone_id}_bg")

            _add_path_geometry(rect_el, w_pt, h_pt)
        else:
            story_id = story_map.get(zone_id, zone_id)
            tf_el = ET.SubElement(spread, "TextFrame", {
                "Self": f"u_tf_{zone_id}",
                "ParentStory": f"u_{story_id}",
                "ContentType": "TextType",
                "ItemTransform": f"1 0 0 1 {x_pt:.4f} {y_pt:.4f}",
                "StrokeWeight": "0",
            })

            bg_color = zone.get("bg_color", "")
            if bg_color and bg_color != "#FFFFFF":
                tf_el.set("FillColor", f"Color/{zone_id}_bg")

            ET.SubElement(tf_el, "TextFramePreference", {
                "TextColumnCount": str(max(1, cols)),
                "TextColumnGutter": f"{gap_pt:.4f}",
            })

            _add_path_geometry(tf_el, w_pt, h_pt)

    return _xml_to_string(root)


def _add_path_geometry(parent_el: ET.Element, w_pt: float, h_pt: float) -> None:
    """Add PathGeometry with a 4-corner bounding box to a TextFrame or Rectangle."""
    props = ET.SubElement(parent_el, "Properties")
    pg = ET.SubElement(props, "PathGeometry")
    gpc = ET.SubElement(pg, "GeometryPathType", PathOpen="false")
    ppa = ET.SubElement(gpc, "PathPointArray")

    corners = [
        (0, 0),
        (w_pt, 0),
        (w_pt, h_pt),
        (0, h_pt),
    ]
    for cx, cy in corners:
        ET.SubElement(ppa, "PathPointType", {
            "Anchor": f"{cx:.4f} {cy:.4f}",
            "LeftDirection": f"{cx:.4f} {cy:.4f}",
            "RightDirection": f"{cx:.4f} {cy:.4f}",
        })


def _story_xml(story_id: str, style_name: str, content: str, font_size: float) -> str:
    root = ET.Element("idPkg:Story", {
        "xmlns:idPkg": _IDPKG_NS,
        "DOMVersion": _DOM_VERSION,
    })

    story_el = ET.SubElement(root, "Story", {
        "Self": f"u_{story_id}",
        "AppliedTOCStyle": "n",
        "TrackChanges": "false",
        "StoryTitle": story_id,
        "AppliedNamedGrid": "n",
    })

    # Split content into paragraphs at newlines
    para_texts = content.split("\n") if content else [""]

    for i, para_text in enumerate(para_texts):
        ps = ET.SubElement(story_el, "ParagraphStyleRange", {
            "AppliedParagraphStyle": f"ParagraphStyle/{style_name}",
        })
        cs = ET.SubElement(ps, "CharacterStyleRange", {
            "AppliedCharacterStyle": "CharacterStyle/$ID/[No character style]",
            "PointSize": str(font_size),
        })
        content_el = ET.SubElement(cs, "Content")
        content_el.text = para_text

        # Add paragraph break between paragraphs (not after the last one)
        if i < len(para_texts) - 1:
            br_el = ET.SubElement(cs, "Br")

    return _xml_to_string(root)


# ---------------------------------------------------------------------------
# Content extraction helpers
# ---------------------------------------------------------------------------

def _get_zone_content(zone: dict, story: dict) -> str:
    """Determine text content for a zone based on its type."""
    zone_type = zone.get("type", "")

    if zone_type == "masthead":
        return zone.get("label", "")
    elif zone_type == "headline":
        return story.get("headline", "")
    elif zone_type == "body":
        paragraphs = story.get("paragraphs", [])
        texts = []
        for p in paragraphs:
            if isinstance(p, dict):
                texts.append(p.get("text", ""))
            elif isinstance(p, str):
                texts.append(p)
        return "\n".join(texts)
    elif zone_type in ("pullquote", "highlight", "sidebar"):
        return zone.get("text", "")
    else:
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_idml(layout_config: dict, story: dict) -> bytes:
    """Generate a valid IDML package from layout config and story content.

    Parameters
    ----------
    layout_config : dict
        {width_mm, height_mm, zones: [{id, type, label, x_mm, y_mm,
        width_mm, height_mm, columns, column_gap_mm, font_size_pt,
        font_family, bg_color, text_color, border_color, text}, ...]}
    story : dict
        {headline, paragraphs: [{text}], category, reporter: {name}, location}

    Returns
    -------
    bytes
        ZIP bytes of the .idml package.
    """
    width_mm = layout_config.get("width_mm", 380)
    height_mm = layout_config.get("height_mm", 560)
    zones = layout_config.get("zones", [])

    page_w_pt = width_mm * MM_TO_PT
    page_h_pt = height_mm * MM_TO_PT

    # --- Build story_map and collect swatches ---
    story_map: dict[str, str] = {}   # zone_id -> story_id
    swatches: dict[str, str] = {}    # swatch_name -> hex_color
    stories: dict[str, dict] = {}    # story_id -> {style_name, content, font_size}

    for zone in zones:
        zone_id = zone.get("id", "")
        zone_type = zone.get("type", "")

        # Collect swatches for all zones
        for color_field, suffix in [("bg_color", "bg"), ("text_color", "text"), ("border_color", "border")]:
            hex_val = zone.get(color_field, "")
            if hex_val and hex_val not in ("#FFFFFF", "#000000"):
                swatches[f"{zone_id}_{suffix}"] = hex_val

        # Skip non-text zones (no story needed)
        if zone_type in _NON_TEXT_ZONE_TYPES:
            continue

        # Story mapping
        story_id = f"story_{zone_id}"
        story_map[zone_id] = story_id

        style_name = ZONE_STYLE_MAP.get(zone_type, "BodyText")
        content = _get_zone_content(zone, story)
        font_size = zone.get("font_size_pt", 10)

        stories[story_id] = {
            "style_name": style_name,
            "content": content,
            "font_size": font_size,
        }

    # --- Assemble ZIP ---
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # 1. mimetype MUST be first entry, stored uncompressed (IDML spec)
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            _mimetype(),
            compress_type=zipfile.ZIP_STORED,
        )

        # 2. META-INF/container.xml
        zf.writestr("META-INF/container.xml", _container_xml(), compress_type=zipfile.ZIP_DEFLATED)

        # 3. designmap.xml
        story_ids = list(stories.keys())
        zf.writestr("designmap.xml", _designmap_xml(story_ids, page_w_pt, page_h_pt), compress_type=zipfile.ZIP_DEFLATED)

        # 4. Resources/Preferences.xml
        zf.writestr("Resources/Preferences.xml", _preferences_xml(page_w_pt, page_h_pt), compress_type=zipfile.ZIP_DEFLATED)

        # 5. Resources/Fonts.xml
        zf.writestr("Resources/Fonts.xml", _fonts_xml(), compress_type=zipfile.ZIP_DEFLATED)

        # 6. Resources/Styles.xml
        zf.writestr("Resources/Styles.xml", _styles_xml(), compress_type=zipfile.ZIP_DEFLATED)

        # 7. Resources/Graphic.xml
        zf.writestr("Resources/Graphic.xml", _graphic_xml(swatches), compress_type=zipfile.ZIP_DEFLATED)

        # 8. Spreads/Spread_1.xml
        zf.writestr(
            "Spreads/Spread_1.xml",
            _spread_xml(page_w_pt, page_h_pt, zones, story_map),
            compress_type=zipfile.ZIP_DEFLATED,
        )

        # 9. Stories
        for sid, sdata in stories.items():
            zf.writestr(
                f"Stories/Story_{sid}.xml",
                _story_xml(sid, sdata["style_name"], sdata["content"], sdata["font_size"]),
                compress_type=zipfile.ZIP_DEFLATED,
            )

    return buf.getvalue()
