import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

class AppTypography {
  AppTypography._();

  // ===== English — Plus Jakarta Sans =====
  static TextStyle get displayLarge => GoogleFonts.plusJakartaSans(
    fontSize: 40,
    fontWeight: FontWeight.w800,
    letterSpacing: -1.5,
    color: AppColors.neutral800,
    height: 1.15,
  );

  static TextStyle get displayMedium => GoogleFonts.plusJakartaSans(
    fontSize: 32,
    fontWeight: FontWeight.w800,
    letterSpacing: -1.0,
    color: AppColors.neutral800,
    height: 1.2,
  );

  static TextStyle get headlineLarge => GoogleFonts.plusJakartaSans(
    fontSize: 26,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.5,
    color: AppColors.neutral800,
    height: 1.25,
  );

  static TextStyle get headlineMedium => GoogleFonts.plusJakartaSans(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: AppColors.neutral800,
    height: 1.3,
  );

  static TextStyle get titleLarge => GoogleFonts.plusJakartaSans(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.neutral800,
    height: 1.35,
  );

  static TextStyle get titleMedium => GoogleFonts.plusJakartaSans(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AppColors.neutral700,
    height: 1.4,
  );

  static TextStyle get bodyLarge => GoogleFonts.plusJakartaSans(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral600,
    height: 1.5,
  );

  static TextStyle get bodyMedium => GoogleFonts.plusJakartaSans(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral600,
    height: 1.5,
  );

  static TextStyle get bodySmall => GoogleFonts.plusJakartaSans(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral500,
    height: 1.5,
  );

  static TextStyle get labelLarge => GoogleFonts.plusJakartaSans(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: AppColors.neutral700,
  );

  static TextStyle get labelSmall => GoogleFonts.plusJakartaSans(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
    color: AppColors.neutral400,
  );

  static TextStyle get caption => GoogleFonts.plusJakartaSans(
    fontSize: 12,
    fontWeight: FontWeight.w500,
    color: AppColors.neutral500,
  );

  // ===== Odia — Headlines: Anek Odia =====
  static TextStyle get odiaHeadlineLarge => GoogleFonts.anekOdia(
    fontSize: 28,
    fontWeight: FontWeight.w800,
    color: AppColors.neutral800,
    height: 1.5,
  );

  static TextStyle get odiaHeadlineMedium => GoogleFonts.anekOdia(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: AppColors.neutral800,
    height: 1.5,
  );

  static TextStyle get odiaTitleLarge => GoogleFonts.anekOdia(
    fontSize: 19,
    fontWeight: FontWeight.w700,
    color: AppColors.neutral800,
    height: 1.5,
  );

  // ===== Odia — Body: Noto Sans Oriya =====
  static TextStyle get odiaBodyLarge => GoogleFonts.notoSansOriya(
    fontSize: 17,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral600,
    height: 1.7,
  );

  static TextStyle get odiaBodyMedium => GoogleFonts.notoSansOriya(
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral600,
    height: 1.6,
  );

  static TextStyle get odiaBodySmall => GoogleFonts.notoSansOriya(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AppColors.neutral500,
    height: 1.6,
  );
}
