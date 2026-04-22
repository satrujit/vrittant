# Vrittant UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the entire app to match the Vrittant reference screenshots — new colors, proper visual hierarchy, clean headers, 6-box OTP, sorted stories, no trash icons, floating FAB.

**Architecture:** Update theme tokens first, then rewrite each screen top-down. No new packages needed except `google_fonts` (already present) for Playfair Display serif headlines.

**Tech Stack:** Flutter, Riverpod, GoRouter, google_fonts, lucide_icons

---

### Task 1: Update Theme Tokens

**Files:**
- Modify: `lib/core/theme/app_theme_data.dart`
- Modify: `lib/core/theme/app_colors.dart`

**Step 1: Add new colors to AppColors**

Add to `app_colors.dart` after existing colors:

```dart
// ===== Vrittant Reference Palette =====
static const vrCoral = Color(0xFFD4714A);
static const vrCoralLight = Color(0xFFFDEEE8);
static const vrCoralMuted = Color(0xFFE8A87C);
static const vrWarmBg = Color(0xFFFEF7F2);
static const vrCardBorder = Color(0xFFF0EBE6);
static const vrAccentIndigo = Color(0xFF3D3B8E);
static const vrHeading = Color(0xFF1C1917);
static const vrBody = Color(0xFF44403C);
static const vrMuted = Color(0xFFA8A29E);
static const vrSection = Color(0xFF78716C);
static const vrBadgeBorder = Color(0xFFD6D3D1);
```

**Step 2: Update warmPastelTheme with exact reference colors**

Replace the entire `warmPastelTheme` definition:

```dart
final warmPastelTheme = AppThemeData(
  key: 'warm_pastel',
  label: 'Warm Pastel',
  odiaLabel: '\u0B09\u0B37\u0B4D\u0B23 \u0B2A\u0B4D\u0B5F\u0B3E\u0B38\u0B4D\u0B1F\u0B47\u0B32\u0B4D',
  scaffoldBg: AppColors.neutral0,          // #FFFFFF — clean white
  cardBg: AppColors.neutral0,              // #FFFFFF
  dividerColor: AppColors.vrCardBorder,    // #F0EBE6
  primary: AppColors.vrCoral,              // #D4714A — muted warm coral
  primaryLight: AppColors.vrCoralLight,    // #FDEEE8
  primaryGradient: const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.vrCoral, AppColors.vrCoralMuted],
  ),
  micButtonColor: AppColors.vrCoral,
  headingColor: AppColors.vrHeading,       // #1C1917
  bodyColor: AppColors.vrBody,             // #44403C
  mutedColor: AppColors.vrMuted,           // #A8A29E
  onPrimary: AppColors.neutral0,
  aiChipBg: AppColors.vrCoralLight,
  aiChipText: AppColors.vrCoral,
  actionChipBg: AppColors.vrCoralLight,
  actionChipIcon: AppColors.vrCoral,
  selectedParaBg: AppColors.vrCoralLight,
  selectedParaBorder: AppColors.vrCoral,
  recordingBg: AppColors.vrCoralLight,
  waveformBarColor: AppColors.vrCoral,
  recordingTextColor: AppColors.vrCoral,
  draftBg: AppColors.vrCoralLight,
  draftText: AppColors.vrCoral,
  submittedBg: const Color(0xFFF0F0F0),
  submittedText: AppColors.vrSection,
  navBg: AppColors.neutral0,
  navActiveColor: AppColors.vrHeading,     // #1C1917 — dark active
  navInactiveColor: AppColors.vrMuted,     // #A8A29E
  headerBg: AppColors.neutral0,            // WHITE — no more dark header
  headerGradient: const LinearGradient(
    colors: [AppColors.neutral0, AppColors.neutral0],
  ),
  brightness: Brightness.light,
);
```

**Step 3: Commit**

```bash
git add lib/core/theme/app_colors.dart lib/core/theme/app_theme_data.dart
git commit -m "feat: update warm pastel theme with exact Vrittant reference colors"
```

---

### Task 2: Rebrand to Vrittant + Update Bottom Nav to 4 Tabs

**Files:**
- Modify: `lib/app.dart` (title)
- Modify: `lib/core/widgets/app_bottom_nav.dart` (4 tabs)
- Modify: `lib/core/router/app_router.dart` (add /files route)
- Modify: `lib/features/auth/screens/login_screen.dart` (title text)

**Step 1: Update app.dart title**

Change `'Vrittant'` title (already done) — verify it says Vrittant not NewsFlow.

**Step 2: Update login_screen.dart title**

Replace the ShaderMask text from `'NewsFlow'` to `'Vrittant'`.

**Step 3: Rewrite app_bottom_nav.dart with 4 tabs**

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/theme_extensions.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final uri = GoRouterState.of(context).uri.toString();
    if (uri.startsWith('/all-news')) return 1;
    if (uri.startsWith('/files')) return 2;
    if (uri.startsWith('/profile')) return 3;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final index = _currentIndex(context);
    final t = context.t;
    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: t.navBg,
          border: Border(top: BorderSide(color: t.dividerColor, width: 0.5)),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(icon: LucideIcons.home, label: 'HOME', isActive: index == 0, onTap: () => context.go('/home')),
                _NavItem(icon: LucideIcons.list, label: 'ALL STORIES', isActive: index == 1, onTap: () => context.go('/all-news')),
                _NavItem(icon: LucideIcons.folderOpen, label: 'FILES', isActive: index == 2, onTap: () => context.go('/files')),
                _NavItem(icon: LucideIcons.settings, label: 'SETTINGS', isActive: index == 3, onTap: () => context.go('/profile')),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

The `_NavItem` widget: use uppercase English labels, fontSize 9, letterSpacing 0.5, fontWeight w600 for active / w500 for inactive.

**Step 4: Add /files placeholder route to app_router.dart**

Add inside ShellRoute routes:
```dart
GoRoute(path: '/files', builder: (_, __) => const Scaffold(body: Center(child: Text('Files')))),
```

**Step 5: Commit**

---

### Task 3: Redesign Home Screen

**Files:**
- Modify: `lib/features/home/screens/home_screen.dart`

This is the biggest change. The home screen needs to match the reference:

**New layout structure:**
1. **Header area** (white bg, SafeArea):
   - Left: "Vrittant" in dark bold 24px + "GLOBAL REPORTER" in coral uppercase 11px below
   - Right: Search icon + profile avatar circle
2. **"ACTIVE PROJECTS" section** (if any in-progress stories):
   - Section label: uppercase, `vrSection` color, 11px, letterSpacing 1.0
   - Right: "X Total" in same style
   - Cards: white bg, subtle border, **3px left indigo accent bar** (`vrAccentIndigo`), headline text, "IN PROGRESS" coral badge (outlined), "CONTINUE RECORDING" coral text link with mic icon
3. **"ALL STORIES" section**:
   - Label left + "Filter" coral link right
   - Cards: headline + outlined status badge
4. **Floating Action Button**: coral circle, white mic icon, positioned bottom-right

**Key implementation details:**
- Remove the old `_buildHeader()` with dark `headerBg`
- Remove `_buildCreateButton()` gradient button
- Replace with clean white header + floating FAB
- Cards use `Container` with `decoration: BoxDecoration(border: Border(left: BorderSide(color: vrAccentIndigo, width: 3)))` for active projects
- Status badges: outlined with `Border.all` instead of filled background
- "CONTINUE RECORDING" = `Row(children: [Icon(mic), Text()])` in coral

**Step: Commit**

---

### Task 4: Redesign All News Screen

**Files:**
- Modify: `lib/features/all_news/screens/all_news_screen.dart`

**Changes:**
1. **Remove dark header** — replace `_buildHeader()` with white bg title
2. **Sort stories** before grouping: `stories.sort((a, b) => b.createdAt.compareTo(a.createdAt))` in `_buildGroupedStoryWidgets`
3. **Remove inline trash icons** — delete the entire `if (story.status == 'draft')` block with trash icon (lines 538-548)
4. **Smaller date section labels**: change from `odiaTitleLarge.copyWith(fontSize: 17)` to uppercase style: `labelSmall.copyWith(fontSize: 11, letterSpacing: 1.0, color: vrSection)`
5. **Status badges**: outlined style instead of filled

**Step: Commit**

---

### Task 5: Build 6-Box OTP Input on Login Screen

**Files:**
- Modify: `lib/features/auth/screens/login_screen.dart`

**Replace** the single OTP TextFormField with a custom 6-box Row:

```dart
Widget _buildOtpBoxes() {
  return Row(
    mainAxisAlignment: MainAxisAlignment.spaceBetween,
    children: List.generate(6, (i) {
      return SizedBox(
        width: 48,
        height: 56,
        child: TextField(
          controller: _otpControllers[i],
          keyboardType: TextInputType.number,
          textAlign: TextAlign.center,
          maxLength: 1,
          style: AppTypography.headlineMedium.copyWith(color: t.headingColor),
          decoration: InputDecoration(
            counterText: '',
            filled: true,
            fillColor: t.cardBg,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              borderSide: BorderSide(color: t.dividerColor),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              borderSide: BorderSide(color: t.dividerColor),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              borderSide: BorderSide(color: t.primary, width: 2),
            ),
          ),
          onChanged: (value) {
            if (value.isNotEmpty && i < 5) {
              FocusScope.of(context).nextFocus();
            }
            if (value.isEmpty && i > 0) {
              FocusScope.of(context).previousFocus();
            }
            // Combine all controllers into _otpController
            _otpController.text = _otpControllers.map((c) => c.text).join();
          },
        ),
      );
    }),
  );
}
```

Also change `_otpController` to a list of 6 controllers + single combined controller. Add `_otpControllers` list in state.

**Step: Commit**

---

### Task 6: Update Notepad Screen Background + Cleanup

**Files:**
- Modify: `lib/features/create_news/screens/notepad_screen.dart`

**Changes:**
- Scaffold bg should use `AppColors.vrWarmBg` (`#FEF7F2`) for warm paper feel — but since it uses `context.t.scaffoldBg` which is now white, add a new token `notepadBg` to AppThemeData or just hardcode `AppColors.vrWarmBg` for the notepad scaffold only.
- Best approach: the notepad already uses `context.t.scaffoldBg`. Since warmPastel scaffold is now #FFFFFF, override just notepad's scaffold to use the warm bg directly:
  ```dart
  backgroundColor: AppColors.vrWarmBg,
  ```

**Step: Commit**

---

### Task 7: Flutter Analyze + Hot Reload + Visual Verification

**Step 1:** Run `flutter analyze` — fix any errors
**Step 2:** Hot reload on simulator
**Step 3:** Take screenshots of every screen
**Step 4:** Compare against reference designs
**Step 5:** Final commit

---
