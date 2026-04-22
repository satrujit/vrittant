import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AutoPolishNotifier extends Notifier<bool> {
  static const _prefKey = 'auto_polish_enabled';

  @override
  bool build() {
    _loadFromDisk();
    // Off by default. Auto-polish runs an LLM pass on every committed
    // paragraph, which costs latency and tokens and can rewrite phrasing
    // a reporter wanted left alone. Users who want it can opt in via
    // Profile → Auto-Polish; the choice is persisted to SharedPreferences.
    return false;
  }

  Future<void> _loadFromDisk() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final val = prefs.getBool(_prefKey);
      if (val != null) state = val;
    } catch (_) {}
  }

  Future<void> toggle() async {
    state = !state;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, state);
    } catch (_) {}
  }
}

final autoPolishProvider =
    NotifierProvider<AutoPolishNotifier, bool>(AutoPolishNotifier.new);
