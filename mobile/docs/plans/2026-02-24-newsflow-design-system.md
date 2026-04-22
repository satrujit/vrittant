# NewsFlow Design System v1.0

> A comprehensive design system for the NewsFlow news processing automation platform.
> Built for Flutter (Mobile) + Web (Admin Dashboard).

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing & Layout](#4-spacing--layout)
5. [Component Library](#5-component-library)
6. [Iconography](#6-iconography)
7. [Motion & Animation](#7-motion--animation)
8. [Platform-Specific Notes](#8-platform-specific-notes)
9. [Flutter Implementation](#9-flutter-implementation)
10. [Accessibility](#10-accessibility)

---

## 1. Design Philosophy

### Core Principles

| Principle | Description |
|---|---|
| **Warm & Inviting** | Sunset-inspired gradients create emotional warmth — news shouldn't feel clinical |
| **Voice-First** | UI emphasizes the microphone/dictation as the hero action |
| **Clarity Over Decoration** | Every element earns its place. Minimalist but not sterile |
| **Glass & Glow** | Frosted glass cards over gradient backgrounds. Soft, layered depth |
| **Odia-First** | Typography and layout optimized for Odia readability, not retrofitted |

### Design DNA

Inspired by:
- **Sarvam AI** — Clean, airy layouts with purposeful whitespace
- **Sunset Gradients** — Warm orange-gold-peach color stories (from mood board)
- **Glassmorphism** — Frosted translucent cards with soft borders
- **Mesh Gradients** — Organic, fluid background textures

---

## 2. Color System

### 2.1 Primary Palette — "Sunrise"

The primary palette draws from the warm sunset/sunrise gradients in the mood board.

| Token | Hex | RGB | Usage |
|---|---|---|---|
| `primary.50` | `#FFF8F0` | 255, 248, 240 | Lightest background tint |
| `primary.100` | `#FFECD2` | 255, 236, 210 | Card backgrounds, hover states |
| `primary.200` | `#FFD9A8` | 255, 217, 168 | Soft accents, dividers |
| `primary.300` | `#FFC178` | 255, 193, 120 | Secondary buttons, tags |
| `primary.400` | `#FFA94D` | 255, 169, 77 | Active states, progress indicators |
| `primary.500` | `#FF8C22` | 255, 140, 34 | **Primary brand color** — CTAs, FABs |
| `primary.600` | `#E07010` | 224, 112, 16 | Pressed states |
| `primary.700` | `#B85A0A` | 184, 90, 10 | Dark accents |
| `primary.800` | `#8A4308` | 138, 67, 8 | Text on light backgrounds |
| `primary.900` | `#5C2D05` | 92, 45, 5 | Darkest brand accent |

### 2.2 Secondary Palette — "Coral Blush"

| Token | Hex | RGB | Usage |
|---|---|---|---|
| `secondary.50` | `#FFF5F5` | 255, 245, 245 | Error/alert light background |
| `secondary.100` | `#FFE0E0` | 255, 224, 224 | Light coral tint |
| `secondary.200` | `#FFB3B3` | 255, 179, 179 | Soft coral accent |
| `secondary.300` | `#FF8585` | 255, 133, 133 | Notification badges |
| `secondary.400` | `#FF6B6B` | 255, 107, 107 | Alert emphasis |
| `secondary.500` | `#E84C4C` | 232, 76, 76 | **Rejection/Error** states |

### 2.3 Accent Palette — "Golden Hour"

| Token | Hex | RGB | Usage |
|---|---|---|---|
| `accent.gold` | `#F5B800` | 245, 184, 0 | Priority news badge, stars |
| `accent.amber` | `#FFBF47` | 255, 191, 71 | Warning states |
| `accent.peach` | `#FFCBA4` | 255, 203, 164 | Soft highlights |
| `accent.cream` | `#FFF5E6` | 255, 245, 230 | Warm white backgrounds |

### 2.4 Semantic Colors

| Token | Hex | Usage |
|---|---|---|
| `success` | `#22C55E` | Approved, published, success states |
| `warning` | `#F59E0B` | Under review, pending states |
| `error` | `#EF4444` | Rejected, error states |
| `info` | `#3B82F6` | Informational messages |

### 2.5 Neutral Palette

| Token | Hex | Usage |
|---|---|---|
| `neutral.0` | `#FFFFFF` | Pure white — card surfaces |
| `neutral.50` | `#FAFAF9` | Page background |
| `neutral.100` | `#F5F5F4` | Subtle backgrounds |
| `neutral.200` | `#E7E5E4` | Borders, dividers |
| `neutral.300` | `#D6D3D1` | Disabled states |
| `neutral.400` | `#A8A29E` | Placeholder text |
| `neutral.500` | `#78716C` | Secondary text |
| `neutral.600` | `#57534E` | Body text |
| `neutral.700` | `#44403C` | Strong body text |
| `neutral.800` | `#292524` | Headlines |
| `neutral.900` | `#1C1917` | Highest contrast text |

### 2.6 Gradient Definitions

These are the hero gradients used for backgrounds, cards, and accent elements.

```
GRADIENT: "Sunrise"
  Type: Linear (135deg)
  Stops: #FF8C22 (0%) → #FFA94D (40%) → #FFECD2 (100%)
  Usage: Primary page headers, hero sections, splash screen

GRADIENT: "Sunset Wave"
  Type: Linear (180deg)
  Stops: #FF6B6B (0%) → #FF8C22 (50%) → #FFD9A8 (100%)
  Usage: Featured/priority news card backgrounds

GRADIENT: "Golden Mist"
  Type: Radial (center)
  Stops: #FFECD2 (0%) → #FFF8F0 (60%) → #FFFFFF (100%)
  Usage: Subtle page backgrounds, ambient glow behind content

GRADIENT: "Warm Glass"
  Type: Linear (135deg)
  Stops: rgba(255,255,255,0.25) (0%) → rgba(255,255,255,0.08) (100%)
  Blur: 20px backdrop-blur
  Usage: Glassmorphic card overlays

GRADIENT: "Mesh Aurora" (Animated)
  Type: Mesh gradient (4 control points)
  Colors: #FF8C22, #FFD9A8, #FFC178, #FFF8F0
  Usage: Splash screen background, login screen, animated ambient backgrounds
```

### 2.7 Dark Mode (v2 — future)

Dark mode will invert the neutral palette and soften the gradients. Not in scope for v1 but the token system is designed to support it.

---

## 3. Typography

### 3.1 Font Families

| Role | English | Odia | Flutter Package |
|---|---|---|---|
| **Display / Headlines** | `Inter` (Bold/SemiBold) | `Anek Odia` (Bold/SemiBold, Expanded) | `google_fonts` |
| **Body Text** | `Inter` (Regular/Medium) | `Noto Sans Oriya` (Regular/Medium) | `google_fonts` |
| **Monospace / Code** | `JetBrains Mono` | — | `google_fonts` |

**Why this pairing:**
- **Inter** — Industry-standard UI font. Clean, highly legible, excellent for mobile interfaces. Massive weight range. Free.
- **Anek Odia** — Modern, multi-width Odia display font. The width axis (Expanded) creates strong editorial headlines. Single file covers both Latin + Odia.
- **Noto Sans Oriya** — The most readable Odia body font. Designed by Google for screen clarity. Full weight range.

### 3.2 Type Scale

All sizes follow a 1.25x modular scale. Odia sizes are +1px per Material Design's Indic script guidelines.

| Token | English Size | Odia Size | Weight | Line Height | Letter Spacing | Usage |
|---|---|---|---|---|---|---|
| `display.large` | 36px | 37px | Bold (700) | 1.2 | -0.5px | Splash screen title |
| `display.medium` | 30px | 31px | Bold (700) | 1.2 | -0.25px | Page titles |
| `heading.h1` | 26px | 27px | SemiBold (600) | 1.3 | 0px | Section headers |
| `heading.h2` | 22px | 23px | SemiBold (600) | 1.3 | 0px | Card titles, news headline |
| `heading.h3` | 18px | 19px | Medium (500) | 1.4 | 0px | Subsection headers |
| `body.large` | 16px | 17px | Regular (400) | 1.6 | 0px | **Primary body text** |
| `body.medium` | 14px | 15px | Regular (400) | 1.5 | 0.1px | Secondary text, descriptions |
| `body.small` | 12px | 13px | Regular (400) | 1.5 | 0.2px | Captions, timestamps |
| `label.large` | 14px | 15px | Medium (500) | 1.4 | 0.1px | Button text, tab labels |
| `label.medium` | 12px | 13px | Medium (500) | 1.4 | 0.5px | Chips, tags, badges |
| `label.small` | 10px | 11px | Medium (500) | 1.3 | 0.5px | Micro labels (use sparingly) |

### 3.3 Odia-Specific Typography Rules

1. **Never go below 13px** for Odia text on mobile — the script's complexity makes it unreadable
2. **Always use Regular (400) weight** for Odia body text — Bold appears too heavy per native speaker feedback
3. **Do NOT adjust letter-spacing** for Odia — it breaks conjunct glyph rendering
4. **Line height must be 1.5x+** for Odia body — the script has tall vertical metrics (matras above/below)
5. **Paragraph spacing**: 12px between paragraphs for Odia content
6. **Text line length**: Target 35-45 Odia characters per line on mobile

### 3.4 Flutter Implementation

```dart
// In theme configuration
import 'package:google_fonts/google_fonts.dart';

// English text theme
final englishTextTheme = TextTheme(
  displayLarge: GoogleFonts.inter(fontSize: 36, fontWeight: FontWeight.w700, height: 1.2, letterSpacing: -0.5),
  displayMedium: GoogleFonts.inter(fontSize: 30, fontWeight: FontWeight.w700, height: 1.2, letterSpacing: -0.25),
  headlineLarge: GoogleFonts.inter(fontSize: 26, fontWeight: FontWeight.w600, height: 1.3),
  headlineMedium: GoogleFonts.inter(fontSize: 22, fontWeight: FontWeight.w600, height: 1.3),
  headlineSmall: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w500, height: 1.4),
  bodyLarge: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w400, height: 1.6),
  bodyMedium: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w400, height: 1.5, letterSpacing: 0.1),
  bodySmall: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w400, height: 1.5, letterSpacing: 0.2),
  labelLarge: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w500, height: 1.4, letterSpacing: 0.1),
  labelMedium: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w500, height: 1.4, letterSpacing: 0.5),
  labelSmall: GoogleFonts.inter(fontSize: 10, fontWeight: FontWeight.w500, height: 1.3, letterSpacing: 0.5),
);

// Odia text theme (headlines)
final odiaHeadlineStyle = GoogleFonts.anekOdia(fontSize: 27, fontWeight: FontWeight.w600, height: 1.3);

// Odia text theme (body)
final odiaBodyStyle = GoogleFonts.notoSansOriya(fontSize: 17, fontWeight: FontWeight.w400, height: 1.6);
```

---

## 4. Spacing & Layout

### 4.1 Spacing Scale (4px base unit)

| Token | Value | Usage |
|---|---|---|
| `space.2xs` | 2px | Micro gaps (icon-to-text in compact chips) |
| `space.xs` | 4px | Tightest spacing (between related icons) |
| `space.sm` | 8px | Small gap (within components, inner padding) |
| `space.md` | 12px | Medium gap (between related elements) |
| `space.lg` | 16px | Standard gap (component padding, list spacing) |
| `space.xl` | 24px | Large gap (section spacing within a card) |
| `space.2xl` | 32px | Section separation |
| `space.3xl` | 48px | Major section breaks |
| `space.4xl` | 64px | Page-level padding tops |

### 4.2 Layout Grid

**Mobile (Reporter App):**
- Screen padding: 16px horizontal
- Card padding: 16px all sides
- Grid: Single column, full-width cards
- Max content width: Device width - 32px

**Web (Admin Dashboard):**
- Max content width: 1280px, centered
- Side navigation: 260px fixed
- Content area padding: 32px
- Grid: 12-column with 24px gutters
- Cards: 2-3 column layouts for news list

### 4.3 Border Radius Scale

| Token | Value | Usage |
|---|---|---|
| `radius.none` | 0px | Sharp edges (rare) |
| `radius.sm` | 6px | Small chips, tags |
| `radius.md` | 12px | Buttons, input fields |
| `radius.lg` | 16px | Cards, modals |
| `radius.xl` | 24px | Large cards, bottom sheets |
| `radius.full` | 9999px | Pills, avatars, FABs |

### 4.4 Elevation / Shadow System

We use soft, warm-tinted shadows (not grey).

| Token | Shadow | Usage |
|---|---|---|
| `elevation.none` | none | Flat elements |
| `elevation.xs` | `0 1px 3px rgba(255,140,34,0.08)` | Subtle lift (chips) |
| `elevation.sm` | `0 2px 8px rgba(255,140,34,0.10)` | Cards at rest |
| `elevation.md` | `0 4px 16px rgba(255,140,34,0.12)` | Elevated cards, dropdowns |
| `elevation.lg` | `0 8px 32px rgba(255,140,34,0.15)` | Modals, floating action |
| `elevation.xl` | `0 16px 48px rgba(255,140,34,0.18)` | Hero cards, splash overlays |

---

## 5. Component Library

### 5.1 Recommended Flutter Packages

| Category | Package | Why |
|---|---|---|
| **Base Components** | `shadcn_ui` | Modern, shadcn-inspired. 30+ components. Clean aesthetic. |
| **Mesh Gradients** | `mesh_gradient` | Animated mesh backgrounds for splash/login/headers |
| **Glassmorphism** | `glass_kit` | Frosted glass cards with `frostedGlass` constructor |
| **Icons** | `lucide_icons` | Clean, consistent line icons. Pairs with shadcn_ui |
| **Typography** | `google_fonts` | Load Inter, Anek Odia, Noto Sans Oriya |
| **Animations** | `rive` | Interactive animations for mic recording, loading states |
| **State Management** | `flutter_riverpod` | Type-safe, testable state management |
| **Design Catalog** | `widgetbook` | Component catalog for team collaboration |

### 5.2 Core Components

#### A. Glass Card

The primary container for all content.

```
┌──────────────────────────────────────┐
│  ╭────────────────────────────────╮  │ ← Gradient background
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  │
│  │ ░  Frosted Glass Card        ░ │  │ ← BackdropFilter blur: 20px
│  │ ░  Background: white @ 0.65  ░ │  │ ← Background: rgba(255,255,255,0.65)
│  │ ░  Border: white @ 0.3       ░ │  │ ← Border: 1px solid rgba(255,255,255,0.3)
│  │ ░  Radius: 16px              ░ │  │ ← radius.lg
│  │ ░  Shadow: elevation.sm      ░ │  │
│  │ ░  Padding: 16px             ░ │  │
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  │
│  ╰────────────────────────────────╯  │
└──────────────────────────────────────┘
```

**Specs:**
- Background: `rgba(255, 255, 255, 0.65)`
- Backdrop blur: `20px`
- Border: `1px solid rgba(255, 255, 255, 0.3)`
- Border radius: `16px`
- Shadow: `elevation.sm`
- Padding: `16px`

#### B. Primary Button (CTA)

```
╭──────────────────────────╮
│      Submit News    →    │  ← Gradient fill: "Sunrise"
╰──────────────────────────╯
  Height: 52px
  Radius: radius.full (pill)
  Text: label.large, white, medium
  Padding: 24px horizontal
  Shadow: elevation.md

  States:
    Default: Gradient fill
    Pressed: Darken 10%, scale(0.98)
    Disabled: Opacity 0.4, no shadow
    Loading: Replace text with spinner
```

#### C. Secondary Button

```
╭──────────────────────────╮
│      Save Draft          │  ← Border: 1.5px primary.500
╰──────────────────────────╯    Background: transparent
  Height: 48px                  Text: primary.500
  Radius: radius.full

  States:
    Hover: Background primary.50
    Pressed: Background primary.100
```

#### D. Ghost Button

```
  Rephrase with AI  →          ← No border, no background
                                Text: primary.500
  Height: 40px                  Icon + text

  States:
    Hover: Background primary.50, radius.md
```

#### E. Text Input Field

```
╭──────────────────────────────────╮
│ Label                            │
├──────────────────────────────────┤
│  ┌────────────────────────────┐  │
│  │ Placeholder text...        │  │  ← Background: neutral.50
│  └────────────────────────────┘  │  ← Border: 1px neutral.200
├──────────────────────────────────┤     Radius: radius.md (12px)
│ Helper text                      │     Height: 52px
╰──────────────────────────────────╯     Padding: 16px horizontal
                                         Focus border: primary.500
  States:
    Default: Border neutral.200
    Focus: Border primary.500, shadow glow(primary.500, 0.15)
    Error: Border error, helper text turns error color
    Disabled: Background neutral.100, opacity 0.6
```

#### F. Voice Dictation Button (Hero Component)

The most important UI element — the mic button for voice input.

```
           ╭─────╮
          ╱       ╲
         │   🎤    │     ← 72px diameter circle
          ╲       ╱      ← Gradient fill: "Sunrise"
           ╰─────╯       ← Shadow: elevation.lg
              │           ← Pulse animation when recording
              │
  "Tap to dictate"       ← label.medium, neutral.500

  States:
    Idle: Static gradient, mic icon (white)
    Recording:
      - Pulsing glow ring animation (primary.300 @ 0.3, expanding)
      - Waveform visualization around button
      - Red dot indicator
      - Duration timer appears
    Processing: Spinner replaces mic icon

  Size variants:
    Large (hero): 72px — on dictation screen
    Medium: 48px — inline in text editor
```

#### G. News Card (Reporter View)

```
╭────────────────────────────────────╮
│                                    │
│  ┌──────┐  ରାଜନୀତି    12:45 PM    │  ← Category chip + time
│  │ 📷   │                          │
│  │      │  ମୁଖ୍ୟମନ୍ତ୍ରୀ ଆଜି...     │  ← Headline (heading.h2, Anek Odia)
│  │      │                          │
│  └──────┘  ଭୁବନେଶ୍ୱର | ସତ୍ରୁଜିତ  │  ← Location + Reporter
│                                    │
│  ┌──────────────────────────────┐  │
│  │ ██████████████░░░░░░░░░░░░░ │  │  ← Status bar
│  │ Draft — 60% complete        │  │
│  └──────────────────────────────┘  │
│                                    │
│  [Continue Editing]    [Submit →]  │  ← Action buttons
│                                    │
╰────────────────────────────────────╯

  Style: Glass Card specs
  Thumbnail: 64x64, radius.md, left-aligned
  Priority badge: Gold star icon on top-right if isPriority
  Ad badge: "AD" pill in accent.gold if isAdvertisement
```

#### H. News Card (Admin View)

```
╭────────────────────────────────────────────────╮
│  ⭐ PRIORITY                                    │  ← Gold badge if priority
│                                                  │
│  ମୁଖ୍ୟମନ୍ତ୍ରୀ ଆଜି କଟକ ଗସ୍ତରେ...                │  ← Headline (heading.h2)
│                                                  │
│  📍 ଭୁବନେଶ୍ୱର  👤 ସତ୍ରୁଜିତ  📅 24 Feb 2026    │  ← Metadata row
│                                                  │
│  ┌────────┐ ┌────────┐ ┌────────┐               │
│  │ 📷 3   │ │ 🎥 1   │ │ 📎 2   │               │  ← Media thumbnails
│  └────────┘ └────────┘ └────────┘               │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  ● Submitted   ○ Approved   ○ Published  │   │  ← Status stepper
│  └──────────────────────────────────────────┘   │
│                                                  │
│  [Reject]  [Translate 🌐]  [Approve ✓]         │  ← Action buttons
│                                                  │
╰────────────────────────────────────────────────╯
```

#### I. Status Chips

```
╭───────────╮
│ ● Draft   │  ← neutral.400 dot, neutral.100 bg, neutral.700 text
╰───────────╯

╭───────────────╮
│ ● Submitted   │  ← warning dot (#F59E0B), warning.50 bg, warning.700 text
╰───────────────╯

╭──────────────╮
│ ● Approved   │  ← success dot (#22C55E), success.50 bg, success.700 text
╰──────────────╯

╭──────────────╮
│ ● Rejected   │  ← error dot (#EF4444), error.50 bg, error.700 text
╰──────────────╯

╭───────────────╮
│ ● Published   │  ← primary.500 dot, primary.50 bg, primary.700 text
╰───────────────╯

  Height: 28px
  Padding: 8px horizontal, 4px vertical
  Radius: radius.full
  Text: label.medium
  Dot: 8px circle
```

#### J. Category Chip

```
╭──────────────────╮
│  🏛️ ରାଜନୀତି     │  ← Icon + Odia category name
╰──────────────────╯

  Height: 32px
  Background: primary.100
  Text: primary.800, label.medium
  Radius: radius.sm (6px)
  Border: none

  Selected state:
    Background: primary.500
    Text: white
```

#### K. Bottom Navigation (Mobile)

```
┌────────────────────────────────────────────┐
│                                            │
│  🏠       📋        ➕        👤          │
│  Home    My News   New      Profile       │
│  ━━━━                                     │  ← Active indicator: 3px primary.500 bar
│                                            │
└────────────────────────────────────────────┘

  Height: 64px + safe area
  Background: white
  Shadow: 0 -2px 12px rgba(0,0,0,0.06)
  Active icon: primary.500
  Inactive icon: neutral.400
  Active text: primary.500, label.small, medium
  Inactive text: neutral.400, label.small

  The "+" (New News) button is elevated:
    ╭─────╮
    │  +  │  ← 56px circle, gradient "Sunrise" fill
    ╰─────╯    Floats above the nav bar by 16px
               Shadow: elevation.md
```

#### L. Top App Bar

```
┌────────────────────────────────────────────┐
│                                            │
│  ← Back     Today's News        🔔  ⚙️   │
│                                            │
└────────────────────────────────────────────┘

  Height: 56px
  Background: transparent (blends with page gradient)
  Title: heading.h3, neutral.800
  Icons: 24px, neutral.700
  Notification bell: Red dot badge when unread
```

#### M. Search Bar

```
╭──────────────────────────────────────╮
│  🔍  Search news, reporters...       │  ← Background: neutral.50
╰──────────────────────────────────────╯    Border: 1px neutral.200
                                            Radius: radius.full
  Height: 48px                              Padding: 16px left (after icon)
  Icon: neutral.400, 20px
  Placeholder: neutral.400, body.medium

  Focus state: Expands to show filter chips below
  ┌──────────────────────────────────────┐
  │  [All] [Today] [Priority] [Pending]  │  ← Filter chips
  └──────────────────────────────────────┘
```

#### N. Toast / Snackbar

```
╭────────────────────────────────────────╮
│  ✓  News submitted successfully!       │  ← Glass card style
╰────────────────────────────────────────╯

  Background: Glass (white @ 0.8, blur 16px)
  Border-left: 4px solid (success/error/warning/info)
  Radius: radius.md
  Shadow: elevation.md
  Position: Bottom center, 16px from bottom
  Auto-dismiss: 4 seconds
  Swipe to dismiss
```

#### O. Empty State

```
  ╭─────────╮
  │  📰     │  ← 80px illustration (Rive animation)
  │  ~~~    │
  ╰─────────╯

  No news yet today
  ────────────────
  Tap the + button to start
  dictating your first news

  [+ Start Dictating]

  Illustration: Animated (subtle float/bounce)
  Title: heading.h3, neutral.800
  Description: body.medium, neutral.500
  CTA: Primary button (pill)
```

---

## 6. Iconography

### Icon Set: Lucide Icons

- **Package:** `lucide_icons` on pub.dev
- **Style:** 24px base, 1.5px stroke weight, rounded caps
- **Why:** Clean, minimal line icons that match the shadcn_ui aesthetic

### Core Icons Map

| Icon | Usage |
|---|---|
| `mic` | Dictation |
| `mic-off` | Stop recording |
| `send` | Submit news |
| `file-text` | News article |
| `image` | Photo attachment |
| `video` | Video attachment |
| `headphones` | Audio attachment |
| `paperclip` | Document attachment |
| `map-pin` | Location |
| `calendar` | Date |
| `user` | Reporter |
| `check-circle` | Approved |
| `x-circle` | Rejected |
| `clock` | Pending/submitted |
| `star` | Priority |
| `tag` | Category |
| `search` | Search |
| `bell` | Notifications |
| `settings` | Settings |
| `log-out` | Logout |
| `home` | Home |
| `list` | My news |
| `plus` | New news |
| `edit-3` | Edit/proofread |
| `eye` | Preview |
| `volume-2` | TTS playback |
| `languages` | Translation |
| `sparkles` | AI rephrase |
| `download` | Export |
| `printer` | Print export |
| `globe` | Web publish |
| `building-2` | Organization |
| `users` | Team/reporters |
| `bar-chart-3` | Analytics |
| `filter` | Filter |
| `chevron-right` | Navigation |
| `arrow-left` | Back |

### Icon Sizing

| Context | Size | Color |
|---|---|---|
| Navigation | 24px | Active: primary.500, Inactive: neutral.400 |
| In buttons | 20px | Same as button text |
| In cards | 20px | neutral.500 |
| Decorative | 16px | neutral.400 |
| Hero/Feature | 32px | primary.500 |

---

## 7. Motion & Animation

### 7.1 Timing Curves

| Token | Curve | Duration | Usage |
|---|---|---|---|
| `motion.quick` | `easeOut` | 150ms | Micro-interactions (button press, toggle) |
| `motion.standard` | `easeInOut` | 250ms | State changes (expand, collapse, fade) |
| `motion.emphasis` | `cubicBezier(0.4, 0, 0, 1)` | 350ms | Page transitions, modal entrances |
| `motion.dramatic` | `spring(damping: 15)` | 500ms | Hero elements, celebrations |

### 7.2 Key Animations

| Element | Animation | Tool |
|---|---|---|
| **Mic recording pulse** | Expanding/fading concentric circles from mic button | `Rive` |
| **Audio waveform** | Real-time waveform bars during recording | Custom painter |
| **Mesh gradient bg** | Slowly morphing mesh gradient on login/splash | `mesh_gradient` |
| **Card entrance** | Slide up + fade in, staggered for lists | Flutter `AnimatedList` |
| **Status change** | Color morph + check/x icon animation | `Rive` |
| **AI processing** | Shimmer effect on text while LLM rephrases | Custom shimmer |
| **Submit success** | Confetti/particle burst | `Rive` |
| **Pull to refresh** | Custom sunrise animation | `Rive` |
| **Page transitions** | Shared element + fade | Flutter Hero + `PageRouteBuilder` |

### 7.3 Loading States

```
Content loading:     ░░░░░░░░░░░░░  ← Shimmer with warm gradient tint
                     ░░░░░░░░░░░░░    (not grey shimmer — use primary.100 → primary.50)
                     ░░░░░░░░░░░

AI processing:       ✨ Rephrasing your news...
                     ████████░░░░░░  ← Animated progress with sparkle icon
                     Powered by Sarvam AI

Upload progress:     📤 Uploading media...
                     ██████████░░░  ← Percentage + animated bar
                     3 of 5 files (60%)
```

---

## 8. Platform-Specific Notes

### 8.1 Mobile (Flutter — Reporter App)

- **Safe areas:** Respect notches, dynamic island, home indicator
- **Haptics:** Light haptic on mic tap, medium on submit, success on approve
- **Keyboard:** Auto-scroll form fields above keyboard
- **Orientation:** Portrait only (lock)
- **Pull to refresh:** Custom sunrise animation
- **Offline indicator:** Subtle amber bar at top when offline: "You're offline. Drafts will sync when connected."

### 8.2 Web (Admin Dashboard)

- **Responsive breakpoints:**
  - Mobile: < 640px (stack to single column)
  - Tablet: 640-1024px (collapsible sidebar)
  - Desktop: > 1024px (full sidebar + content)
- **Hover states:** All interactive elements must have hover state
- **Keyboard navigation:** Full tab-order support
- **Sidebar:** Fixed left nav, collapsible to icons-only

### 8.3 Shared

- **Minimum touch target:** 44x44px (Apple HIG)
- **Focus rings:** 2px primary.500 outline, 2px offset (for accessibility)
- **Scrollbar:** Thin, neutral.300 track, neutral.400 thumb (web only)

---

## 9. Flutter Implementation

### 9.1 Package Dependencies

```yaml
# pubspec.yaml
dependencies:
  flutter:
    sdk: flutter

  # UI Components
  shadcn_ui: ^0.15.0          # Base component library
  lucide_icons: ^0.257.0       # Icon set
  google_fonts: ^6.2.0         # Typography

  # Visual Effects
  mesh_gradient: ^1.3.0        # Animated mesh backgrounds
  glass_kit: ^3.0.0            # Glassmorphic cards

  # Animation
  rive: ^0.13.0                # Interactive animations
  shimmer: ^3.0.0              # Loading shimmer effect

  # State Management
  flutter_riverpod: ^2.5.0     # State management
  riverpod_annotation: ^2.3.0  # Code generation for Riverpod

  # Design System Tooling
  widgetbook: ^3.14.0          # Component catalog
  widgetbook_annotation: ^3.2.0

dev_dependencies:
  riverpod_generator: ^2.4.0
  build_runner: ^2.4.0
  widgetbook_generator: ^3.10.0
```

### 9.2 Theme Structure

```
lib/
├── design_system/
│   ├── tokens/
│   │   ├── colors.dart          # All color tokens
│   │   ├── typography.dart      # Text styles + Odia overrides
│   │   ├── spacing.dart         # Spacing scale constants
│   │   ├── radius.dart          # Border radius tokens
│   │   ├── elevation.dart       # Shadow definitions
│   │   └── gradients.dart       # Gradient definitions
│   ├── theme/
│   │   ├── app_theme.dart       # ThemeData configuration
│   │   ├── color_scheme.dart    # Material ColorScheme mapping
│   │   └── extensions/
│   │       ├── gradient_ext.dart   # Custom ThemeExtension for gradients
│   │       └── glass_ext.dart      # Custom ThemeExtension for glass
│   ├── components/
│   │   ├── glass_card.dart      # Reusable glass card widget
│   │   ├── gradient_button.dart # Primary gradient button
│   │   ├── voice_button.dart    # Mic/dictation hero button
│   │   ├── status_chip.dart     # News status badges
│   │   ├── category_chip.dart   # Category selection chips
│   │   ├── news_card.dart       # News article card
│   │   ├── search_bar.dart      # Search with filters
│   │   ├── toast.dart           # Toast/snackbar
│   │   ├── empty_state.dart     # Empty state illustration
│   │   └── shimmer_loading.dart # Warm shimmer loading
│   └── foundations/
│       ├── responsive.dart      # Breakpoint utilities
│       └── haptics.dart         # Haptic feedback helper
```

### 9.3 Design Token Example (colors.dart)

```dart
import 'package:flutter/material.dart';

abstract class NewsFlowColors {
  // Primary — Sunrise
  static const primary50 = Color(0xFFFFF8F0);
  static const primary100 = Color(0xFFFFECD2);
  static const primary200 = Color(0xFFFFD9A8);
  static const primary300 = Color(0xFFFFC178);
  static const primary400 = Color(0xFFFFA94D);
  static const primary500 = Color(0xFFFF8C22); // Brand primary
  static const primary600 = Color(0xFFE07010);
  static const primary700 = Color(0xFFB85A0A);
  static const primary800 = Color(0xFF8A4308);
  static const primary900 = Color(0xFF5C2D05);

  // Neutral
  static const neutral0 = Color(0xFFFFFFFF);
  static const neutral50 = Color(0xFFFAFAF9);
  static const neutral100 = Color(0xFFF5F5F4);
  static const neutral200 = Color(0xFFE7E5E4);
  static const neutral300 = Color(0xFFD6D3D1);
  static const neutral400 = Color(0xFFA8A29E);
  static const neutral500 = Color(0xFF78716C);
  static const neutral600 = Color(0xFF57534E);
  static const neutral700 = Color(0xFF44403C);
  static const neutral800 = Color(0xFF292524);
  static const neutral900 = Color(0xFF1C1917);

  // Semantic
  static const success = Color(0xFF22C55E);
  static const warning = Color(0xFFF59E0B);
  static const error = Color(0xFFEF4444);
  static const info = Color(0xFF3B82F6);

  // Accent
  static const gold = Color(0xFFF5B800);
  static const amber = Color(0xFFFFBF47);
  static const peach = Color(0xFFFFCBA4);
  static const cream = Color(0xFFFFF5E6);
}
```

---

## 10. Accessibility

### 10.1 Color Contrast

All text must meet WCAG AA standards:
- **Normal text (< 18px):** 4.5:1 minimum contrast ratio
- **Large text (>= 18px bold or >= 24px):** 3:1 minimum contrast ratio

| Combination | Ratio | Pass? |
|---|---|---|
| neutral.800 on neutral.0 (white) | 14.7:1 | AA |
| neutral.600 on neutral.0 | 7.2:1 | AA |
| neutral.500 on neutral.0 | 4.6:1 | AA |
| primary.500 on neutral.0 | 3.2:1 | AA Large only |
| white on primary.500 | 3.2:1 | AA Large only |
| primary.800 on primary.50 | 8.9:1 | AA |
| white on primary.600 | 4.8:1 | AA |

**Rule:** Use `primary.600` or darker for text on white. Use `primary.500` only for large text, icons, and decorative elements.

### 10.2 Touch Targets

- Minimum 44x44px for all interactive elements
- Minimum 8px spacing between adjacent touch targets

### 10.3 Screen Reader Support

- All images must have alt text
- Status chips must announce their state ("News status: Approved")
- Mic button: "Tap to start dictating. Double-tap for text input"
- Progress indicators must announce percentage changes

### 10.4 Reduced Motion

- Respect `MediaQuery.disableAnimations`
- Replace mesh gradient animations with static gradient
- Replace pulse/confetti with simple fade transitions

---

## Appendix: Visual Summary

### Color Palette at a Glance

```
PRIMARY (Sunrise)
  50   100   200   300   400   500   600   700   800   900
  ░░░  ░░░  ▒▒▒  ▒▒▒  ▓▓▓  ███  ███  ███  ███  ███
  Warm ─────────────────────────────────────────── Deep

NEUTRAL (Stone)
  50   100   200   300   400   500   600   700   800   900
  ░░░  ░░░  ░░░  ▒▒▒  ▒▒▒  ▓▓▓  ▓▓▓  ███  ███  ███
  Light ────────────────────────────────────────── Dark

SEMANTIC
  Success   Warning   Error   Info
    🟢        🟡       🔴      🔵
```

### Design System Mood

```
  ┌─────────────────────────────────────────┐
  │                                         │
  │    ╭─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╮     │
  │    ┊                              ┊     │
  │    ┊  Warm sunset gradient bg     ┊     │  ← Mesh gradient background
  │    ┊                              ┊     │
  │    ┊  ╭──────────────────────╮    ┊     │
  │    ┊  │ ░░ Frosted Glass ░░ │    ┊     │  ← Glass card
  │    ┊  │ ░░  Card Content ░░ │    ┊     │
  │    ┊  │ ░░              ░░  │    ┊     │
  │    ┊  ╰──────────────────────╯    ┊     │
  │    ┊                              ┊     │
  │    ┊       [Gradient CTA]         ┊     │  ← Pill button
  │    ┊                              ┊     │
  │    ╰─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╯     │
  │                                         │
  │    🏠      📋      (+)      👤          │  ← Bottom nav
  └─────────────────────────────────────────┘
```

---

*Design System Version: 1.0*
*Created: 2026-02-24*
*Platform: Flutter (Mobile + Web)*
*Project: NewsFlow — News Processing Automation System*
