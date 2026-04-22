import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'app_theme_data.dart';

class ThemeNotifier extends Notifier<AppThemeData> {
  static const _prefKey = 'app_theme';

  @override
  AppThemeData build() {
    _loadSavedTheme();
    return warmPastelTheme;
  }

  Future<void> _loadSavedTheme() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = prefs.getString(_prefKey);
      if (key == null || key == 'classic') {
        // Migrate old 'classic' preference to warm_pastel (Vrittant redesign)
        await prefs.setString(_prefKey, 'warm_pastel');
        return; // already warm_pastel from build()
      }
      if (appThemePresets.containsKey(key)) {
        state = appThemePresets[key]!;
      }
    } catch (_) {}
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
