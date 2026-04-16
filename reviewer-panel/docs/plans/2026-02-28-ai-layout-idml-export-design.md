# AI Auto-Layout + IDML Export — Design Document

**Date:** 2026-02-28
**Status:** Approved

## Overview

Two features added to the Page Layout tab in ReviewPage:

1. **AI Auto-Layout** — GPT-4o analyzes story content and generates optimal newspaper zone layout automatically
2. **IDML Export** — Export the canvas layout as a full-fidelity InDesign package (.idml) with positioned text frames, styles, and colors

## Decisions

| Decision | Choice |
|----------|--------|
| AI input | Content-only analysis (headline length, paragraphs, images, category) |
| AI trigger | On-demand "Auto Layout" button |
| AI provider | OpenAI GPT-4o |
| IDML generation | Backend Python (from scratch, no external libs) |
| Creative elements | Pullquotes, highlights, color accents for longer stories |
| Voice refinement | Deferred to follow-up |

---

## Feature 1: AI Auto-Layout

### Data Flow

```
[Auto Layout] button click
       │
       ▼
POST /admin/stories/{id}/auto-layout
Body: { paper_size, width_mm, height_mm }
       │
       ▼ (Backend)
1. Fetch story from DB (headline, paragraphs, images)
2. Compute metrics:
   - headline_chars, paragraph_count, total_words
   - image_count, category
3. Build GPT prompt with page dims + metrics + zone schema + layout rules
4. Call OpenAI GPT-4o → returns zones JSON
5. Validate zones (bounds, no overlaps)
6. Return { zones: [...] }
       │
       ▼
Frontend: setLayoutTemplate({...zones}) → canvas re-renders
```

### Expanded Zone Types

| Type | Purpose | When Used |
|------|---------|-----------|
| `masthead` | Newspaper name at top | Always |
| `headline` | Story headline | Always |
| `body` | Story paragraphs, multi-column | Always |
| `image` | Image placeholder | When images exist |
| `pullquote` | Key sentence on colored background | Stories > 300 words |
| `highlight` | Stat/fact box with accent | Stories > 500 words |
| `divider` | Decorative color band | Between sections |
| `sidebar` | Secondary info box | Long-form stories |

### Color Support (New Zone Properties)

```json
{
  "bg_color": "#FEF3C7",
  "text_color": "#92400E",
  "border_color": "#F59E0B",
  "text": "AI-selected impactful sentence"
}
```

Category-based color palettes:
- Politics: blue accents (#1E40AF, #DBEAFE)
- Sports: green accents (#166534, #DCFCE7)
- Crime: red accents (#991B1B, #FEE2E2)
- Business: amber accents (#92400E, #FEF3C7)
- Entertainment: purple accents (#6B21A8, #F3E8FF)
- Default: neutral grey (#374151, #F3F4F6)

### GPT Prompt Structure

```
System: You are a newspaper page layout designer. Given story
metrics and page dimensions, generate an optimal zone layout
as a JSON array.

Rules:
- Masthead always at top, full width, ~30mm height
- Headline below masthead, prominent size based on char count
- Body text fills remaining space, 2-4 columns for long stories
- Images get dedicated zones (never overlap text)
- Margins: 10mm on all sides, column gap: 4mm minimum
- Stories > 300 words: add a pullquote (pick most impactful sentence)
- Stories > 500 words: add pullquote + highlight box for key stats
- Use category-appropriate colors, 2-3 accent colors max
- Be creative with layout — vary zone placement, not always top-to-bottom

Output: JSON array of zone objects matching schema.

User: Page: {width_mm}x{height_mm}mm ({paper_size})
Story: headline="{headline}" ({headline_chars} chars)
       {paragraph_count} paragraphs, {total_words} words
       {image_count} images, category={category}
Paragraphs: [first 200 chars of each paragraph for context]
```

### Validation Rules (Backend)

- All zones must fit within page bounds (x + width <= page width, etc.)
- No zone smaller than 20mm in any dimension
- Required zones: at least masthead + headline + body
- Zone IDs must be unique
- Colors must be valid hex codes

---

## Feature 2: IDML Export

### IDML Package Structure

```
story-export.idml (ZIP)
├── mimetype
├── META-INF/container.xml
├── designmap.xml
├── Resources/
│   ├── Styles.xml          → Paragraph + character styles
│   └── Graphic.xml         → Color swatches from zone colors
├── Spreads/
│   └── Spread_1.xml        → Page dims + text frame positions
│       ├── TextFrame per zone (x, y, width, height in points)
│       └── Rectangle for colored backgrounds
└── Stories/
    └── Story_{zone_id}.xml → Text content + style references
```

### Coordinate Conversion

| Canvas (mm) | IDML (points) | Factor |
|-------------|---------------|--------|
| x_mm, y_mm | Transform | x 2.8346 |
| width_mm, height_mm | Frame size | x 2.8346 |
| font_size_pt | PointSize | Direct |
| columns | TextFrameColumn | Direct |
| bg_color (hex) | FillColor swatch | Hex → CMYK approx |

### Backend Endpoint

```
POST /admin/stories/{id}/export-idml
Body: { layout_config: { width_mm, height_mm, zones: [...] } }
Response: application/octet-stream (downloadable .idml file)
Content-Disposition: attachment; filename="{headline}-layout.idml"
```

### Python Implementation

- Use stdlib only: `zipfile`, `xml.etree.ElementTree`
- Build each XML file from string templates
- Hex → CMYK conversion: simple approximation formula
- Stream ZIP response via FastAPI `StreamingResponse`

---

## Frontend UX

Two new buttons in LayoutConfigPanel (bottom of config panel):

- **Auto Layout** (sparkle icon) — calls auto-layout endpoint, shows spinner, replaces zones
- **Export IDML** (download icon) — calls export-idml endpoint, triggers browser download

Canvas renderer updates:
- Support `bg_color` → `ctx.fillStyle` rectangle behind zone
- Support `text_color` → override text fill color
- Support `border_color` → left-side accent bar for pullquotes
- Support `text` field → render custom text for pullquote/highlight zones
- New draw functions: `drawPullquote()`, `drawHighlight()`, `drawDivider()`, `drawSidebar()`

---

## Backend Configuration

- OpenAI API key stored in `app/config.py` as `OPENAI_API_KEY` env var
- New dependency: `openai` Python package (or direct HTTP via `httpx`)
- No other external dependencies needed

---

## Out of Scope

- Voice commands to refine layout (follow-up feature)
- Image upload/placement within zones
- Multi-page layouts
- InDesign template matching
