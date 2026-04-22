# Vrittant UI Redesign

## Color Palette (extracted from reference)

| Token | Hex | Usage |
|-------|-----|-------|
| scaffoldBg | `#FFFFFF` | Main screens |
| warmBg | `#FEF7F2` | Story detail, notepad bg |
| cardBg | `#FFFFFF` | Cards |
| cardBorder | `#F0EBE6` | Subtle warm border |
| activeAccent | `#3D3B8E` | Left accent bar on active cards |
| primary (coral) | `#D4714A` | FAB, badges, links, actions |
| coralLight | `#FDEEE8` | Badge bg, light coral tint |
| headingDark | `#1C1917` | Titles, headlines |
| bodyText | `#44403C` | Paragraphs |
| mutedText | `#A8A29E` | Timestamps, metadata |
| sectionLabel | `#78716C` | Uppercase section labels |
| badgeBorderGray | `#D6D3D1` | PUBLISHED badge border |
| badgeTextGray | `#78716C` | PUBLISHED text |
| navInactive | `#A8A29E` | Bottom nav inactive |
| navActive | `#1C1917` | Bottom nav active |
| dividerCoral | `#D4714A` → `#E8A87C` | Gradient dividers |
| serifFont | Playfair Display | Story detail headlines |

## Changes by Screen

### 1. Global
- App name: "Vrittant" (replace all "NewsFlow" references)
- Remove ALL dark colored header blocks — white/cream bg headers only
- Bottom nav: 4 tabs: ଘର (HOME), ସବୁ ଖବର (ALL STORIES), ଫାଇଲ (FILES), ସେଟିଂସ (SETTINGS)
- Nav colors: dark active, gray inactive (no coral active)
- Floating coral mic FAB (bottom-right) replaces center mic in bottom bar on home

### 2. Home Screen
- Header: "Vrittant" in dark text (left), subtitle "GLOBAL REPORTER" in coral uppercase below
- Search icon + profile avatar (top-right)
- "ACTIVE PROJECTS" section: small uppercase coral label + "X Total" right
- Active cards: white bg, subtle border, LEFT indigo accent bar, headline, "IN PROGRESS" coral badge, "CONTINUE RECORDING" coral link with mic icon
- "ALL STORIES" section: uppercase label + "Filter" coral link right
- Story cards: headline + outlined status badge (PUBLISHED=gray-outlined, DRAFT=gray-outlined)
- Floating coral FAB (mic icon) bottom-right

### 3. All News Screen
- Kill dark header — white bg, "ସବୁ ଖବର" as normal title
- Sort stories by createdAt DESC before grouping (fixes duplicate date sections)
- Remove inline trash icons — swipe-to-delete only
- Date section labels: smaller, uppercase style
- Cards: same clean style as home

### 4. Login Screen
- Title: "Vrittant" (not NewsFlow)
- 6-box OTP input using Row of 6 individual TextField boxes
- Phone input: better styled with +91 prefix

### 5. Notepad Screen
- Use warmBg (#FEF7F2) as scaffold instead of white
- Keep existing layout, already has smaller buttons

### 6. Profile Screen
- Keep existing but update colors to match new palette

### 7. Theme Token Updates
- Update warmPastelTheme with exact extracted colors
- headerBg: white (not coral600)
- primary: #D4714A (muted coral, not #FF5733)
- headingColor: #1C1917
- bodyColor: #44403C
- navActiveColor: #1C1917 (dark, not coral)
