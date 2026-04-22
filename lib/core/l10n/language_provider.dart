import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum AppLanguage { odia, english }

const _kLanguageKey = 'app_language';

/// Global language notifier. Persists to SharedPreferences so the chosen
/// language survives app restarts.
class LanguageNotifier extends Notifier<AppLanguage> {
  @override
  AppLanguage build() {
    // Kick off async load from disk (non-blocking).
    Future.microtask(() => _loadFromDisk());
    return AppLanguage.english; // default to English
  }

  Future<void> _loadFromDisk() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_kLanguageKey);
    if (saved == 'odia') {
      state = AppLanguage.odia;
    } else {
      state = AppLanguage.english;
    }
  }

  void setLanguage(AppLanguage lang) {
    state = lang;
    // Persist asynchronously
    SharedPreferences.getInstance().then((prefs) {
      prefs.setString(_kLanguageKey, lang == AppLanguage.odia ? 'odia' : 'english');
    });
  }
}

final languageProvider =
    NotifierProvider<LanguageNotifier, AppLanguage>(LanguageNotifier.new);
