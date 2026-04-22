# Dynamic Theme System Design

## Overview
Replace hardcoded color/typography references with a provider-based dynamic theme system. Users select from 3 curated presets via the settings screen. All screens read tokens from the theme provider.

## Architecture

### ThemeNotifier (Riverpod)
- Holds current `AppThemeData` instance
- Persists selected theme key to `SharedPreferences`
- Exposes `setTheme(String key)` method
- Loaded on app startup

### AppThemeData (Data Class)
Each preset defines these tokens:

| Token group | Properties |
|-------------|-----------|
| Scaffold | `scaffoldBg`, `cardBg`, `dividerColor` |
| Primary | `primary`, `primaryLight`, `primaryGradient` (2-color LinearGradient) |
| Mic button | `micButtonColor` (solid, 48px circle) |
| Text | `headingColor`, `bodyColor`, `mutedColor`, `onPrimary` |
| Chips | `aiChipBg`, `aiChipText`, `actionChipBg`, `actionChipIcon` |
| Selection | `selectedParaBg`, `selectedParaBorder` |
| Recording | `recordingBg`, `waveformBarColor`, `recordingTextColor` |
| Status badges | `draftBg`/`draftText`, `submittedBg`/`submittedText` |

### Context Extension
```dart
extension ThemeX on BuildContext {
  AppThemeData get t => ProviderScope.containerOf(this).read(themeProvider);
}
```

## 3 Presets

### Classic (current look)
- Scaffold: `neutral50` (#FAFAF9)
- Card: white
- Primary: `indigo600` (#4F46E5)
- Button gradient: indigo600 -> teal500
- Mic: indigo500
- Heading: neutral800, Body: neutral600, Muted: neutral400
- AI chip: indigo50 bg / indigo600 text
- Selected para: indigo50 bg
- Waveform: indigo400
- Recording bg: white

### Warm Pastel (new default-candidate)
- Scaffold: #FFF8F5 (warm cream)
- Card: #FFFBF9
- Primary: coral500 (#FF5733)
- Button gradient: coral400 -> coral600
- Mic: coral500
- Heading: neutral800, Body: neutral600, Muted: neutral400
- AI chip: coral50 bg / coral600 text
- Selected para: #FFF0EB bg
- Waveform: coral400
- Recording bg: #FFF5F2

### Dark
- Scaffold: neutral900 (#1C1917)
- Card: neutral800 (#292524)
- Primary: coral400 (#FF7A5C)
- Button gradient: coral500 -> coral300
- Mic: coral400
- Heading: neutral100, Body: neutral300, Muted: neutral500
- AI chip: dark coral bg / coral300 text
- Selected para: neutral700 bg
- Waveform: coral300
- Recording bg: neutral800

## Settings UI
Add "Theme" row to profile_screen.dart settings list (between Language and Help).
Tap opens bottom sheet with 3 visual preview cards showing scaffold + card + primary colors.
Tapping a card switches theme instantly.

## Migration Strategy
1. Create `lib/core/theme/app_theme_data.dart` — data class + 3 preset instances
2. Create `lib/core/theme/theme_provider.dart` — ThemeNotifier + provider
3. Create `lib/core/theme/theme_extensions.dart` — BuildContext extension
4. Migrate `notepad_screen.dart` — replace hardcoded AppColors/AppGradients with `context.t`
5. Migrate `home_screen.dart`
6. Migrate `login_screen.dart`
7. Migrate `profile_screen.dart` + add theme picker UI
8. Migrate bottom nav (`app_bottom_nav.dart`)

## Files
- `lib/core/theme/app_theme_data.dart` — NEW
- `lib/core/theme/theme_provider.dart` — NEW
- `lib/core/theme/theme_extensions.dart` — NEW
- `lib/features/create_news/screens/notepad_screen.dart` — MODIFY
- `lib/features/home/screens/home_screen.dart` — MODIFY
- `lib/features/auth/screens/login_screen.dart` — MODIFY
- `lib/features/profile/screens/profile_screen.dart` — MODIFY
- `lib/core/widgets/app_bottom_nav.dart` — MODIFY
- `lib/app.dart` — MODIFY (wrap with theme provider)
