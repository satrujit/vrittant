"""IDML generator — produces InDesign-compatible IDML packages.

Matches the structure of InDesign 2025 (DOMVersion 21.2) exports.
Text frames use center-based coordinate system with PathGeometry.
"""

import io
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOM_VERSION = "21.2"
NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

PAGE_W_PT = 612.0   # US Letter
PAGE_H_PT = 792.0
MARGIN_PT = 36.0
CONTENT_W = PAGE_W_PT - 2 * MARGIN_PT   # 540
CONTENT_H = PAGE_H_PT - 2 * MARGIN_PT   # 720
COL_GAP_PT = 12.0

# ---------------------------------------------------------------------------
# Static XML templates (from validated InDesign 2025 IDML export)
# ---------------------------------------------------------------------------

MIMETYPE = "application/vnd.adobe.indesign-idml-package"

CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
\t<rootfiles>
\t\t<rootfile full-path="designmap.xml" media-type="text/xml">
\t\t</rootfile>
\t</rootfiles>
</container>"""

TAGS_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Tags xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<XMLTag Self="XMLTag/Root" Name="Root">
\t\t<Properties>
\t\t\t<TagColor type="enumeration">LightBlue</TagColor>
\t\t</Properties>
\t</XMLTag>
</idPkg:Tags>"""

BACKING_STORY_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:BackingStory xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<XmlStory Self="ub3" UserText="true" IsEndnoteStory="false" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" AppliedNamedGrid="n">
\t\t<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle">
\t\t\t<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
\t\t\t\t<XMLElement Self="di2" MarkupTag="XMLTag/Root" />
\t\t\t\t<Content>\ufeff</Content>
\t\t\t</CharacterStyleRange>
\t\t</ParagraphStyleRange>
\t</XmlStory>
</idPkg:BackingStory>"""

MASTER_SPREAD_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:MasterSpread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<MasterSpread Self="ud8" Name="A-Parent" NamePrefix="A" BaseName="Parent" ShowMasterItems="true" PageCount="2" OverriddenPageItemProps="" PrimaryTextFrame="n" ItemTransform="1 0 0 1 0 0">
\t\t<Properties>
\t\t\t<PageColor type="enumeration">UseMasterColor</PageColor>
\t\t</Properties>
\t\t<Page Self="udd" TabOrder="" AppliedMaster="n" OverrideList="" MasterPageTransform="1 0 0 1 0 0" Name="A" AppliedTrapPreset="TrapPreset/$ID/kDefaultTrapStyleName" GeometricBounds="0 0 {ph} {pw}" ItemTransform="1 0 0 1 -{pw} -{half_ph}" AppliedAlternateLayout="n" LayoutRule="Off" SnapshotBlendingMode="IgnoreLayoutSnapshots" OptionalPage="false" GridStartingPoint="TopOutside" UseMasterGrid="true">
\t\t\t<Properties>
\t\t\t\t<PageColor type="enumeration">UseMasterColor</PageColor>
\t\t\t</Properties>
\t\t\t<MarginPreference ColumnCount="1" ColumnGutter="12" Top="36" Bottom="36" Left="36" Right="36" ColumnDirection="Horizontal" ColumnsPositions="0 {content_w}" />
\t\t</Page>
\t\t<Page Self="ude" TabOrder="" AppliedMaster="n" OverrideList="" MasterPageTransform="1 0 0 1 0 0" Name="A" AppliedTrapPreset="TrapPreset/$ID/kDefaultTrapStyleName" GeometricBounds="0 0 {ph} {pw}" ItemTransform="1 0 0 1 0 -{half_ph}" AppliedAlternateLayout="n" LayoutRule="Off" SnapshotBlendingMode="IgnoreLayoutSnapshots" OptionalPage="false" GridStartingPoint="TopOutside" UseMasterGrid="true">
\t\t\t<Properties>
\t\t\t\t<PageColor type="enumeration">UseMasterColor</PageColor>
\t\t\t</Properties>
\t\t\t<MarginPreference ColumnCount="1" ColumnGutter="12" Top="36" Bottom="36" Left="36" Right="36" ColumnDirection="Horizontal" ColumnsPositions="0 {content_w}" />
\t\t</Page>
\t</MasterSpread>
</idPkg:MasterSpread>"""


def _master_spread_xml(pw: float = PAGE_W_PT, ph: float = PAGE_H_PT) -> str:
    return MASTER_SPREAD_XML.format(
        pw=int(pw), ph=int(ph),
        half_ph=int(ph / 2),
        content_w=int(pw - 2 * MARGIN_PT),
    )


# ---------------------------------------------------------------------------
# Graphic.xml — colors, inks, swatches, stroke styles
# ---------------------------------------------------------------------------

GRAPHIC_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" ColorOverride="Specialblack" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Black" ColorEditable="false" ColorRemovable="false" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch3" />
\t<Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" ColorOverride="Specialpaper" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Paper" ColorEditable="true" ColorRemovable="false" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch2" />
\t<Color Self="Color/Registration" Model="Registration" Space="CMYK" ColorValue="100 100 100 100" ColorOverride="Specialregistration" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Registration" ColorEditable="false" ColorRemovable="false" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch1" />
\t<Color Self="Color/C=100 M=0 Y=0 K=0" Model="Process" Space="CMYK" ColorValue="100 0 0 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=100 M=0 Y=0 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch4" />
\t<Color Self="Color/C=0 M=100 Y=0 K=0" Model="Process" Space="CMYK" ColorValue="0 100 0 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=0 M=100 Y=0 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch5" />
\t<Color Self="Color/C=0 M=0 Y=100 K=0" Model="Process" Space="CMYK" ColorValue="0 0 100 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=0 M=0 Y=100 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch6" />
\t<Color Self="Color/C=15 M=100 Y=100 K=0" Model="Process" Space="CMYK" ColorValue="15 100 100 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=15 M=100 Y=100 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch7" />
\t<Color Self="Color/C=75 M=5 Y=100 K=0" Model="Process" Space="CMYK" ColorValue="75 5 100 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=75 M=5 Y=100 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch8" />
\t<Color Self="Color/C=100 M=90 Y=10 K=0" Model="Process" Space="CMYK" ColorValue="100 90 10 0" ColorOverride="Normal" ConvertToHsb="false" AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="C=100 M=90 Y=10 K=0" ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch9" />
\t<Ink Self="Ink/$ID/Process Cyan" Name="$ID/Process Cyan" Angle="75" ConvertToProcess="false" Frequency="70" NeutralDensity="0.61" PrintInk="true" TrapOrder="1" InkType="Normal" />
\t<Ink Self="Ink/$ID/Process Magenta" Name="$ID/Process Magenta" Angle="15" ConvertToProcess="false" Frequency="70" NeutralDensity="0.76" PrintInk="true" TrapOrder="2" InkType="Normal" />
\t<Ink Self="Ink/$ID/Process Yellow" Name="$ID/Process Yellow" Angle="0" ConvertToProcess="false" Frequency="70" NeutralDensity="0.16" PrintInk="true" TrapOrder="3" InkType="Normal" />
\t<Ink Self="Ink/$ID/Process Black" Name="$ID/Process Black" Angle="45" ConvertToProcess="false" Frequency="70" NeutralDensity="1.7" PrintInk="true" TrapOrder="4" InkType="Normal" />
\t<Swatch Self="Swatch/None" Name="None" ColorEditable="false" ColorRemovable="false" Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="u18ColorGroupSwatch0" />
\t<StrokeStyle Self="StrokeStyle/$ID/Solid" Name="$ID/Solid" />
\t<StrokeStyle Self="StrokeStyle/$ID/Dashed" Name="$ID/Dashed" />
\t<StrokeStyle Self="StrokeStyle/$ID/Canned Dotted" Name="$ID/Canned Dotted" />
</idPkg:Graphic>"""

# ---------------------------------------------------------------------------
# Fonts.xml
# ---------------------------------------------------------------------------

FONTS_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Fonts xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<FontFamily Self="di41" Name="Minion Pro">
\t\t<Font Self="di41FontnMinion Pro Regular" FontFamily="Minion Pro" Name="Minion Pro Regular" PostScriptName="MinionPro-Regular" Status="Installed" FontStyleName="Regular" FontType="OpenTypeCFF" WritingScript="0" FullName="Minion Pro" FullNameNative="Minion Pro" FontStyleNameNative="Regular" PlatformName="$ID/" Version="Version 2.112;PS 2.000;hotconv 1.0.70;makeotf.lib2.5.5900" TypekitID="$ID/" />
\t</FontFamily>
\t<FontFamily Self="dia0" Name="Myriad Pro">
\t\t<Font Self="dia0FontnMyriad Pro Regular" FontFamily="Myriad Pro" Name="Myriad Pro Regular" PostScriptName="MyriadPro-Regular" Status="Installed" FontStyleName="Regular" FontType="OpenTypeCFF" WritingScript="0" FullName="Myriad Pro" FullNameNative="Myriad Pro" FontStyleNameNative="Regular" PlatformName="$ID/" Version="Version 2.106;PS 2.000;hotconv 1.0.70;makeotf.lib2.5.58329" TypekitID="$ID/" />
\t\t<Font Self="dia0FontnMyriad Pro Bold" FontFamily="Myriad Pro" Name="Myriad Pro Bold" PostScriptName="MyriadPro-Bold" Status="Installed" FontStyleName="Bold" FontType="OpenTypeCFF" WritingScript="0" FullName="Myriad Pro Bold" FullNameNative="Myriad Pro Bold" FontStyleNameNative="Bold" PlatformName="$ID/" Version="Version 2.106;PS 2.000;hotconv 1.0.70;makeotf.lib2.5.58329" TypekitID="$ID/" />
\t\t<Font Self="dia0FontnMyriad Pro Italic" FontFamily="Myriad Pro" Name="Myriad Pro Italic" PostScriptName="MyriadPro-It" Status="Installed" FontStyleName="Italic" FontType="OpenTypeCFF" WritingScript="0" FullName="Myriad Pro Italic" FullNameNative="Myriad Pro Italic" FontStyleNameNative="Italic" PlatformName="$ID/" Version="Version 2.106;PS 2.000;hotconv 1.0.70;makeotf.lib2.5.58329" TypekitID="$ID/" />
\t</FontFamily>
</idPkg:Fonts>"""

# ---------------------------------------------------------------------------
# Styles.xml — paragraph, character, object styles
# ---------------------------------------------------------------------------

STYLES_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<RootCharacterStyleGroup Self="u82">
\t\t<CharacterStyle Self="CharacterStyle/$ID/[No character style]" Imported="false" SplitDocument="false" EmitCss="true" StyleUniqueId="$ID/" IncludeClass="true" ExtendedKeyboardShortcut="0 0 0" EpubAriaRole="" Name="$ID/[No character style]" />
\t</RootCharacterStyleGroup>
\t<RootParagraphStyleGroup Self="u81">
\t\t<ParagraphStyle Self="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[No paragraph style]" Imported="false" SplitDocument="false" EmitCss="true" StyleUniqueId="$ID/" IncludeClass="true" ExtendedKeyboardShortcut="0 0 0" EpubAriaRole="" EmptyNestedStyles="true" EmptyLineStyles="true" EmptyGrepStyles="true" FillColor="Color/Black" FontStyle="Regular" PointSize="12" Justification="LeftAlign" Composer="HL Composer">
\t\t\t<Properties>
\t\t\t\t<AppliedFont type="string">Minion Pro</AppliedFont>
\t\t\t\t<Leading type="enumeration">Auto</Leading>
\t\t\t</Properties>
\t\t</ParagraphStyle>
\t\t<ParagraphStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle" Imported="false" NextStyle="ParagraphStyle/$ID/NormalParagraphStyle" SplitDocument="false" EmitCss="true" StyleUniqueId="nps1" IncludeClass="true" ExtendedKeyboardShortcut="0 0 0" EpubAriaRole="" EmptyNestedStyles="true" EmptyLineStyles="true" EmptyGrepStyles="true" KeyboardShortcut="0 0">
\t\t\t<Properties>
\t\t\t\t<BasedOn type="string">$ID/[No paragraph style]</BasedOn>
\t\t\t</Properties>
\t\t</ParagraphStyle>
\t</RootParagraphStyleGroup>
\t<TOCStyle Self="TOCStyle/$ID/DefaultTOCStyleName" TitleStyle="ParagraphStyle/$ID/[No paragraph style]" Title="Contents" Name="$ID/DefaultTOCStyleName" RunIn="false" IncludeHidden="false" IncludeBookDocuments="false" CreateBookmarks="true" SetStoryDirection="Horizontal" NumberedParagraphs="IncludeFullParagraph" MakeAnchor="false" RemoveForcedLineBreak="false" />
\t<RootCellStyleGroup Self="u91">
\t\t<CellStyle Self="CellStyle/$ID/[None]" AppliedParagraphStyle="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[None]" />
\t</RootCellStyleGroup>
\t<RootTableStyleGroup Self="u93">
\t\t<TableStyle Self="TableStyle/$ID/[No table style]" Name="$ID/[No table style]" />
\t\t<TableStyle Self="TableStyle/$ID/[Basic Table]" ExtendedKeyboardShortcut="0 0 0" Name="$ID/[Basic Table]" KeyboardShortcut="0 0">
\t\t\t<Properties>
\t\t\t\t<BasedOn type="string">$ID/[No table style]</BasedOn>
\t\t\t</Properties>
\t\t</TableStyle>
\t</RootTableStyleGroup>
\t<RootObjectStyleGroup Self="u9c">
\t\t<ObjectStyle Self="ObjectStyle/$ID/[None]" Name="$ID/[None]" AppliedParagraphStyle="ParagraphStyle/$ID/[No paragraph style]" FillColor="Swatch/None" StrokeWeight="0" StrokeColor="Swatch/None">
\t\t\t<TextFramePreference TextColumnCount="1" TextColumnGutter="12" VerticalJustification="TopAlign" />
\t\t\t<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" FrameType="TextFrameType" StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection" />
\t\t</ObjectStyle>
\t\t<ObjectStyle Self="ObjectStyle/$ID/[Normal Graphics Frame]" Name="$ID/[Normal Graphics Frame]" StrokeColor="Color/Black" StrokeWeight="1" FillColor="Swatch/None">
\t\t\t<Properties>
\t\t\t\t<BasedOn type="string">$ID/[None]</BasedOn>
\t\t\t</Properties>
\t\t</ObjectStyle>
\t\t<ObjectStyle Self="ObjectStyle/$ID/[Normal Text Frame]" Name="$ID/[Normal Text Frame]" StrokeWeight="0" StrokeColor="Swatch/None" FillColor="Swatch/None" AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle">
\t\t\t<Properties>
\t\t\t\t<BasedOn type="string">$ID/[None]</BasedOn>
\t\t\t</Properties>
\t\t\t<TextFramePreference TextColumnCount="1" TextColumnGutter="12" VerticalJustification="TopAlign" />
\t\t</ObjectStyle>
\t</RootObjectStyleGroup>
\t<TrapPreset Self="TrapPreset/$ID/kDefaultTrapStyleName" Name="$ID/kDefaultTrapStyleName" DefaultTrapWidth="0.25" BlackWidth="0.5" />
</idPkg:Styles>"""

# ---------------------------------------------------------------------------
# Preferences.xml — document, margin, text preferences
# ---------------------------------------------------------------------------

PREFERENCES_XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Preferences xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2">
\t<DocumentPreference PageHeight="{ph}" PageWidth="{pw}" PagesPerDocument="1" FacingPages="true" DocumentBleedTopOffset="0" DocumentBleedBottomOffset="0" DocumentBleedInsideOrLeftOffset="0" DocumentBleedOutsideOrRightOffset="0" DocumentBleedUniformSize="true" SlugTopOffset="0" SlugBottomOffset="0" SlugInsideOrLeftOffset="0" SlugRightOrOutsideOffset="0" DocumentSlugUniformSize="false" PreserveLayoutWhenShuffling="true" AllowPageShuffle="true" OverprintBlack="true" PageBinding="LeftToRight" ColumnDirection="Horizontal" Intent="PrintIntent" />
\t<MarginPreference ColumnCount="1" ColumnGutter="12" Top="36" Bottom="36" Left="36" Right="36" ColumnDirection="Horizontal" />
\t<TextPreference TypographersQuotes="true" SmallCap="70" SuperscriptSize="58.3" SuperscriptPosition="33.3" SubscriptSize="58.3" SubscriptPosition="33.3" />
\t<TextDefault AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle" AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" FontStyle="Regular" PointSize="12" FillColor="Color/Black" StrokeColor="Swatch/None" AppliedLanguage="$ID/English: USA">
\t\t<Properties>
\t\t\t<AppliedFont type="string">Minion Pro</AppliedFont>
\t\t\t<Leading type="enumeration">Auto</Leading>
\t\t</Properties>
\t</TextDefault>
\t<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" FrameType="TextFrameType" StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection" />
\t<TextFramePreference TextColumnCount="1" TextColumnGutter="12" VerticalJustification="TopAlign">
\t\t<Properties>
\t\t\t<InsetSpacing type="list">
\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t\t<ListItem type="unit">0</ListItem>
\t\t\t</InsetSpacing>
\t\t</Properties>
\t</TextFramePreference>
\t<ViewPreference HorizontalMeasurementUnits="Points" VerticalMeasurementUnits="Points" PointsPerInch="72" />
\t<TransparencyPreference BlendingSpace="CMYK" GlobalLightAngle="120" GlobalLightAltitude="30" />
\t<PageItemDefault AppliedGraphicObjectStyle="ObjectStyle/$ID/[Normal Graphics Frame]" AppliedTextObjectStyle="ObjectStyle/$ID/[Normal Text Frame]" FillColor="Swatch/None" StrokeColor="Swatch/None" StrokeWeight="1" />
</idPkg:Preferences>"""


def _preferences_xml(pw: float = PAGE_W_PT, ph: float = PAGE_H_PT) -> str:
    return PREFERENCES_XML_TEMPLATE.format(pw=int(pw), ph=int(ph))


# ---------------------------------------------------------------------------
# Metadata.xml (XMP)
# ---------------------------------------------------------------------------

def _metadata_xml() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    iid = f"xmp.iid:{uuid.uuid4()}"
    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Newsflow IDML Generator">
   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about=""
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:xmp="http://ns.adobe.com/xap/1.0/"
            xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">
         <dc:format>application/x-indesign</dc:format>
         <xmp:CreatorTool>Newsflow IDML Generator</xmp:CreatorTool>
         <xmp:CreateDate>{now}</xmp:CreateDate>
         <xmp:MetadataDate>{now}</xmp:MetadataDate>
         <xmp:ModifyDate>{now}</xmp:ModifyDate>
         <xmpMM:InstanceID>{iid}</xmpMM:InstanceID>
         <xmpMM:DocumentID>{iid}</xmpMM:DocumentID>
         <xmpMM:OriginalDocumentID>{iid}</xmpMM:OriginalDocumentID>
      </rdf:Description>
   </rdf:RDF>
</x:xmpmeta>
<?xpacket end="r"?>"""


# ---------------------------------------------------------------------------
# designmap.xml builder
# ---------------------------------------------------------------------------

def _designmap_xml(story_ids: list[str], pw: float = PAGE_W_PT, ph: float = PAGE_H_PT) -> str:
    story_list = " ".join(story_ids) + " ub3"
    story_refs = "\n".join(
        f'\t<idPkg:Story src="Stories/Story_{sid}.xml" />'
        for sid in story_ids
    )

    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<?aid style="50" type="document" readerVersion="6.0" featureSet="257" product="21.2(30)" ?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2" Self="d" StoryList="{story_list}" Name="Article" ZeroPoint="0 0" ActiveLayer="uce" CMYKProfile="U.S. Web Coated (SWOP) v2" RGBProfile="sRGB IEC61966-2.1" SolidColorIntent="UseColorSettings" AfterBlendingIntent="UseColorSettings" DefaultImageIntent="UseColorSettings" RGBPolicy="PreserveEmbeddedProfiles" CMYKPolicy="CombinationOfPreserveAndSafeCmyk" AccurateLABSpots="false">
\t<Language Self="Language/$ID/[No Language]" Name="$ID/[No Language]" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/[No Language]" SublanguageName="$ID/[No Language]" Id="0" HyphenationVendor="$ID/" SpellingVendor="$ID/" />
\t<Language Self="Language/$ID/English%3a USA" Name="$ID/English: USA" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/English" SublanguageName="$ID/USA" Id="269" HyphenationVendor="Hunspell" SpellingVendor="Hunspell" />
\t<Language Self="Language/$ID/English%3a UK" Name="$ID/English: UK" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/English" SublanguageName="$ID/UK" Id="525" HyphenationVendor="Hunspell" SpellingVendor="Hunspell" />
\t<Language Self="Language/$ID/or_IN" Name="$ID/or_IN" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/" SublanguageName="$ID/" Id="348" HyphenationVendor="Hunspell" SpellingVendor="Hunspell" />
\t<Language Self="Language/$ID/hi_IN" Name="$ID/hi_IN" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/" SublanguageName="$ID/" Id="348" HyphenationVendor="Hunspell" SpellingVendor="Hunspell" />
\t<idPkg:Graphic src="Resources/Graphic.xml" />
\t<idPkg:Fonts src="Resources/Fonts.xml" />
\t<idPkg:Styles src="Resources/Styles.xml" />
\t<NumberingList Self="NumberingList/$ID/[Default]" Name="$ID/[Default]" ContinueNumbersAcrossStories="false" ContinueNumbersAcrossDocuments="false" />
\t<NamedGrid Self="NamedGrid/$ID/[Page Grid]" Name="$ID/[Page Grid]">
\t\t<GridDataInformation FontStyle="Regular" PointSize="12" CharacterAki="0" LineAki="9" HorizontalScale="100" VerticalScale="100" LineAlignment="LeftOrTopLineJustify" GridAlignment="AlignEmCenter" CharacterAlignment="AlignEmCenter">
\t\t\t<Properties>
\t\t\t\t<AppliedFont type="string">Minion Pro</AppliedFont>
\t\t\t</Properties>
\t\t</GridDataInformation>
\t</NamedGrid>
\t<idPkg:Preferences src="Resources/Preferences.xml" />
\t<EndnoteOption EndnoteTitle="Endnotes" EndnoteTitleStyle="ParagraphStyle/$ID/NormalParagraphStyle" StartEndnoteNumberAt="1" EndnoteMarkerStyle="CharacterStyle/$ID/[No character style]" EndnoteTextStyle="ParagraphStyle/$ID/NormalParagraphStyle" EndnoteSeparatorText="&#x9;" EndnotePrefix="" EndnoteSuffix="">
\t\t<Properties>
\t\t\t<EndnoteNumberingStyle type="enumeration">Arabic</EndnoteNumberingStyle>
\t\t\t<RestartEndnoteNumbering type="enumeration">Continuous</RestartEndnoteNumbering>
\t\t\t<EndnoteMarkerPositioning type="enumeration">SuperscriptMarker</EndnoteMarkerPositioning>
\t\t\t<ScopeValue type="enumeration">EndnoteDocumentScope</ScopeValue>
\t\t\t<FrameCreateOption type="enumeration">NewPage</FrameCreateOption>
\t\t\t<ShowEndnotePrefixSuffix type="enumeration">NoPrefixSuffix</ShowEndnotePrefixSuffix>
\t\t</Properties>
\t</EndnoteOption>
\t<TextVariable Self="dTextVariablenCreation Date" Name="Creation Date" VariableType="CreationDateType">
\t\t<DateVariablePreference TextBefore="" Format="MM/dd/yy" TextAfter="" />
\t</TextVariable>
\t<TextVariable Self="dTextVariablenModification Date" Name="Modification Date" VariableType="ModificationDateType">
\t\t<DateVariablePreference TextBefore="" Format="MMMM d, yyyy h:mm aa" TextAfter="" />
\t</TextVariable>
\t<TextVariable Self="dTextVariablenFile Name" Name="File Name" VariableType="FileNameType">
\t\t<FileNameVariablePreference TextBefore="" IncludePath="false" IncludeExtension="false" TextAfter="" />
\t</TextVariable>
\t<idPkg:Tags src="XML/Tags.xml" />
\t<Layer Self="uce" Name="Layer 1" Visible="true" Locked="false" IgnoreWrap="false" ShowGuides="true" LockGuides="false" UI="true" Expendable="true" Printable="true">
\t\t<Properties>
\t\t\t<LayerColor type="enumeration">LightBlue</LayerColor>
\t\t</Properties>
\t</Layer>
\t<idPkg:MasterSpread src="MasterSpreads/MasterSpread_ud8.xml" />
\t<idPkg:Spread src="Spreads/Spread_ud1.xml" />
\t<Section Self="ud7" Length="1" Name="" ContinueNumbering="true" IncludeSectionPrefix="false" Marker="" PageStart="ud6" SectionPrefix="" AlternateLayoutLength="1" AlternateLayout="Letter V">
\t\t<Properties>
\t\t\t<PageNumberStyle type="enumeration">Arabic</PageNumberStyle>
\t\t</Properties>
\t</Section>
\t<DocumentUser Self="dDocumentUser0" UserName="$ID/Unknown User Name">
\t\t<Properties>
\t\t\t<UserColor type="enumeration">Gold</UserColor>
\t\t</Properties>
\t</DocumentUser>
\t<idPkg:BackingStory src="XML/BackingStory.xml" />
{story_refs}
\t<ColorGroup Self="ColorGroup/[Root Color Group]" Name="[Root Color Group]" IsRootColorGroup="true">
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch0" SwatchItemRef="Swatch/None" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch1" SwatchItemRef="Color/Registration" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch2" SwatchItemRef="Color/Paper" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch3" SwatchItemRef="Color/Black" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch4" SwatchItemRef="Color/C=100 M=0 Y=0 K=0" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch5" SwatchItemRef="Color/C=0 M=100 Y=0 K=0" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch6" SwatchItemRef="Color/C=0 M=0 Y=100 K=0" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch7" SwatchItemRef="Color/C=15 M=100 Y=100 K=0" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch8" SwatchItemRef="Color/C=75 M=5 Y=100 K=0" />
\t\t<ColorGroupSwatch Self="u18ColorGroupSwatch9" SwatchItemRef="Color/C=100 M=90 Y=10 K=0" />
\t</ColorGroup>
\t<ABullet Self="dABullet0" CharacterType="UnicodeOnly" CharacterValue="8226">
\t\t<Properties>
\t\t\t<BulletsFont type="string">$ID/</BulletsFont>
\t\t\t<BulletsFontStyle type="string">$ID/</BulletsFontStyle>
\t\t</Properties>
\t</ABullet>
\t<Assignment Self="udf" Name="$ID/UnassignedInCopy" UserName="$ID/" ExportOptions="AssignedSpreads" IncludeLinksWhenPackage="true" FilePath="$ID/">
\t\t<Properties>
\t\t\t<FrameColor type="enumeration">Nothing</FrameColor>
\t\t</Properties>
\t</Assignment>
</Document>"""


# ---------------------------------------------------------------------------
# Story XML builder
# ---------------------------------------------------------------------------

def _story_xml(story_id: str, paragraphs: list[dict]) -> str:
    """Build a Story XML file.

    Each paragraph dict: {text, point_size, justification, fill_color, font_style}
    """
    para_xml_parts = []
    for p in paragraphs:
        text = xml_escape(p.get("text", ""))
        pt = p.get("point_size", 12)
        just = p.get("justification", "LeftAlign")
        color = p.get("fill_color", "Color/Black")
        style = p.get("font_style", "Regular")

        # Split on newlines for multi-line paragraphs
        lines = text.split("\n") if text else [""]
        content_parts = []
        for i, line in enumerate(lines):
            content_parts.append(f"\t\t\t\t<Content>{line}</Content>")
            if i < len(lines) - 1:
                content_parts.append('\t\t\t\t<Br />')
        content_xml = "\n".join(content_parts)

        para_xml_parts.append(f"""\
\t\t<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle" Justification="{just}">
\t\t\t<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" FillColor="{color}" PointSize="{pt}" FontStyle="{style}">
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
