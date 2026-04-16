/**
 * Vrittant — InDesign ICML (InCopy Markup Language) Export Utility
 *
 * Generates a valid ICML XML document from a story object that can be
 * placed directly into an InDesign layout.
 */

/**
 * Escapes special XML characters in a string.
 */
function escapeXml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Generates a complete ICML XML string from a story object.
 *
 * @param {object} story
 * @param {string} story.headline
 * @param {Array}  story.paragraphs — each { text: string }
 * @param {string} story.category
 * @param {object} story.reporter — { name: string }
 * @param {string} [story.bodyText] — fallback if paragraphs is missing
 * @returns {string} Valid ICML XML document
 */
export function generateICML(story) {
  if (!story) return '';

  const headline = escapeXml(story.headline || 'Untitled');
  const category = escapeXml(story.category || '');
  const reporter = escapeXml(story.reporter?.name || '');
  const location = escapeXml(story.location || '');

  // Build paragraph content from paragraphs array or bodyText fallback
  const bodyParagraphs = story.paragraphs
    ? story.paragraphs.map((p) => escapeXml(p.text))
    : (story.bodyText || '').split('\n\n').map((t) => escapeXml(t));

  const bodyContent = bodyParagraphs
    .map(
      (text) => `
      <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/BodyText">
        <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/BodyText">
          <Content>${text}</Content>
        </CharacterStyleRange>
        <Br/>
      </ParagraphStyleRange>`
    )
    .join('\n');

  const icml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<?aid style="50" type="snippet" readerVersion="6.0" featureSet="513" product="8.0(370)" ?>
<?aid SnsijdxaqcxEa ?>
<Document DOMVersion="8.0" Self="d">

  <!-- ═══ Paragraph Style Definitions ═══ -->
  <RootParagraphStyleGroup Self="vrittant_psg">
    <ParagraphStyle Self="ParagraphStyle/Title"
                    Name="Title"
                    FontStyle="Bold"
                    PointSize="28"
                    Leading="34"
                    SpaceAfter="12"
                    Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Byline"
                    Name="Byline"
                    FontStyle="Italic"
                    PointSize="11"
                    Leading="14"
                    SpaceAfter="6"
                    Justification="LeftAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Category"
                    Name="Category"
                    FontStyle="Bold"
                    PointSize="9"
                    Leading="12"
                    SpaceAfter="16"
                    Justification="LeftAlign"
                    FillColor="Color/CategoryAccent"
                    Capitalization="AllCaps"/>
    <ParagraphStyle Self="ParagraphStyle/BodyText"
                    Name="BodyText"
                    FontStyle="Regular"
                    PointSize="11"
                    Leading="16"
                    SpaceAfter="10"
                    Justification="LeftJustify"/>
  </RootParagraphStyleGroup>

  <!-- ═══ Character Style Definitions ═══ -->
  <RootCharacterStyleGroup Self="vrittant_csg">
    <CharacterStyle Self="CharacterStyle/Title"
                    Name="Title"
                    FontStyle="Bold"
                    PointSize="28"
                    FillColor="Color/k100"/>
    <CharacterStyle Self="CharacterStyle/Byline"
                    Name="Byline"
                    FontStyle="Italic"
                    PointSize="11"
                    FillColor="Color/k60"/>
    <CharacterStyle Self="CharacterStyle/Category"
                    Name="Category"
                    FontStyle="Bold"
                    PointSize="9"
                    FillColor="Color/CategoryAccent"
                    Capitalization="AllCaps"/>
    <CharacterStyle Self="CharacterStyle/BodyText"
                    Name="BodyText"
                    FontStyle="Regular"
                    PointSize="11"
                    FillColor="Color/k100"/>
  </RootCharacterStyleGroup>

  <!-- ═══ Story Content ═══ -->
  <Story Self="vrittant_story" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="${headline}">

    <!-- Category -->
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Category">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/Category">
        <Content>${category}</Content>
      </CharacterStyleRange>
      <Br/>
    </ParagraphStyleRange>

    <!-- Headline -->
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Title">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/Title">
        <Content>${headline}</Content>
      </CharacterStyleRange>
      <Br/>
    </ParagraphStyleRange>

    <!-- Byline -->
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Byline">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/Byline">
        <Content>By ${reporter}${location ? `, ${location}` : ''}</Content>
      </CharacterStyleRange>
      <Br/>
    </ParagraphStyleRange>

    <!-- Body Paragraphs -->
${bodyContent}

  </Story>
</Document>`;

  return icml;
}

export default generateICML;
