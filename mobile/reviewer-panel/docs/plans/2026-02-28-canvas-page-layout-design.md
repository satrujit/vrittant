# Canvas Page Layout Preview — Design Document

**Date:** 2026-02-28
**Status:** Approved

## Problem

Editors review and edit stories in a TipTap rich-text editor but have no way to
preview how the story will look when placed on an actual newspaper page. They
must mentally estimate column fit, headline sizing, and image placement before
exporting to InDesign.

## Solution

Add a **"Page Layout" tab** alongside the existing editor in ReviewPage. The tab
renders the story on an HTML Canvas using a configurable newspaper page template.
Editors can select a saved template, tweak layout controls, and see the story
text flow into columns in real time.

## Architecture

### Tab System (ReviewPage)

A tab bar above the editor area: **Editor | Page Layout**.

- **Editor tab** — existing TipTap editor (unchanged)
- **Page Layout tab** — canvas preview + config controls side-by-side

### Canvas Renderer

HTML `<canvas>` element that draws a scaled newspaper page.

**Rendering pipeline:**
1. Draw page background (white rectangle at template dimensions)
2. For each zone in the template config:
   - Draw zone border/guides (dashed lines)
   - Based on zone type:
     - `headline` — render story headline with configured font size, bold
     - `body` — flow story paragraphs into multi-column layout using
       `ctx.measureText()` for word wrapping and column breaks
     - `image` — draw story images scaled to fit the zone
     - `masthead` — render newspaper name/branding
3. Scale the entire canvas to fit the viewport (~600px tall for broadsheet)

**Text reflow algorithm:**
- Split paragraph text into words
- Measure word widths with `ctx.measureText()`
- Wrap into lines within column width
- When a column fills vertically, move to the next column
- When all columns in a zone fill, overflow is clipped (visual indicator)

**Odia text support:** Uses system fonts via canvas font stack
(`'Noto Sans Odia', sans-serif`).

### Config Controls Panel

Displayed to the right of the canvas when Page Layout tab is active.

**Controls:**
- **Template picker** — dropdown of saved templates
- **Page size** — preset (broadsheet 380×560mm, tabloid 280×430mm) or custom
- **Zone list** — each zone shows:
  - Type: headline | body | image | masthead (dropdown)
  - Position: x, y (mm, number inputs)
  - Size: width, height (mm, number inputs)
  - Columns: 1–5 (number input, body zones only)
  - Column gap: mm (number input)
  - Font size: pt (number input)
  - Label: freetext (admin-facing name)
- **Add zone** button
- **Remove zone** button (per zone)
- **"Save as Template"** button — saves current config as a new reusable template
- **"Reset to Template"** button — discards per-story overrides

Canvas re-renders on every config change (debounced ~100ms).

### Data Model

#### PageTemplate (new database table)

```
page_templates
  id          UUID PK
  name        String NOT NULL
  paper_size  String (broadsheet | tabloid | custom)
  width_mm    Float NOT NULL
  height_mm   Float NOT NULL
  zones       JSON NOT NULL  -- array of zone objects
  created_by  String FK -> users.id
  created_at  DateTime
  updated_at  DateTime
```

Zone object schema (inside `zones` JSON array):

```json
{
  "id": "zone-1",
  "type": "headline | body | image | masthead",
  "x_mm": 20,
  "y_mm": 40,
  "width_mm": 170,
  "height_mm": 30,
  "columns": 1,
  "column_gap_mm": 4,
  "font_size_pt": 10,
  "font_family": "serif",
  "label": "Lead Headline"
}
```

#### Per-story layout override

Add `layout_config` JSON column to `story_revisions` table. Stores the full
zone config if the editor tweaks the template for a specific story. `null` means
"use template as-is".

### API Endpoints

```
GET    /admin/templates          — list all templates
POST   /admin/templates          — create template
GET    /admin/templates/:id      — get single template
PUT    /admin/templates/:id      — update template
DELETE /admin/templates/:id      — delete template
```

The existing PUT `/admin/stories/:id` endpoint already saves revision data.
`layout_config` will be included as an optional field in `AdminStoryUpdate`.

### Frontend Components

```
src/
  components/
    PageLayoutPreview/
      PageLayoutCanvas.jsx      — canvas rendering logic
      LayoutConfigPanel.jsx     — config controls panel
      ZoneEditor.jsx            — single zone config form
      TemplateSelector.jsx      — template picker dropdown
      useCanvasRenderer.js      — hook: text reflow + drawing
  pages/
    ReviewPage.jsx              — add tab bar, integrate PageLayoutPreview
```

### Data Flow

1. Editor opens Page Layout tab
2. Frontend fetches available templates from `/admin/templates`
3. Editor picks a template → zones loaded into state
4. Canvas renders story content into zones
5. Editor tweaks zone configs → canvas re-renders in real time
6. On save: if config differs from template, store override in
   `story_revisions.layout_config`
7. "Save as Template" → POST to `/admin/templates`

## Out of Scope (for now)

- PDF export from canvas (future: `canvas.toDataURL()` or jsPDF)
- ICML/InDesign export using template zones (future enhancement)
- Multiple stories per template (current: one story per preview)
- Drag-and-drop zone positioning (current: numeric inputs only)
