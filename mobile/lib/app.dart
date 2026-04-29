import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
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

    final baseTheme = AppTheme.light;
    final theme = baseTheme.copyWith(
      scaffoldBackgroundColor: t.scaffoldBg,
      colorScheme: baseTheme.colorScheme.copyWith(
        primary: t.primary,
        surface: t.cardBg,
        onSurface: t.headingColor,
      ),
      appBarTheme: baseTheme.appBarTheme.copyWith(
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
      // Force the app's locale to Odia (or-IN). On Android, Gboard / Samsung
      // Keyboard / most Indic IMEs auto-switch to the foreground app's
      // locale, so reporters land directly on the Odia layout in the
      // notepad without tapping the globe key. iOS doesn't expose a
      // programmatic keyboard-language switch, but since iOS is sticky
      // per text-field, the first manual switch is the only friction.
      locale: const Locale('or', 'IN'),
      supportedLocales: const [
        Locale('or', 'IN'),
        Locale('en', 'US'),
        Locale('hi', 'IN'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: router,
    );
  }
}
