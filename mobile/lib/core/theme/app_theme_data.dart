import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Holds every colour / gradient token the UI needs.
///
/// Three presets are provided: classic, warm_pastel, and dark.
class AppThemeData {
  const AppThemeData({
    // Identifiers
    required this.key,
    required this.label,
    required this.odiaLabel,
    // Scaffold
    required this.scaffoldBg,
    required this.cardBg,
    required this.dividerColor,
    // Primary
    required this.primary,
    required this.primaryLight,
    required this.primaryGradient,
    // Mic
    required this.micButtonColor,
    // Text
    required this.headingColor,
    required this.bodyColor,
    required this.mutedColor,
    required this.onPrimary,
    // Chips
    required this.aiChipBg,
    required this.aiChipText,
    required this.actionChipBg,
    required this.actionChipIcon,
    // Selection
    required this.selectedParaBg,
    required this.selectedParaBorder,
    // Recording
    required this.recordingBg,
    required this.waveformBarColor,
    required this.recordingTextColor,
    // Status
    required this.draftBg,
    required this.draftText,
    required this.submittedBg,
    required this.submittedText,
    // Nav
    required this.navBg,
    required this.navActiveColor,
    required this.navInactiveColor,
    // Header
    required this.headerBg,
    required this.headerGradient,
    // Brightness
    required this.brightness,
  });

  // ── Identifiers ──────────────────────────────────────────────────────
  final String key;
  final String label;
  final String odiaLabel;

  // ── Scaffold ─────────────────────────────────────────────────────────
  final Color scaffoldBg;
  final Color cardBg;
  final Color dividerColor;

  // ── Primary ──────────────────────────────────────────────────────────
  final Color primary;
  final Color primaryLight;
  final LinearGradient primaryGradient;

  // ── Mic ──────────────────────────────────────────────────────────────
  final Color micButtonColor;

  // ── Text ──────────────────────────────────────────────────────────────
  final Color headingColor;
  final Color bodyColor;
  final Color mutedColor;
  final Color onPrimary;

  // ── Chips ─────────────────────────────────────────────────────────────
  final Color aiChipBg;
  final Color aiChipText;
  final Color actionChipBg;
  final Color actionChipIcon;

  // ── Selection ─────────────────────────────────────────────────────────
  final Color selectedParaBg;
  final Color selectedParaBorder;

  // ── Recording ─────────────────────────────────────────────────────────
  final Color recordingBg;
  final Color waveformBarColor;
  final Color recordingTextColor;

  // ── Status ────────────────────────────────────────────────────────────
  final Color draftBg;
  final Color draftText;
  final Color submittedBg;
  final Color submittedText;

  // ── Nav ───────────────────────────────────────────────────────────────
  final Color navBg;
  final Color navActiveColor;
  final Color navInactiveColor;

  // ── Header ────────────────────────────────────────────────────────────
  final Color headerBg;
  final LinearGradient headerGradient;

  // ── Brightness ────────────────────────────────────────────────────────
  final Brightness brightness;
}

// ═══════════════════════════════════════════════════════════════════════════
// Presets
// ═══════════════════════════════════════════════════════════════════════════

/// **Classic** — the current indigo / teal look.
final classicTheme = AppThemeData(
  key: 'classic',
  label: 'Classic',
  odiaLabel: '\u0B15\u0B4D\u0B32\u0B3E\u0B38\u0B3F\u0B15\u0B4D',
  // Scaffold
  scaffoldBg: AppColors.neutral50,
  cardBg: AppColors.neutral0,
  dividerColor: AppColors.neutral200,
  // Primary
  primary: AppColors.indigo600,
  primaryLight: AppColors.indigo50,
  primaryGradient: const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.indigo600, AppColors.teal500],
  ),
  // Mic
  micButtonColor: AppColors.indigo600,
  // Text
  headingColor: AppColors.neutral800,
  bodyColor: AppColors.neutral600,
  mutedColor: AppColors.neutral400,
  onPrimary: AppColors.neutral0,
  // Chips
  aiChipBg: AppColors.indigo50,
  aiChipText: AppColors.indigo600,
  actionChipBg: AppColors.teal50,
  actionChipIcon: AppColors.teal500,
  // Selection
  selectedParaBg: AppColors.indigo50,
  selectedParaBorder: AppColors.indigo500,
  // Recording
  recordingBg: AppColors.coral50,
  waveformBarColor: AppColors.coral500,
  recordingTextColor: AppColors.coral600,
  // Status
  draftBg: AppColors.gold50,
  draftText: AppColors.gold600,
  submittedBg: AppColors.teal50,
  submittedText: AppColors.teal600,
  // Nav
  navBg: AppColors.neutral0,
  navActiveColor: AppColors.indigo600,
  navInactiveColor: AppColors.neutral400,
  // Header
  headerBg: AppColors.indigo800,
  headerGradient: const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      AppColors.indigo800,
      Color(0xFF312E81),
      AppColors.indigo700,
      AppColors.teal600,
    ],
  ),
  // Brightness
  brightness: Brightness.light,
);

/// **Warm Pastel** — Vrittant reference: muted coral, clean white, warm accents.
final warmPastelTheme = AppThemeData(
  key: 'warm_pastel',
  label: 'Warm Pastel',
  odiaLabel: '\u0B09\u0B37\u0B4D\u0B23 \u0B2A\u0B4D\u0B5F\u0B3E\u0B38\u0B4D\u0B1F\u0B47\u0B32\u0B4D',
  scaffoldBg: AppColors.neutral0,          // #FFFFFF — clean white
  cardBg: AppColors.neutral0,              // #FFFFFF
  dividerColor: AppColors.vrCardBorder,    // #F0EBE6
  primary: AppColors.vrCoral,              // #FA6C38 — brand coral
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

/// **Dark** — neutral900 scaffold, coral400 accent, light text.
final darkTheme = AppThemeData(
  key: 'dark',
  label: 'Dark',
  odiaLabel: '\u0B05\u0B28\u0B4D\u0B27\u0B3E\u0B30',
  // Scaffold
  scaffoldBg: AppColors.neutral900,
  cardBg: AppColors.neutral800,
  dividerColor: AppColors.neutral700,
  // Primary
  primary: AppColors.coral400,
  primaryLight: const Color(0xFF3D2520),
  primaryGradient: const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.coral400, AppColors.pink400],
  ),
  // Mic
  micButtonColor: AppColors.coral400,
  // Text
  headingColor: AppColors.neutral100,
  bodyColor: AppColors.neutral300,
  mutedColor: AppColors.neutral500,
  onPrimary: AppColors.neutral0,
  // Chips
  aiChipBg: const Color(0xFF3D2520),
  aiChipText: AppColors.coral300,
  actionChipBg: const Color(0xFF1A332E),
  actionChipIcon: AppColors.teal400,
  // Selection
  selectedParaBg: const Color(0xFF3D2520),
  selectedParaBorder: AppColors.coral400,
  // Recording
  recordingBg: const Color(0xFF3D2520),
  waveformBarColor: AppColors.coral400,
  recordingTextColor: AppColors.coral300,
  // Status
  draftBg: const Color(0xFF3D3015),
  draftText: AppColors.gold300,
  submittedBg: const Color(0xFF1A332E),
  submittedText: AppColors.teal300,
  // Nav
  navBg: AppColors.neutral900,
  navActiveColor: AppColors.coral400,
  navInactiveColor: AppColors.neutral500,
  // Header
  headerBg: AppColors.neutral800,
  headerGradient: const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.neutral800, AppColors.neutral900],
  ),
  // Brightness
  brightness: Brightness.dark,
);

// ═══════════════════════════════════════════════════════════════════════════
// Preset lookup map
// ═══════════════════════════════════════════════════════════════════════════

final appThemePresets = <String, AppThemeData>{
  'classic': classicTheme,
  'warm_pastel': warmPastelTheme,
  'dark': darkTheme,
};
