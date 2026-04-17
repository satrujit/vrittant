"""Static IDML header/document XML — templates and per-document builders.

Includes the manifest mimetype, container/META-INF, fonts, graphic, styles,
tags, backing story, master spread, preferences, designmap, and metadata.
"""

import uuid
from datetime import datetime, timezone

from ._constants import MARGIN_PT, PAGE_H_PT, PAGE_W_PT

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
\t<FontFamily Self="dib0" Name="Noto Sans Oriya">
\t\t<Font Self="dib0FontnNoto Sans Oriya Regular" FontFamily="Noto Sans Oriya" Name="Noto Sans Oriya Regular" PostScriptName="NotoSansOriya" Status="Installed" FontStyleName="Regular" FontType="OpenTypeTrueType" WritingScript="12" FullName="Noto Sans Oriya" FullNameNative="Noto Sans Oriya" FontStyleNameNative="Regular" PlatformName="$ID/" />
\t\t<Font Self="dib0FontnNoto Sans Oriya Bold" FontFamily="Noto Sans Oriya" Name="Noto Sans Oriya Bold" PostScriptName="NotoSansOriya-Bold" Status="Installed" FontStyleName="Bold" FontType="OpenTypeTrueType" WritingScript="12" FullName="Noto Sans Oriya Bold" FullNameNative="Noto Sans Oriya Bold" FontStyleNameNative="Bold" PlatformName="$ID/" />
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
\t\t<ParagraphStyle Self="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[No paragraph style]" Imported="false" SplitDocument="false" EmitCss="true" StyleUniqueId="$ID/" IncludeClass="true" ExtendedKeyboardShortcut="0 0 0" EpubAriaRole="" EmptyNestedStyles="true" EmptyLineStyles="true" EmptyGrepStyles="true" FillColor="Color/Black" FontStyle="Regular" PointSize="12" Justification="LeftAlign" Composer="Adobe World-Ready Paragraph Composer">
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
\t<Language Self="Language/$ID/Oriya" Name="$ID/Oriya" SingleQuotes="&apos;&apos;" DoubleQuotes="&quot;&quot;" PrimaryLanguageName="$ID/Oriya" SublanguageName="$ID/" Id="348" HyphenationVendor="Hunspell" SpellingVendor="Hunspell" />
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
