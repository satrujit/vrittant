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
      routerConfig: router,
    );
  }
}
