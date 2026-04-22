# Dynamic Theme System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all hardcoded colors/gradients with a Riverpod-based dynamic theme system offering 3 presets (Classic, Warm Pastel, Dark), selectable from the profile/settings screen.

**Architecture:** `AppThemeData` data class holds all color/gradient tokens. `ThemeNotifier` (Riverpod Notifier) manages current theme, persists selection to SharedPreferences. All widgets access tokens via `context.t` extension. Existing `AppColors`/`AppTypography`/`AppGradients` remain for static values not covered by themes.

**Tech Stack:** Flutter, Riverpod, SharedPreferences, Google Fonts

---

### Task 1: Create AppThemeData data class

**Files:**
- Create: `lib/core/theme/app_theme_data.dart`

**Step 1: Create the theme data class with all token fields**

```dart
import 'package:flutter/material.dart';

class AppThemeData {
  // -- Identifiers --
  final String key;
  final String label;
  final String odiaLabel;

  // -- Scaffold --
  final Color scaffoldBg;
  final Color cardBg;
  final Color dividerColor;

  // -- Primary --
  final Color primary;
  final Color primaryLight;
  final LinearGradient primaryGradient;

  // -- Mic button --
  final Color micButtonColor;

  // -- Text --
  final Color headingColor;
  final Color bodyColor;
  final Color mutedColor;
  final Color onPrimary;

  // -- Chips --
  final Color aiChipBg;
  final Color aiChipText;
  final Color actionChipBg;
  final Color actionChipIcon;

  // -- Selection --
  final Color selectedParaBg;
  final Color selectedParaBorder;

  // -- Recording --
  final Color recordingBg;
  final Color waveformBarColor;
  final Color recordingTextColor;

  // -- Status badges --
  final Color draftBg;
  final Color draftText;
  final Color submittedBg;
  final Color submittedText;

  // -- Nav --
  final Color navBg;
  final Color navActiveColor;
  final Color navInactiveColor;

  // -- Header --
  final Color headerBg;
  final LinearGradient headerGradient;

  // -- Brightness --
  final Brightness brightness;

  const AppThemeData({
    required this.key,
    required this.label,
    required this.odiaLabel,
    required this.scaffoldBg,
    required this.cardBg,
    required this.dividerColor,
    required this.primary,
    required this.primaryLight,
    required this.primaryGradient,
    required this.micButtonColor,
    required this.headingColor,
    required this.bodyColor,
    required this.mutedColor,
    required this.onPrimary,
    required this.aiChipBg,
    required this.aiChipText,
    required this.actionChipBg,
    required this.actionChipIcon,
    required this.selectedParaBg,
    required this.selectedParaBorder,
    required this.recordingBg,
    required this.waveformBarColor,
    required this.recordingTextColor,
    required this.draftBg,
    required this.draftText,
    required this.submittedBg,
    required this.submittedText,
    required this.navBg,
    required this.navActiveColor,
    required this.navInactiveColor,
    required this.headerBg,
    required this.headerGradient,
    required this.brightness,
  });
}
```

**Step 2: Define 3 preset instances below the class**

Use exact hex values from the design doc. Reference `AppColors` for shared constants.

```dart
import 'app_colors.dart';

const classicTheme = AppThemeData(
  key: 'classic',
  label: 'Classic',
  odiaLabel: '\u0B15\u0B4D\u0B32\u0B3E\u0B38\u0B3F\u0B15', // କ୍ଲାସିକ
  scaffoldBg: AppColors.neutral50,
  cardBg: AppColors.neutral0,
  dividerColor: AppColors.neutral200,
  primary: AppColors.indigo600,
  primaryLight: AppColors.indigo50,
  primaryGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.indigo600, AppColors.teal500],
  ),
  micButtonColor: AppColors.indigo500,
  headingColor: AppColors.neutral800,
  bodyColor: AppColors.neutral600,
  mutedColor: AppColors.neutral400,
  onPrimary: Colors.white,
  aiChipBg: AppColors.indigo50,
  aiChipText: AppColors.indigo600,
  actionChipBg: AppColors.neutral100,
  actionChipIcon: AppColors.neutral600,
  selectedParaBg: AppColors.indigo50,
  selectedParaBorder: AppColors.indigo200,
  recordingBg: AppColors.neutral0,
  waveformBarColor: AppColors.indigo400,
  recordingTextColor: AppColors.indigo600,
  draftBg: AppColors.gold50,
  draftText: AppColors.gold600,
  submittedBg: AppColors.teal50,
  submittedText: AppColors.teal600,
  navBg: AppColors.neutral0,
  navActiveColor: AppColors.indigo600,
  navInactiveColor: AppColors.neutral400,
  headerBg: AppColors.neutral0,
  headerGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.indigo800, Color(0xFF312E81), AppColors.teal600],
  ),
  brightness: Brightness.light,
);

const warmPastelTheme = AppThemeData(
  key: 'warm_pastel',
  label: 'Warm Pastel',
  odiaLabel: '\u0B09\u0B37\u0B4D\u0B23 \u0B2A\u0B4D\u0B5F\u0B3E\u0B38\u0B4D\u0B1F\u0B47\u0B32', // ଉଷ୍ଣ ପ୍ୟାସ୍ଟେଲ
  scaffoldBg: Color(0xFFFFF8F5),
  cardBg: Color(0xFFFFFBF9),
  dividerColor: Color(0xFFFFE4DE),
  primary: AppColors.coral500,
  primaryLight: AppColors.coral50,
  primaryGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.coral400, AppColors.coral600],
  ),
  micButtonColor: AppColors.coral500,
  headingColor: AppColors.neutral800,
  bodyColor: AppColors.neutral600,
  mutedColor: AppColors.neutral400,
  onPrimary: Colors.white,
  aiChipBg: AppColors.coral50,
  aiChipText: AppColors.coral600,
  actionChipBg: Color(0xFFFFF0EB),
  actionChipIcon: AppColors.neutral600,
  selectedParaBg: Color(0xFFFFF0EB),
  selectedParaBorder: AppColors.coral200,
  recordingBg: Color(0xFFFFF5F2),
  waveformBarColor: AppColors.coral400,
  recordingTextColor: AppColors.coral600,
  draftBg: AppColors.gold50,
  draftText: AppColors.gold600,
  submittedBg: AppColors.teal50,
  submittedText: AppColors.teal600,
  navBg: Color(0xFFFFFBF9),
  navActiveColor: AppColors.coral500,
  navInactiveColor: AppColors.neutral400,
  headerBg: Color(0xFFFFFBF9),
  headerGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.coral500, AppColors.coral600, Color(0xFFB83A1F)],
  ),
  brightness: Brightness.light,
);

const darkTheme = AppThemeData(
  key: 'dark',
  label: 'Dark',
  odiaLabel: '\u0B05\u0B28\u0B4D\u0B27\u0B3E\u0B30', // ଅନ୍ଧାର
  scaffoldBg: AppColors.neutral900,
  cardBg: AppColors.neutral800,
  dividerColor: AppColors.neutral700,
  primary: AppColors.coral400,
  primaryLight: Color(0xFF3D1F1A),
  primaryGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.coral500, AppColors.coral300],
  ),
  micButtonColor: AppColors.coral400,
  headingColor: AppColors.neutral100,
  bodyColor: AppColors.neutral300,
  mutedColor: AppColors.neutral500,
  onPrimary: Colors.white,
  aiChipBg: Color(0xFF3D1F1A),
  aiChipText: AppColors.coral300,
  actionChipBg: AppColors.neutral700,
  actionChipIcon: AppColors.neutral300,
  selectedParaBg: AppColors.neutral700,
  selectedParaBorder: AppColors.neutral600,
  recordingBg: AppColors.neutral800,
  waveformBarColor: AppColors.coral300,
  recordingTextColor: AppColors.coral300,
  draftBg: Color(0xFF3D2F0A),
  draftText: AppColors.gold400,
  submittedBg: Color(0xFF0A3D2F),
  submittedText: AppColors.teal300,
  navBg: AppColors.neutral900,
  navActiveColor: AppColors.coral400,
  navInactiveColor: AppColors.neutral500,
  headerBg: AppColors.neutral800,
  headerGradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.neutral900, AppColors.neutral800, Color(0xFF3D1F1A)],
  ),
  brightness: Brightness.dark,
);

const appThemePresets = <String, AppThemeData>{
  'classic': classicTheme,
  'warm_pastel': warmPastelTheme,
  'dark': darkTheme,
};
```

**Step 3: Commit**

```bash
git add lib/core/theme/app_theme_data.dart
git commit -m "feat: add AppThemeData class with 3 preset themes"
```

---

### Task 2: Create ThemeNotifier provider

**Files:**
- Create: `lib/core/theme/theme_provider.dart`

**Step 1: Create the provider with SharedPreferences persistence**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'app_theme_data.dart';

class ThemeNotifier extends Notifier<AppThemeData> {
  static const _prefKey = 'app_theme';

  @override
  AppThemeData build() {
    _loadSavedTheme();
    return classicTheme;
  }

  Future<void> _loadSavedTheme() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = prefs.getString(_prefKey);
      if (key != null && appThemePresets.containsKey(key)) {
        state = appThemePresets[key]!;
      }
    } catch (_) {
      // SharedPreferences may fail on simulator — silently keep default
    }
  }

  Future<void> setTheme(String key) async {
    final theme = appThemePresets[key];
    if (theme == null) return;
    state = theme;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefKey, key);
    } catch (_) {}
  }
}

final themeProvider =
    NotifierProvider<ThemeNotifier, AppThemeData>(ThemeNotifier.new);
```

**Step 2: Commit**

```bash
git add lib/core/theme/theme_provider.dart
git commit -m "feat: add ThemeNotifier provider with persistence"
```

---

### Task 3: Create BuildContext extension

**Files:**
- Create: `lib/core/theme/theme_extensions.dart`

**Step 1: Create the extension**

```dart
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app_theme_data.dart';
import 'theme_provider.dart';

extension ThemeX on BuildContext {
  AppThemeData get t {
    return ProviderScope.containerOf(this).read(themeProvider);
  }
}
```

**Step 2: Commit**

```bash
git add lib/core/theme/theme_extensions.dart
git commit -m "feat: add context.t extension for theme access"
```

---

### Task 4: Wire theme into app.dart

**Files:**
- Modify: `lib/app.dart`

**Step 1: Update app.dart to use theme provider for MaterialApp**

Change `NewsFlowApp` to watch `themeProvider` and derive `ThemeData` from it. Keep `AppTheme.light` as a base but override key colors. Key changes:

- Import `theme_provider.dart` and `app_theme_data.dart`
- Watch `themeProvider` to get current `AppThemeData`
- Set `scaffoldBackgroundColor`, `colorScheme.primary`, and `brightness` from the theme data
- Set `SystemUiOverlayStyle` based on brightness

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_provider.dart';
import 'core/router/app_router.dart';

class NewsFlowApp extends ConsumerWidget {
  const NewsFlowApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final t = ref.watch(themeProvider);

    final base = AppTheme.light;
    final theme = base.copyWith(
      scaffoldBackgroundColor: t.scaffoldBg,
      colorScheme: base.colorScheme.copyWith(
        primary: t.primary,
        surface: t.cardBg,
        onSurface: t.headingColor,
        brightness: t.brightness,
      ),
      appBarTheme: base.appBarTheme.copyWith(
        backgroundColor: t.headerBg,
        systemOverlayStyle: t.brightness == Brightness.dark
            ? SystemUiOverlayStyle.light
            : SystemUiOverlayStyle.dark,
      ),
    );

    return MaterialApp.router(
      title: 'Vrittant',
      debugShowCheckedModeBanner: false,
      theme: theme,
      routerConfig: router,
    );
  }
}
```

**Step 2: Build and verify no compile errors**

Run: `cd /Users/admin/Desktop/newsflow && flutter build ios --debug --no-codesign 2>&1 | tail -3`
Expected: `BUILD SUCCESSFUL` or similar

**Step 3: Commit**

```bash
git add lib/app.dart
git commit -m "feat: wire theme provider into MaterialApp"
```

---

### Task 5: Migrate bottom nav

**Files:**
- Modify: `lib/core/widgets/app_bottom_nav.dart`

**Step 1: Replace hardcoded AppColors with context.t tokens**

Key changes:
- Import `theme_extensions.dart`
- `AppShell`: `color: Colors.white` -> `color: context.t.navBg`
- `_NavItem`: `AppColors.indigo600` -> pass active/inactive colors from parent using `context.t.navActiveColor` / `context.t.navInactiveColor`

**Step 2: Build and verify**

**Step 3: Commit**

```bash
git add lib/core/widgets/app_bottom_nav.dart
git commit -m "feat: migrate bottom nav to dynamic theme"
```

---

### Task 6: Migrate notepad screen

**Files:**
- Modify: `lib/features/create_news/screens/notepad_screen.dart`

This is the largest migration. Replace hardcoded `AppColors` references with `context.t` tokens throughout the file. Key areas:

**Step 1: Add imports at top of file**

```dart
import '../../../core/theme/theme_extensions.dart';
import '../../../core/theme/theme_provider.dart';
```

**Step 2: Migrate Scaffold and header**

- `Scaffold backgroundColor: AppColors.neutral50` -> `context.t.scaffoldBg`
- Header `color: Colors.white` -> `context.t.headerBg`
- Header border color -> `context.t.dividerColor`
- Back arrow / icon colors -> `context.t.bodyColor`
- Headline text color -> `context.t.headingColor`
- Mic dictation button -> use `context.t.primary` and `context.t.primaryLight`

**Step 3: Migrate paragraph blocks**

- `_ParagraphBlock` selected background -> `context.t.selectedParaBg`
- Selected border -> `context.t.selectedParaBorder`
- Body text -> `context.t.bodyColor`

**Step 4: Migrate action chips**

- `_EditActionChips` AI chip -> bg: `context.t.aiChipBg`, text: `context.t.aiChipText`
- Move/delete chips -> bg: `context.t.actionChipBg`, icon: `context.t.actionChipIcon`

**Step 5: Migrate recording UI**

- `_RecordingBottomBar` waveform bar color -> `context.t.waveformBarColor`
- Recording text -> `context.t.recordingTextColor`
- Stop button -> `context.t.primary`
- `_IdleBottomBar` mic button -> `context.t.micButtonColor`
- Submit button gradient -> `context.t.primaryGradient`

**Step 6: Migrate AI instruction panel**

- Panel bg -> `context.t.cardBg`
- Sparkle icon color -> `context.t.primary`
- Apply button -> `context.t.primary`

**Step 7: Migrate status badges, metadata chips, empty state**

- Draft badge -> `context.t.draftBg` / `context.t.draftText`
- Category chip -> use `context.t.primary` and `context.t.primaryLight`
- Empty state mic button -> `context.t.micButtonColor`

**Step 8: Build and verify**

Run: `flutter build ios --debug --no-codesign`

**Step 9: Hot reload on simulator and visually verify**

**Step 10: Commit**

```bash
git add lib/features/create_news/screens/notepad_screen.dart
git commit -m "feat: migrate notepad screen to dynamic theme"
```

---

### Task 7: Migrate home screen

**Files:**
- Modify: `lib/features/home/screens/home_screen.dart`

**Step 1: Replace hardcoded colors**

- Scaffold bg -> `context.t.scaffoldBg`
- Header bg -> `context.t.headerBg`
- Name gradient -> `context.t.primaryGradient`
- Create button gradient -> `context.t.primaryGradient`
- Story card bg -> `context.t.cardBg`
- Story card border -> `context.t.dividerColor`
- Headline text -> `context.t.headingColor`
- Body text -> `context.t.bodyColor`
- Status badges -> `context.t.draftBg/draftText`, `context.t.submittedBg/submittedText`

**Step 2: Build, verify, commit**

```bash
git add lib/features/home/screens/home_screen.dart
git commit -m "feat: migrate home screen to dynamic theme"
```

---

### Task 8: Migrate login screen

**Files:**
- Modify: `lib/features/auth/screens/login_screen.dart`

**Step 1: Replace hardcoded colors**

- Scaffold bg -> `context.t.scaffoldBg`
- Title gradient -> `context.t.primaryGradient`
- Input borders -> `context.t.dividerColor` / `context.t.primary`
- Input fill -> `context.t.cardBg`
- Button gradient -> `context.t.primaryGradient`
- Text colors -> `context.t.headingColor`, `context.t.bodyColor`

**Step 2: Build, verify, commit**

```bash
git add lib/features/auth/screens/login_screen.dart
git commit -m "feat: migrate login screen to dynamic theme"
```

---

### Task 9: Add theme picker to profile screen

**Files:**
- Modify: `lib/features/profile/screens/profile_screen.dart`

**Step 1: Migrate existing profile colors to theme tokens**

- Header gradient -> `context.t.headerGradient`
- Stats card bg -> `context.t.cardBg`
- Settings card bg -> `context.t.cardBg`
- Setting icon bg -> `context.t.primaryLight`
- Setting icon color -> `context.t.primary`

**Step 2: Add theme row to settings list**

Insert between "Language" and "Help & Support":
```dart
(LucideIcons.palette, 'Theme', '\u0B25\u0B3F\u0B2E\u0B4D'),  // ଥିମ୍
```

**Step 3: Create `_showThemePicker` bottom sheet**

When "Theme" row is tapped, show a modal bottom sheet with 3 cards. Each card shows:
- Small preview rectangle (scaffold bg + card bg + primary accent stripe)
- Theme Odia label
- Checkmark on the currently active theme

Tapping a card calls `ref.read(themeProvider.notifier).setTheme(key)`.

```dart
void _showThemePicker(BuildContext context, WidgetRef ref) {
  final current = ref.read(themeProvider);
  showModalBottomSheet(
    context: context,
    backgroundColor: current.cardBg,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // drag handle
              Container(width: 40, height: 4, decoration: BoxDecoration(
                color: current.dividerColor, borderRadius: BorderRadius.circular(2))),
              const SizedBox(height: 16),
              Text('\u0B25\u0B3F\u0B2E\u0B4D \u0B2C\u0B3E\u0B1B\u0B28\u0B4D\u0B24\u0B41', /* ଥିମ୍ ବାଛନ୍ତୁ */
                style: AppTypography.odiaTitleLarge),
              const SizedBox(height: 16),
              Row(
                children: appThemePresets.values.map((theme) {
                  final isActive = theme.key == current.key;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () {
                        ref.read(themeProvider.notifier).setTheme(theme.key);
                        Navigator.pop(ctx);
                      },
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: theme.scaffoldBg,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isActive ? theme.primary : theme.dividerColor,
                            width: isActive ? 2 : 1,
                          ),
                        ),
                        child: Column(
                          children: [
                            // Preview: card with primary stripe
                            Container(
                              height: 48,
                              decoration: BoxDecoration(
                                color: theme.cardBg,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(children: [
                                Container(width: 4, decoration: BoxDecoration(
                                  color: theme.primary,
                                  borderRadius: const BorderRadius.horizontal(
                                    left: Radius.circular(8)),
                                )),
                                const Spacer(),
                              ]),
                            ),
                            const SizedBox(height: 8),
                            Text(theme.odiaLabel,
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: isActive ? FontWeight.w700 : FontWeight.w400,
                                color: theme.headingColor,
                              )),
                            if (isActive) ...[
                              const SizedBox(height: 4),
                              Icon(Icons.check_circle, size: 16, color: theme.primary),
                            ],
                          ],
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ],
          ),
        ),
      );
    },
  );
}
```

**Step 4: Handle the theme row tap in the settings list**

Change the `_buildSettings` method: when `title == 'Theme'` (or use a separate flag), call `_showThemePicker`.

**Step 5: Convert `ProfileScreen` to `ConsumerWidget` (currently `StatelessWidget`)**

It needs `ref` to read/watch `themeProvider`.

**Step 6: Build, hot reload, verify all 3 themes switch correctly**

**Step 7: Commit**

```bash
git add lib/features/profile/screens/profile_screen.dart
git commit -m "feat: add theme picker to settings and migrate profile screen"
```

---

### Task 10: Migrate all_news_screen

**Files:**
- Modify: `lib/features/all_news/screens/all_news_screen.dart`

**Step 1: Replace hardcoded colors with context.t tokens**

Same pattern as other screens — scaffold bg, card bg, text colors, chip colors.

**Step 2: Build, verify, commit**

```bash
git add lib/features/all_news/screens/all_news_screen.dart
git commit -m "feat: migrate all news screen to dynamic theme"
```

---

### Task 11: Final verification

**Step 1: Build full app**

Run: `cd /Users/admin/Desktop/newsflow && flutter build ios --debug --no-codesign`

**Step 2: Run on simulator**

Run: `flutter run -d C6B6E44C-1D0D-43F8-9DE0-0BB211FAFA62`

**Step 3: Visually verify each theme**

- Navigate to Profile -> Theme -> switch to each preset
- Verify: login screen, home, all news, notepad, recording panel, bottom nav
- Verify persistence: switch to Warm Pastel, kill app, relaunch — should stay on Warm Pastel

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: theme migration cleanup and visual polish"
```
