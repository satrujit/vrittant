"""Story XML and text-frame builders — paragraph-level rendering."""

from xml.sax.saxutils import escape as xml_escape

from ._constants import COL_GAP_PT, LATIN_FONT, ODIA_FONT, _is_odia


def _story_xml(story_id: str, paragraphs: list[dict]) -> str:
    """Build a Story XML file.

    Each paragraph dict: {text, point_size, justification, fill_color, font_style}
    Automatically detects Odia script and applies the correct font + language.
    """
    para_xml_parts = []
    for p in paragraphs:
        text = xml_escape(p.get("text", ""))
        pt = p.get("point_size", 12)
        just = p.get("justification", "LeftAlign")
        color = p.get("fill_color", "Color/Black")
        style = p.get("font_style", "Regular")

        # Detect Odia text and apply appropriate font + language
        raw_text = p.get("text", "")
        odia = _is_odia(raw_text)
        font = ODIA_FONT if odia else LATIN_FONT
        lang = '$ID/Oriya' if odia else '$ID/English: USA'

        # Split on newlines for multi-line paragraphs
        lines = text.split("\n") if text else [""]
        content_parts = []
        for i, line in enumerate(lines):
            content_parts.append(f"\t\t\t\t<Content>{line}</Content>")
            if i < len(lines) - 1:
                content_parts.append('\t\t\t\t<Br />')
        content_xml = "\n".join(content_parts)

        para_xml_parts.append(f"""\
\t\t<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle" Justification="{just}" Composer="Adobe World-Ready Paragraph Composer">
\t\t\t<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" FillColor="{color}" PointSize="{pt}" FontStyle="{style}" AppliedLanguage="{lang}" Ligatures="true">
\t\t\t\t<Properties>
\t\t\t\t\t<AppliedFont type="string">{font}</AppliedFont>
\t\t\t\t</Properties>
{content_xml}
\t\t\t</CharacterStyleRange>
\t\t</ParagraphStyleRange>""")

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
