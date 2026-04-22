import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppGradients {
  AppGradients._();

  // ===== 8 Named Gradients =====
  static const sambalpuriNight = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      AppColors.indigo800,
      Color(0xFF312E81),
      AppColors.indigo700,
      AppColors.teal600,
    ],
  );

  static const kashmir = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.teal700, AppColors.teal500, AppColors.indigo400],
  );

  static const electricPulse = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.coral500, AppColors.pink500, AppColors.lavender500],
  );

  static const lavenderFields = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.lavender300, AppColors.lavender500, AppColors.indigo400],
  );

  static const sunriseGlow = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.gold300, AppColors.coral400, AppColors.pink400],
  );

  static const goldenHour = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.gold200, AppColors.gold400, AppColors.coral500],
  );

  static const aurora = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.teal300, AppColors.lime300, AppColors.teal400],
  );

  static const softMist = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.neutral100, AppColors.indigo50, AppColors.teal50],
  );

  // ===== Brand accent gradient =====
  static const brandAccent = LinearGradient(
    colors: [AppColors.teal300, AppColors.lime300],
  );

  // ===== Primary button gradient =====
  static const primaryButton = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [AppColors.indigo600, AppColors.teal500],
  );

  // ===== Category gradients =====
  static const politics = LinearGradient(
    colors: [AppColors.indigo500, AppColors.lavender500],
  );
  static const sports = LinearGradient(
    colors: [AppColors.teal500, AppColors.lime400],
  );
  static const crime = LinearGradient(
    colors: [AppColors.coral500, AppColors.pink500],
  );
  static const business = LinearGradient(
    colors: [AppColors.gold500, AppColors.coral400],
  );
  static const entertainment = LinearGradient(
    colors: [AppColors.pink400, AppColors.lavender400],
  );
  static const education = LinearGradient(
    colors: [AppColors.teal400, AppColors.indigo400],
  );
  static const health = LinearGradient(
    colors: [AppColors.lime400, AppColors.teal400],
  );
  static const technology = LinearGradient(
    colors: [AppColors.indigo400, AppColors.teal300],
  );

  static LinearGradient forCategory(String category) {
    return switch (category.toLowerCase()) {
      'politics' => politics,
      'sports' => sports,
      'crime' => crime,
      'business' => business,
      'entertainment' => entertainment,
      'education' => education,
      'health' => health,
      'technology' => technology,
      _ => primaryButton,
    };
  }
}
