import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app_theme_data.dart';
import 'theme_provider.dart';

extension ThemeX on BuildContext {
  AppThemeData get t {
    return ProviderScope.containerOf(this).read(themeProvider);
  }
}
