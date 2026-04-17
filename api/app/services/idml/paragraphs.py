"""Story XML and text-frame builders — paragraph-level rendering."""

from xml.sax.saxutils import escape as xml_escape

from ._constants import COL_GAP_PT, LATIN_FONT, ODIA_FONT, _ODIA_RE


def _is_odia_char(ch: str) -> bool:
    """True if char is in the Odia Unicode block (U+0B00–U+0B7F)."""
    return bool(_ODIA_RE.match(ch))


def _split_runs(text: str) -> list[tuple[str, bool]]:
    """Split text into consecutive (chunk, is_odia) runs.

    Classification:
      - Odia block (U+0B00–U+0B7F)   → Odia run
      - ASCII letters/digits         → Latin run
      - Everything else              → neutral, adheres to surrounding run

    Treating only ASCII alphanumerics as "Latin" keeps Odia sentence
    punctuation (danda U+0964, double-danda U+0965), zero-width
    joiners (U+200C/U+200D), smart quotes, em/en dashes, etc. attached
    to the Odia run so they render in Noto Sans Oriya instead of being
    sent to Minion Pro (which lacks those glyphs and shows a missing-
    glyph box). Whitespace is also neutral so a pure-Odia sentence
    stays a single run instead of being chopped at every space.
    """
    if not text:
        return []

    classes: list[bool | None] = []  # True=odia, False=latin, None=neutral
    for ch in text:
        if _is_odia_char(ch):
            classes.append(True)
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            classes.append(False)
        else:
            classes.append(None)

    # Collapse: whitespace inherits from the previous non-whitespace
    # class; if none yet, look ahead to the next non-whitespace.
    resolved: list[bool] = []
    for i, c in enumerate(classes):
        if c is not None:
            resolved.append(c)
            continue
        # whitespace
        prev = next((classes[j] for j in range(i - 1, -1, -1) if classes[j] is not None), None)
        if prev is None:
            prev = next((classes[j] for j in range(i + 1, len(classes)) if classes[j] is not None), False)
        resolved.append(bool(prev))

    runs: list[tuple[str, bool]] = []
    cur_chars: list[str] = []
    cur_is_odia: bool | None = None
    for ch, is_odia in zip(text, resolved):
        if cur_is_odia is None or is_odia == cur_is_odia:
            cur_chars.append(ch)
            cur_is_odia = is_odia
        else:
            runs.append(("".join(cur_chars), bool(cur_is_odia)))
            cur_chars = [ch]
            cur_is_odia = is_odia
    if cur_chars:
        runs.append(("".join(cur_chars), bool(cur_is_odia)))
    return runs


def _character_style_range_xml(run_text: str, is_odia: bool, *,
                               pt: float, just: str, color: str,
                               style: str) -> str:
    """Emit one <CharacterStyleRange> for a single-script text run.

    Splits on newlines (\n) into <Content>...</Content> + <Br /> children.
    """
    font = ODIA_FONT if is_odia else LATIN_FONT
    lang = "$ID/Oriya" if is_odia else "$ID/English: USA"
    escaped = xml_escape(run_text)
    lines = escaped.split("\n") if escaped else [""]
    content_parts = []
    for i, line in enumerate(lines):
        content_parts.append(f"\t\t\t\t<Content>{line}</Content>")
        if i < len(lines) - 1:
            content_parts.append("\t\t\t\t<Br />")
    content_xml = "\n".join(content_parts)

    return (
        f"\t\t\t<CharacterStyleRange "
        f'AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" '
        f'FillColor="{color}" PointSize="{pt}" FontStyle="{style}" '
        f'AppliedLanguage="{lang}" Ligatures="true">\n'
        f"\t\t\t\t<Properties>\n"
        f'\t\t\t\t\t<AppliedFont type="string">{font}</AppliedFont>\n'
        f"\t\t\t\t</Properties>\n"
        f"{content_xml}\n"
        f"\t\t\t</CharacterStyleRange>"
    )


def _story_xml(story_id: str, paragraphs: list[dict]) -> str:
    """Build a Story XML file.

    Each paragraph dict: {text, point_size, justification, fill_color, font_style}
    Splits each paragraph by Unicode script so Latin chunks render with
    Minion Pro and Odia chunks render with Noto Sans Oriya — preventing
    missing-glyph "tofu" boxes when a paragraph mixes scripts.
    """
    para_xml_parts = []
    for p in paragraphs:
        raw_text = p.get("text", "") or ""
        pt = p.get("point_size", 12)
        just = p.get("justification", "LeftAlign")
        color = p.get("fill_color", "Color/Black")
        style = p.get("font_style", "Regular")

        runs = _split_runs(raw_text) or [("", False)]
        csr_blocks = [
            _character_style_range_xml(
                run_text, is_odia,
                pt=pt, just=just, color=color, style=style,
            )
            for run_text, is_odia in runs
        ]
        csrs_xml = "\n".join(csr_blocks)

        para_xml_parts.append(
            f"\t\t<ParagraphStyleRange "
            f'AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle" '
            f'Justification="{just}" '
            f'Composer="Adobe World-Ready Paragraph Composer">\n'
            f"{csrs_xml}\n"
            f"\t\t</ParagraphStyleRange>"
        )

    paras_xml = "\n".join(para_xml_parts)

    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<Story Self="{story_id}" UserText="true" IsEndnoteStory="false" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" AppliedNamedGrid="n">
\t\t<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" FrameType="TextFrameType" StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection" />
\t\t<InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false" />
{paras_xml}
\t</Story>
</idPkg:Story>"""


def _text_frame_xml(frame_id: str, story_id: str, cx: float, cy: float,
                    hw: float, hh: float, col_count: int = 1,
                    v_just: str = "TopAlign") -> str:
    """Build a TextFrame XML element for the spread."""
    col_width = (hw * 2 - COL_GAP_PT * (col_count - 1)) / col_count if col_count > 1 else hw * 2

    return f"""\
\t\t<TextFrame Self="{frame_id}" ParentStory="{story_id}" PreviousTextFrame="n" NextTextFrame="n" ContentType="TextType" OverriddenPageItemProps="" Visible="true" Name="$ID/" ItemLayer="uce" Locked="false" LocalDisplaySetting="Default" AppliedObjectStyle="ObjectStyle/$ID/[Normal Text Frame]" ItemTransform="1 0 0 1 {cx} {cy}" GradientFillStart="0 0" GradientFillLength="0" GradientFillAngle="0" GradientStrokeStart="0 0" GradientStrokeLength="0" GradientStrokeAngle="0">
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
\t\t\t</Properties>
\t\t\t<ObjectExportOption AltTextSourceType="SourceXMLStructure" ActualTextSourceType="SourceXMLStructure" CustomAltText="$ID/" CustomActualText="$ID/" ApplyTagType="TagFromStructure" ImageConversionType="JPEG" ImageExportResolution="Ppi300" GIFOptionsPalette="AdaptivePalette" GIFOptionsInterlaced="true" JPEGOptionsQuality="High" JPEGOptionsFormat="BaselineEncoding" ImageAlignment="AlignLeft" ImageSpaceBefore="0" ImageSpaceAfter="0" UseImagePageBreak="false" ImagePageBreak="PageBreakBefore" CustomImageAlignment="false" SpaceUnit="CssPixel" CustomLayout="false" CustomLayoutType="AlignmentAndSpacing" EpubType="$ID/" SizeType="DefaultSize" CustomSize="$ID/" PreserveAppearanceFromLayout="PreserveAppearanceDefault" EpubAriaRole="$ID/" EpubAriaLabel="$ID/" EpubAriaLabelSourceType="AutomaticARIALabel">
\t\t\t\t<Properties>
\t\t\t\t\t<AltMetadataProperty NamespacePrefix="$ID/" PropertyPath="$ID/" />
\t\t\t\t\t<ActualMetadataProperty NamespacePrefix="$ID/" PropertyPath="$ID/" />
\t\t\t\t</Properties>
\t\t\t</ObjectExportOption>
\t\t\t<TextFramePreference TextColumnCount="{col_count}" TextColumnFixedWidth="{col_width}" VerticalJustification="{v_just}" TextColumnMaxWidth="0" TextColumnGutter="{COL_GAP_PT}">
\t\t\t\t<Properties>
\t\t\t\t\t<InsetSpacing type="list">
\t\t\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t\t</InsetSpacing>
\t\t\t\t</Properties>
\t\t\t</TextFramePreference>
\t\t\t<TextWrapPreference Inverse="false" ApplyToMasterPageOnly="false" TextWrapSide="BothSides" TextWrapMode="None">
\t\t\t\t<Properties>
\t\t\t\t\t<TextWrapOffset Top="0" Left="0" Bottom="0" Right="0" />
\t\t\t\t</Properties>
\t\t\t</TextWrapPreference>
\t\t</TextFrame>"""
