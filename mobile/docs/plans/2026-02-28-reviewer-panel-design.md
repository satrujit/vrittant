# Vrittant Reviewer Panel — Design Document

**Date:** 2026-02-28
**Stack:** React 18 + Vite, React Router v6, @hello-pangea/dnd, Lucide React, CSS Modules
**Backend:** Existing FastAPI at 192.168.1.7:8000 (shared with Flutter reporter app)

## Architecture

Standalone React SPA in `/reviewer-panel/` at the project root. Connects to the same FastAPI backend. Desktop-first, light theme only (tokenized via CSS custom properties). Full i18n — every UI string referenced from a locale table (`en`, `or` for Odia).

## Screens

### 1. Dashboard (Report Review Queue)
- Shows stories submitted in the **last 24 hours only**
- Stats bar: Pending Review, Reviewed Today, Avg. AI Accuracy, Total Published
- Filterable/searchable table: Reporter, Subject, Time, Category chip, Status, Action
- Pagination for high volume (300+ reporters)
- AI insight banner at bottom

### 2. All Stories (Archive)
- Stories older than 24 hours + all historical stories
- **Semantic search** — natural language query input that searches across headline, body text, category, reporter
- Filters: status, category, date range, reporter
- Same table layout as dashboard

### 3. Reporters
- Card grid of reporters with avatar (initials), name, area, org, submission count
- Click → filtered story list for that reporter
- Search by name/area

### 4. Review Editor
- **Text-only** — no source transcript panel
- Clean editable text area for proofreading
- Right sidebar: metadata (category, status, priority, location), action buttons
- Actions: Approve, Reject (with reason), Request Changes
- Export: "Export to InDesign (ICML)" and "Export to Social Media"

### 5. Page Buckets (Kanban)
- Drag-and-drop columns by category
- Cards: headline, snippet, reporter, time, status badge
- "+ New Bucket" for custom categories
- Bottom toolbar: filters, sort, "Publish Reports" CTA

### 6. Social Media Export Panel
- Platform preview cards (Twitter/X, Facebook, Instagram)
- Auto-truncated summaries per platform limits
- Copy-to-clipboard per platform
- Image selection from story media

## Theme Tokens (CSS Custom Properties)
Light theme only, but all values in `--vr-*` custom properties for maintainability.

## Internationalization
All UI strings in `src/i18n/locales/{en,or}.json`. React context provider for locale switching. No hardcoded text in components.

## Export
- ICML generation for InDesign (client-side XML construction)
- Social media panel with platform-specific formatting
