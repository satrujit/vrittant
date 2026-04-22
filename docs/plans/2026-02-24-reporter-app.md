# NewsFlow Reporter App — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Flutter Reporter mobile app with voice dictation, news submission wizard, offline storage, and the v2 multi-hue design system.

**Architecture:** Feature-first folder structure under `lib/`. Riverpod for state management (manual providers, no codegen). GoRouter for navigation. Hive for offline-first local storage. Dio for API calls. Design system tokens in a dedicated `core/theme/` module.

**Tech Stack:** Flutter 3.41.2, Dart 3.11, flutter_riverpod, go_router, shadcn_ui, google_fonts (Inter + Anek Odia + Noto Sans Oriya), lucide_icons, hive_flutter, dio, mesh_gradient, glass_kit, shimmer

---

## Folder Structure

```
lib/
├── main.dart
├── app.dart                          # ProviderScope + MaterialApp.router
├── core/
│   ├── theme/
│   │   ├── app_colors.dart           # All 7 color families + semantics
│   │   ├── app_gradients.dart        # 8 named gradients + category gradients
│   │   ├── app_typography.dart       # Inter + Odia type scale
│   │   ├── app_theme.dart            # ThemeData assembly
│   │   └── app_spacing.dart          # 4px grid spacing constants
│   ├── router/
│   │   └── app_router.dart           # GoRouter config
│   ├── constants/
│   │   └── app_constants.dart        # API URLs, enums
│   └── widgets/                      # Shared reusable widgets
│       ├── gradient_button.dart
│       ├── glass_card.dart
│       ├── status_chip.dart
│       ├── category_chip.dart
│       ├── news_card.dart
│       ├── voice_button.dart
│       ├── app_bottom_nav.dart
│       └── gradient_app_bar.dart
├── features/
│   ├── auth/
│   │   ├── screens/
│   │   │   └── login_screen.dart
│   │   └── providers/
│   │       └── auth_provider.dart
│   ├── home/
│   │   ├── screens/
│   │   │   └── home_screen.dart
│   │   └── providers/
│   │       └── home_provider.dart
│   ├── create_news/
│   │   ├── screens/
│   │   │   ├── create_news_screen.dart    # 4-step wizard shell
│   │   │   ├── step_voice.dart            # Step 1: Voice dictation
│   │   │   ├── step_details.dart          # Step 2: Title, category, priority
│   │   │   ├── step_media.dart            # Step 3: Attach photos/video/docs
│   │   │   └── step_review.dart           # Step 4: Review & submit
│   │   └── providers/
│   │       └── create_news_provider.dart
│   ├── submissions/
│   │   ├── screens/
│   │   │   ├── submissions_screen.dart
│   │   │   └── news_detail_screen.dart
│   │   └── providers/
│   │       └── submissions_provider.dart
│   └── profile/
│       ├── screens/
│       │   └── profile_screen.dart
│       └── providers/
│           └── profile_provider.dart
└── models/
    ├── news_article.dart
    ├── user.dart
    └── category.dart
```

---

### Task 1: Design System — Colors & Gradients

**Files:**
- Create: `lib/core/theme/app_colors.dart`
- Create: `lib/core/theme/app_gradients.dart`
- Create: `lib/core/theme/app_spacing.dart`

**Step 1: Create app_colors.dart**

```dart
import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // ===== Primary — Deep Indigo (Sambalpuri ikat) =====
  static const indigo50  = Color(0xFFEEF2FF);
  static const indigo100 = Color(0xFFE0E7FF);
  static const indigo200 = Color(0xFFC7D2FE);
  static const indigo300 = Color(0xFFA5B4FC);
  static const indigo400 = Color(0xFF818CF8);
  static const indigo500 = Color(0xFF6366F1);
  static const indigo600 = Color(0xFF4F46E5);
  static const indigo700 = Color(0xFF4338CA);
  static const indigo800 = Color(0xFF1E1B4B);
  static const indigo900 = Color(0xFF0F0A2E);

  // ===== Teal — Kashmir =====
  static const teal50  = Color(0xFFF0FDFA);
  static const teal100 = Color(0xFFCCFBF1);
  static const teal200 = Color(0xFF99F6E4);
  static const teal300 = Color(0xFF5EEAD4);
  static const teal400 = Color(0xFF2DD4BF);
  static const teal500 = Color(0xFF14B8A6);
  static const teal600 = Color(0xFF0D9488);
  static const teal700 = Color(0xFF004B3D);

  // ===== Coral — Sunrise/Electric =====
  static const coral50  = Color(0xFFFFF5F2);
  static const coral100 = Color(0xFFFFE4DE);
  static const coral200 = Color(0xFFFFBFB0);
  static const coral300 = Color(0xFFFF9A85);
  static const coral400 = Color(0xFFFF7A5C);
  static const coral500 = Color(0xFFFF5733);
  static const coral600 = Color(0xFFE0421F);

  // ===== Gold =====
  static const gold50  = Color(0xFFFFFBEB);
  static const gold100 = Color(0xFFFEF3C7);
  static const gold200 = Color(0xFFFDE68A);
  static const gold300 = Color(0xFFFCD34D);
  static const gold400 = Color(0xFFFBBF24);
  static const gold500 = Color(0xFFF59E0B);
  static const gold600 = Color(0xFFD97706);

  // ===== Pink =====
  static const pink50  = Color(0xFFFFF1F2);
  static const pink100 = Color(0xFFFFE4E6);
  static const pink200 = Color(0xFFFECDD3);
  static const pink300 = Color(0xFFFDA4AF);
  static const pink400 = Color(0xFFFB7185);
  static const pink500 = Color(0xFFF43F5E);
  static const pink600 = Color(0xFFE11D48);

  // ===== Lavender =====
  static const lavender50  = Color(0xFFFAF5FF);
  static const lavender100 = Color(0xFFF3E8FF);
  static const lavender200 = Color(0xFFE9D5FF);
  static const lavender300 = Color(0xFFD8B4FE);
  static const lavender400 = Color(0xFFC084FC);
  static const lavender500 = Color(0xFFA855F7);
  static const lavender600 = Color(0xFF7C3AED);

  // ===== Lime =====
  static const lime50  = Color(0xFFF7FEE7);
  static const lime100 = Color(0xFFECFCCB);
  static const lime200 = Color(0xFFD9F99D);
  static const lime300 = Color(0xFFBEF264);
  static const lime400 = Color(0xFFA3E635);
  static const lime500 = Color(0xFF84CC16);

  // ===== Neutral — Warm Stone =====
  static const neutral0   = Color(0xFFFFFFFF);
  static const neutral50  = Color(0xFFFAFAF9);
  static const neutral100 = Color(0xFFF5F5F4);
  static const neutral200 = Color(0xFFE7E5E4);
  static const neutral300 = Color(0xFFD6D3D1);
  static const neutral400 = Color(0xFFA8A29E);
  static const neutral500 = Color(0xFF78716C);
  static const neutral600 = Color(0xFF57534E);
  static const neutral700 = Color(0xFF44403C);
  static const neutral800 = Color(0xFF292524);
  static const neutral900 = Color(0xFF1C1917);

  // ===== Semantic =====
  static const success = Color(0xFF22C55E);
  static const warning = Color(0xFFF59E0B);
  static const error   = Color(0xFFEF4444);
  static const info    = Color(0xFF3B82F6);
}
```

**Step 2: Create app_gradients.dart**

```dart
import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppGradients {
  AppGradients._();

  // ===== 8 Named Gradients =====
  static const sambalpuriNight = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.indigo800, Color(0xFF312E81), AppColors.indigo700, AppColors.teal600],
  );

  static const kashmir = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.teal700, AppColors.teal500, AppColors.indigo400],
  );

  static const electricPulse = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.coral500, AppColors.pink500, AppColors.lavender500],
  );

  static const lavenderFields = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.lavender300, AppColors.lavender500, AppColors.indigo400],
  );

  static const sunriseGlow = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.gold300, AppColors.coral400, AppColors.pink400],
  );

  static const goldenHour = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.gold200, AppColors.gold400, AppColors.coral500],
  );

  static const aurora = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.teal300, AppColors.lime300, AppColors.teal400],
  );

  static const softMist = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.neutral100, AppColors.indigo50, AppColors.teal50],
  );

  // ===== Brand accent text gradient colors =====
  static const brandAccent = LinearGradient(
    colors: [AppColors.teal300, AppColors.lime300],
  );

  // ===== Primary button gradient =====
  static const primaryButton = LinearGradient(
    begin: Alignment.topLeft, end: Alignment.bottomRight,
    colors: [AppColors.indigo600, AppColors.teal500],
  );

  // ===== Category gradients =====
  static const politics      = LinearGradient(colors: [AppColors.indigo500, AppColors.lavender500]);
  static const sports         = LinearGradient(colors: [AppColors.teal500, AppColors.lime400]);
  static const crime          = LinearGradient(colors: [AppColors.coral500, AppColors.pink500]);
  static const business       = LinearGradient(colors: [AppColors.gold500, AppColors.coral400]);
  static const entertainment  = LinearGradient(colors: [AppColors.pink400, AppColors.lavender400]);
  static const education      = LinearGradient(colors: [AppColors.teal400, AppColors.indigo400]);
  static const health         = LinearGradient(colors: [AppColors.lime400, AppColors.teal400]);
  static const technology     = LinearGradient(colors: [AppColors.indigo400, AppColors.teal300]);

  static LinearGradient forCategory(String category) {
    return switch (category.toLowerCase()) {
      'politics'      => politics,
      'sports'        => sports,
      'crime'         => crime,
      'business'      => business,
      'entertainment' => entertainment,
      'education'     => education,
      'health'        => health,
      'technology'    => technology,
      _               => primaryButton,
    };
  }
}
```

**Step 3: Create app_spacing.dart**

```dart
class AppSpacing {
  AppSpacing._();

  static const double xs  = 4;
  static const double sm  = 8;
  static const double md  = 12;
  static const double base = 16;
  static const double lg  = 20;
  static const double xl  = 24;
  static const double xxl = 32;
  static const double xxxl = 40;
  static const double huge = 48;
  static const double massive = 64;

  // Border radii
  static const double radiusSm  = 8;
  static const double radiusMd  = 12;
  static const double radiusLg  = 16;
  static const double radiusXl  = 20;
  static const double radiusXxl = 24;
  static const double radiusFull = 999;
}
```

**Step 4: Verify files compile**

Run: `cd /Users/admin/Desktop/newsflow && dart analyze lib/core/theme/`
Expected: No errors

**Step 5: Commit**

```bash
git add lib/core/theme/app_colors.dart lib/core/theme/app_gradients.dart lib/core/theme/app_spacing.dart
git commit -m "feat: add design system color tokens, gradients, and spacing"
```

---

### Task 2: Design System — Typography & Theme

**Files:**
- Create: `lib/core/theme/app_typography.dart`
- Create: `lib/core/theme/app_theme.dart`

**Step 1: Create app_typography.dart**

```dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

class AppTypography {
  AppTypography._();

  // ===== English — Inter =====
  static TextStyle get displayLarge => GoogleFonts.inter(
    fontSize: 40, fontWeight: FontWeight.w800, letterSpacing: -1.5, color: AppColors.neutral800, height: 1.15,
  );
  static TextStyle get displayMedium => GoogleFonts.inter(
    fontSize: 32, fontWeight: FontWeight.w800, letterSpacing: -1.0, color: AppColors.neutral800, height: 1.2,
  );
  static TextStyle get headlineLarge => GoogleFonts.inter(
    fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: AppColors.neutral800, height: 1.25,
  );
  static TextStyle get headlineMedium => GoogleFonts.inter(
    fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.neutral800, height: 1.3,
  );
  static TextStyle get titleLarge => GoogleFonts.inter(
    fontSize: 18, fontWeight: FontWeight.w600, color: AppColors.neutral800, height: 1.35,
  );
  static TextStyle get titleMedium => GoogleFonts.inter(
    fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.neutral700, height: 1.4,
  );
  static TextStyle get bodyLarge => GoogleFonts.inter(
    fontSize: 16, fontWeight: FontWeight.w400, color: AppColors.neutral600, height: 1.5,
  );
  static TextStyle get bodyMedium => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w400, color: AppColors.neutral600, height: 1.5,
  );
  static TextStyle get bodySmall => GoogleFonts.inter(
    fontSize: 12, fontWeight: FontWeight.w400, color: AppColors.neutral500, height: 1.5,
  );
  static TextStyle get labelLarge => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.neutral700,
  );
  static TextStyle get labelSmall => GoogleFonts.inter(
    fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.5, color: AppColors.neutral400,
  );
  static TextStyle get caption => GoogleFonts.inter(
    fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.neutral500,
  );

  // ===== Odia — Headlines: Anek Odia =====
  static TextStyle get odiaHeadlineLarge => GoogleFonts.anekOdia(
    fontSize: 28, fontWeight: FontWeight.w800, color: AppColors.neutral800, height: 1.5,
  );
  static TextStyle get odiaHeadlineMedium => GoogleFonts.anekOdia(
    fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.neutral800, height: 1.5,
  );
  static TextStyle get odiaTitleLarge => GoogleFonts.anekOdia(
    fontSize: 19, fontWeight: FontWeight.w700, color: AppColors.neutral800, height: 1.5,
  );

  // ===== Odia — Body: Noto Sans Oriya =====
  static TextStyle get odiaBodyLarge => GoogleFonts.notoSansOriya(
    fontSize: 17, fontWeight: FontWeight.w400, color: AppColors.neutral600, height: 1.7,
  );
  static TextStyle get odiaBodyMedium => GoogleFonts.notoSansOriya(
    fontSize: 15, fontWeight: FontWeight.w400, color: AppColors.neutral600, height: 1.6,
  );
  static TextStyle get odiaBodySmall => GoogleFonts.notoSansOriya(
    fontSize: 13, fontWeight: FontWeight.w400, color: AppColors.neutral500, height: 1.6,
  );
}
```

**Step 2: Create app_theme.dart**

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';
import 'app_typography.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.neutral50,
      colorScheme: const ColorScheme.light(
        primary: AppColors.indigo500,
        onPrimary: Colors.white,
        primaryContainer: AppColors.indigo100,
        secondary: AppColors.teal500,
        onSecondary: Colors.white,
        secondaryContainer: AppColors.teal100,
        surface: AppColors.neutral0,
        onSurface: AppColors.neutral800,
        error: AppColors.error,
        onError: Colors.white,
        outline: AppColors.neutral200,
        outlineVariant: AppColors.neutral100,
      ),
      textTheme: TextTheme(
        displayLarge: AppTypography.displayLarge,
        displayMedium: AppTypography.displayMedium,
        headlineLarge: AppTypography.headlineLarge,
        headlineMedium: AppTypography.headlineMedium,
        titleLarge: AppTypography.titleLarge,
        titleMedium: AppTypography.titleMedium,
        bodyLarge: AppTypography.bodyLarge,
        bodyMedium: AppTypography.bodyMedium,
        bodySmall: AppTypography.bodySmall,
        labelLarge: AppTypography.labelLarge,
        labelSmall: AppTypography.labelSmall,
      ),
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: Colors.transparent,
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle: AppTypography.titleLarge,
        iconTheme: const IconThemeData(color: AppColors.neutral800),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        color: AppColors.neutral0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.neutral50,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.neutral200, width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.neutral200, width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.indigo500, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: AppTypography.bodyMedium.copyWith(color: AppColors.neutral400),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: AppTypography.labelLarge.copyWith(color: Colors.white),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.transparent,
        elevation: 0,
        selectedItemColor: AppColors.indigo600,
        unselectedItemColor: AppColors.neutral400,
        type: BottomNavigationBarType.fixed,
      ),
    );
  }
}
```

**Step 3: Verify files compile**

Run: `cd /Users/admin/Desktop/newsflow && dart analyze lib/core/theme/`
Expected: No errors

**Step 4: Commit**

```bash
git add lib/core/theme/app_typography.dart lib/core/theme/app_theme.dart
git commit -m "feat: add typography scale and theme configuration"
```

---

### Task 3: Models

**Files:**
- Create: `lib/models/news_article.dart`
- Create: `lib/models/user.dart`
- Create: `lib/models/category.dart`

**Step 1: Create models**

```dart
// lib/models/category.dart
import 'package:flutter/material.dart';
import '../core/theme/app_gradients.dart';

enum NewsCategory {
  politics('Politics', 'ରାଜନୀତି'),
  sports('Sports', 'କ୍ରୀଡ଼ା'),
  crime('Crime', 'ଅପରାଧ'),
  business('Business', 'ବ୍ୟବସାୟ'),
  entertainment('Entertainment', 'ମନୋରଞ୍ଜନ'),
  education('Education', 'ଶିକ୍ଷା'),
  health('Health', 'ସ୍ୱାସ୍ଥ୍ୟ'),
  technology('Technology', 'ପ୍ରଯୁକ୍ତି');

  final String label;
  final String odiaLabel;
  const NewsCategory(this.label, this.odiaLabel);

  LinearGradient get gradient => AppGradients.forCategory(name);
}

enum NewsPriority { normal, urgent, breaking }

enum NewsStatus { draft, submitted, approved, rejected, published }
```

```dart
// lib/models/news_article.dart
import 'category.dart';

class NewsArticle {
  final String id;
  final String title;
  final String body;
  final String? titleOdia;
  final String? bodyOdia;
  final NewsCategory category;
  final NewsPriority priority;
  final NewsStatus status;
  final String reporterId;
  final String? location;
  final List<String> mediaUrls;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? rejectionReason;

  const NewsArticle({
    required this.id,
    required this.title,
    required this.body,
    this.titleOdia,
    this.bodyOdia,
    required this.category,
    this.priority = NewsPriority.normal,
    this.status = NewsStatus.draft,
    required this.reporterId,
    this.location,
    this.mediaUrls = const [],
    required this.createdAt,
    required this.updatedAt,
    this.rejectionReason,
  });

  NewsArticle copyWith({
    String? id,
    String? title,
    String? body,
    String? titleOdia,
    String? bodyOdia,
    NewsCategory? category,
    NewsPriority? priority,
    NewsStatus? status,
    String? reporterId,
    String? location,
    List<String>? mediaUrls,
    DateTime? createdAt,
    DateTime? updatedAt,
    String? rejectionReason,
  }) {
    return NewsArticle(
      id: id ?? this.id,
      title: title ?? this.title,
      body: body ?? this.body,
      titleOdia: titleOdia ?? this.titleOdia,
      bodyOdia: bodyOdia ?? this.bodyOdia,
      category: category ?? this.category,
      priority: priority ?? this.priority,
      status: status ?? this.status,
      reporterId: reporterId ?? this.reporterId,
      location: location ?? this.location,
      mediaUrls: mediaUrls ?? this.mediaUrls,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      rejectionReason: rejectionReason ?? this.rejectionReason,
    );
  }
}
```

```dart
// lib/models/user.dart
class User {
  final String id;
  final String name;
  final String phone;
  final String? email;
  final String? avatarUrl;
  final String orgId;
  final String orgName;

  const User({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.avatarUrl,
    required this.orgId,
    required this.orgName,
  });
}
```

**Step 2: Verify**

Run: `cd /Users/admin/Desktop/newsflow && dart analyze lib/models/`
Expected: No errors

**Step 3: Commit**

```bash
git add lib/models/
git commit -m "feat: add data models for news, user, and categories"
```

---

### Task 4: Router & App Shell

**Files:**
- Create: `lib/core/router/app_router.dart`
- Create: `lib/app.dart`
- Modify: `lib/main.dart`
- Create: `lib/core/widgets/app_bottom_nav.dart`
- Create: `lib/features/home/screens/home_screen.dart` (placeholder)
- Create: `lib/features/submissions/screens/submissions_screen.dart` (placeholder)
- Create: `lib/features/profile/screens/profile_screen.dart` (placeholder)
- Create: `lib/features/create_news/screens/create_news_screen.dart` (placeholder)

**Step 1: Create app_router.dart with GoRouter + shell route for bottom nav**

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../features/home/screens/home_screen.dart';
import '../../features/submissions/screens/submissions_screen.dart';
import '../../features/profile/screens/profile_screen.dart';
import '../../features/create_news/screens/create_news_screen.dart';
import '../widgets/app_bottom_nav.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/home',
  routes: [
    ShellRoute(
      navigatorKey: _shellNavigatorKey,
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
        GoRoute(path: '/submissions', builder: (_, __) => const SubmissionsScreen()),
        GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
      ],
    ),
    GoRoute(
      path: '/create',
      parentNavigatorKey: _rootNavigatorKey,
      builder: (_, __) => const CreateNewsScreen(),
    ),
  ],
);
```

**Step 2: Create AppShell (bottom nav wrapper) in app_bottom_nav.dart**

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_colors.dart';
import '../theme/app_gradients.dart';
import '../theme/app_spacing.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    if (location.startsWith('/submissions')) return 1;
    if (location.startsWith('/profile')) return 2;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final index = _currentIndex(context);
    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.92),
          border: Border(top: BorderSide(color: AppColors.neutral100)),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.base, vertical: AppSpacing.sm),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(icon: LucideIcons.home, label: 'Home', active: index == 0,
                  onTap: () => context.go('/home')),
                _NavItem(icon: LucideIcons.fileText, label: 'My News', active: index == 1,
                  onTap: () => context.go('/submissions')),
                _CreateButton(onTap: () => context.push('/create')),
                _NavItem(icon: LucideIcons.user, label: 'Profile', active: index == 2,
                  onTap: () => context.go('/profile')),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _NavItem({required this.icon, required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 22, color: active ? AppColors.indigo600 : AppColors.neutral400),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500,
            color: active ? AppColors.indigo600 : AppColors.neutral400)),
        ],
      ),
    );
  }
}

class _CreateButton extends StatelessWidget {
  final VoidCallback onTap;
  const _CreateButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 52, height: 52,
        decoration: BoxDecoration(
          gradient: AppGradients.primaryButton,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [BoxShadow(color: AppColors.indigo500.withValues(alpha: 0.4), blurRadius: 20, offset: const Offset(0, 6))],
        ),
        child: const Icon(Icons.add_rounded, color: Colors.white, size: 28),
      ),
    );
  }
}
```

**Step 3: Create placeholder screens**

Each placeholder is a simple centered text widget that confirms the route works.

```dart
// lib/features/home/screens/home_screen.dart
import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(body: Center(child: Text('Home')));
}
```

(Same pattern for submissions_screen.dart, profile_screen.dart, create_news_screen.dart)

**Step 4: Create app.dart**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'core/router/app_router.dart';

class NewsFlowApp extends StatelessWidget {
  const NewsFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'NewsFlow',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: appRouter,
    );
  }
}
```

**Step 5: Replace main.dart**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: NewsFlowApp()));
}
```

**Step 6: Verify compile + run**

Run: `cd /Users/admin/Desktop/newsflow && flutter analyze`
Then: Launch via `newsflow-web` to see bottom nav working.
Expected: App loads with 3 tabs + create button, each tab shows placeholder text.

**Step 7: Commit**

```bash
git add lib/
git commit -m "feat: add router, app shell with bottom navigation, placeholder screens"
```

---

### Task 5: Shared Widgets — Gradient Button, Glass Card, Status Chip, Category Chip

**Files:**
- Create: `lib/core/widgets/gradient_button.dart`
- Create: `lib/core/widgets/glass_card.dart`
- Create: `lib/core/widgets/status_chip.dart`
- Create: `lib/core/widgets/category_chip.dart`

**Step 1: Create gradient_button.dart**

A button with gradient background, shadow, press animation.

```dart
import 'package:flutter/material.dart';
import '../theme/app_gradients.dart';
import '../theme/app_spacing.dart';

class GradientButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  final LinearGradient? gradient;
  final IconData? icon;
  final bool pill;
  final bool loading;

  const GradientButton({
    super.key,
    required this.label,
    required this.onTap,
    this.gradient,
    this.icon,
    this.pill = false,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    final grad = gradient ?? AppGradients.primaryButton;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: loading ? null : onTap,
        borderRadius: BorderRadius.circular(pill ? AppSpacing.radiusFull : 14),
        child: Ink(
          decoration: BoxDecoration(
            gradient: grad,
            borderRadius: BorderRadius.circular(pill ? AppSpacing.radiusFull : 14),
            boxShadow: [BoxShadow(color: grad.colors.first.withValues(alpha: 0.3), blurRadius: 20, offset: const Offset(0, 4))],
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[Icon(icon, color: Colors.white, size: 18), const SizedBox(width: 8)],
                if (loading)
                  const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                else
                  Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

**Step 2: Create glass_card.dart**

```dart
import 'dart:ui';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets? padding;
  final double borderRadius;

  const GlassCard({super.key, required this.child, this.padding, this.borderRadius = 20});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
        child: Container(
          padding: padding ?? const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(color: Colors.white.withValues(alpha: 0.35)),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 20, offset: const Offset(0, 4))],
          ),
          child: child,
        ),
      ),
    );
  }
}
```

**Step 3: Create status_chip.dart**

```dart
import 'package:flutter/material.dart';
import '../../models/category.dart';
import '../theme/app_colors.dart';

class StatusChip extends StatelessWidget {
  final NewsStatus status;
  const StatusChip({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final (bg, textColor, dotColor) = switch (status) {
      NewsStatus.draft     => (AppColors.neutral100, AppColors.neutral600, AppColors.neutral400),
      NewsStatus.submitted => (const Color(0xFFFEF3C7), const Color(0xFF92400E), AppColors.gold500),
      NewsStatus.approved  => (const Color(0xFFDCFCE7), const Color(0xFF166534), AppColors.success),
      NewsStatus.rejected  => (const Color(0xFFFEE2E2), const Color(0xFF991B1B), AppColors.error),
      NewsStatus.published => (AppColors.indigo100, AppColors.indigo700, AppColors.indigo500),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 8, height: 8, decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(status.name[0].toUpperCase() + status.name.substring(1),
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: textColor)),
        ],
      ),
    );
  }
}
```

**Step 4: Create category_chip.dart**

```dart
import 'package:flutter/material.dart';
import '../../models/category.dart';

class CategoryChip extends StatelessWidget {
  final NewsCategory category;
  final bool selected;
  final VoidCallback? onTap;

  const CategoryChip({super.key, required this.category, this.selected = false, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          gradient: selected ? category.gradient : null,
          color: selected ? null : Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: selected ? null : Border.all(color: const Color(0xFFE7E5E4)),
          boxShadow: selected
            ? [BoxShadow(color: category.gradient.colors.first.withValues(alpha: 0.3), blurRadius: 8, offset: const Offset(0, 2))]
            : null,
        ),
        child: Text(
          category.label,
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
            color: selected ? Colors.white : const Color(0xFF78716C)),
        ),
      ),
    );
  }
}
```

**Step 5: Verify**

Run: `cd /Users/admin/Desktop/newsflow && dart analyze lib/core/widgets/`
Expected: No errors

**Step 6: Commit**

```bash
git add lib/core/widgets/
git commit -m "feat: add shared widgets — gradient button, glass card, status/category chips"
```

---

### Task 6: Shared Widgets — News Card, Voice Button, Gradient AppBar

**Files:**
- Create: `lib/core/widgets/news_card.dart`
- Create: `lib/core/widgets/voice_button.dart`
- Create: `lib/core/widgets/gradient_app_bar.dart`

**Step 1: Create news_card.dart**

A card showing headline (Odia), body snippet, category chip, status chip, priority badge, time metadata.

```dart
import 'package:flutter/material.dart';
import '../../models/news_article.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../theme/app_spacing.dart';
import 'status_chip.dart';
import 'category_chip.dart';

class NewsCard extends StatelessWidget {
  final NewsArticle article;
  final VoidCallback? onTap;

  const NewsCard({super.key, required this.article, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 12, offset: const Offset(0, 2))],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CategoryChip(category: article.category, selected: true),
                const Spacer(),
                StatusChip(status: article.status),
              ],
            ),
            const SizedBox(height: 12),
            Text(article.titleOdia ?? article.title, style: AppTypography.odiaTitleLarge),
            const SizedBox(height: 6),
            Text(
              article.bodyOdia ?? article.body,
              style: AppTypography.odiaBodyMedium,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                if (article.priority == NewsPriority.breaking || article.priority == NewsPriority.urgent)
                  _PriorityBadge(priority: article.priority),
                const Spacer(),
                Text(_timeAgo(article.createdAt), style: AppTypography.caption),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _timeAgo(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

class _PriorityBadge extends StatelessWidget {
  final NewsPriority priority;
  const _PriorityBadge({required this.priority});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [AppColors.gold400, AppColors.coral400]),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        priority == NewsPriority.breaking ? 'BREAKING' : 'URGENT',
        style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 0.5),
      ),
    );
  }
}
```

**Step 2: Create voice_button.dart**

Animated mic button with idle (indigo→teal) and recording (coral→pink) states with pulse ripple.

```dart
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_gradients.dart';

class VoiceButton extends StatelessWidget {
  final bool isRecording;
  final VoidCallback onTap;
  final double size;

  const VoiceButton({super.key, required this.isRecording, required this.onTap, this.size = 80});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: SizedBox(
        width: size * 2, height: size * 2,
        child: Stack(
          alignment: Alignment.center,
          children: [
            if (isRecording) ...[
              _Ripple(size: size, delay: 0),
              _Ripple(size: size, delay: 0.5),
            ],
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: size, height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: isRecording ? AppGradients.electricPulse : AppGradients.primaryButton,
                boxShadow: [
                  BoxShadow(
                    color: (isRecording ? AppColors.coral500 : AppColors.indigo500).withValues(alpha: 0.35),
                    blurRadius: 32, offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Icon(
                isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                color: Colors.white, size: size * 0.4,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Ripple extends StatefulWidget {
  final double size;
  final double delay;
  const _Ripple({required this.size, required this.delay});

  @override
  State<_Ripple> createState() => _RippleState();
}

class _RippleState extends State<_Ripple> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
    if (widget.delay > 0) {
      Future.delayed(Duration(milliseconds: (widget.delay * 1000).toInt()), () {
        if (mounted) _ctrl.repeat();
      });
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final scale = 1.0 + _ctrl.value;
        return Opacity(
          opacity: (1.0 - _ctrl.value) * 0.6,
          child: Container(
            width: widget.size * scale,
            height: widget.size * scale,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.coral300, width: 2.5),
            ),
          ),
        );
      },
    );
  }
}
```

**Step 3: Create gradient_app_bar.dart**

```dart
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_gradients.dart';
import '../theme/app_typography.dart';

class GradientAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final String? subtitle;
  final List<Widget>? actions;
  final Widget? leading;

  const GradientAppBar({super.key, required this.title, this.subtitle, this.actions, this.leading});

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppGradients.sambalpuriNight),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              if (leading != null) leading!,
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: AppTypography.titleLarge.copyWith(color: Colors.white)),
                    if (subtitle != null)
                      Text(subtitle!, style: AppTypography.bodySmall.copyWith(color: Colors.white70)),
                  ],
                ),
              ),
              if (actions != null) ...actions!,
            ],
          ),
        ),
      ),
    );
  }
}
```

**Step 4: Verify**

Run: `cd /Users/admin/Desktop/newsflow && dart analyze lib/core/widgets/`
Expected: No errors

**Step 5: Commit**

```bash
git add lib/core/widgets/
git commit -m "feat: add news card, voice button, gradient app bar widgets"
```

---

### Task 7: Home Screen

**Files:**
- Modify: `lib/features/home/screens/home_screen.dart`

**Step 1: Build the full Home Screen**

Features: Gradient header with greeting + org name, search bar, horizontal category filter chips, recent news cards list, "Quick Actions" section (New Story, My Drafts).

Use mock data for now. Design matches the mobile mockup from design-preview-v2.html.

```dart
// Full home screen implementation with:
// - SafeArea + CustomScrollView
// - SliverToBoxAdapter for gradient header (sambalpuriNight bg)
//   - "Good Morning, Reporter" greeting
//   - Odia subtitle "ସୁପ୍ରଭାତ"
//   - Org name badge
// - Search bar
// - Horizontal ListView of CategoryChip widgets
// - "Recent Submissions" section with NewsCard list
// - "Quick Actions" row with gradient icon cards
```

The full code should be written by the implementing agent, following the widget patterns established in Tasks 1-6.

**Step 2: Verify in browser**

Launch web dev server, navigate to /home.
Expected: Full home screen with gradient header, category chips, news cards.

**Step 3: Commit**

```bash
git add lib/features/home/
git commit -m "feat: build home screen with header, categories, and news cards"
```

---

### Task 8: Create News — 4-Step Wizard

**Files:**
- Modify: `lib/features/create_news/screens/create_news_screen.dart`
- Create: `lib/features/create_news/screens/step_voice.dart`
- Create: `lib/features/create_news/screens/step_details.dart`
- Create: `lib/features/create_news/screens/step_media.dart`
- Create: `lib/features/create_news/screens/step_review.dart`
- Create: `lib/features/create_news/providers/create_news_provider.dart`

**Step 1: Create the provider (state management)**

A Riverpod StateNotifier that holds the wizard state:
- currentStep (0-3)
- transcribedText
- selectedCategory
- title / body (Odia + English)
- priority
- location
- mediaFiles
- Methods: nextStep, prevStep, setTranscribedText, setCategory, etc.

**Step 2: Build wizard shell (create_news_screen.dart)**

- AppBar with "New Story" title + step indicator (1/4)
- AnimatedSwitcher between steps
- Bottom bar with Back/Next buttons (gradient)
- Step 4 shows "Submit" instead of "Next"

**Step 3: Build Step 1 — Voice (step_voice.dart)**

- Large VoiceButton centered
- Status text: "Tap to start recording" / "Listening..." / "Processing..."
- Transcribed text appears below in a glass card
- Odia language indicator badge

**Step 4: Build Step 2 — Details (step_details.dart)**

- Title TextField (pre-filled from transcription)
- Category selector (grid of CategoryChip)
- Priority selector (Normal / Urgent / Breaking radio buttons)
- Location TextField

**Step 5: Build Step 3 — Media (step_media.dart)**

- Grid of media thumbnails with add button
- "Add Photo", "Add Video", "Add Document" action buttons
- Uses image_picker / file_picker packages
- Media count indicator

**Step 6: Build Step 4 — Review (step_review.dart)**

- Read-only summary card showing:
  - Title (Odia + English)
  - Category chip
  - Priority badge
  - Body text preview
  - Media thumbnail strip
  - Location
- "Submit" gradient button at bottom

**Step 7: Verify in browser**

Navigate through all 4 steps.
Expected: Smooth step transitions, all UI renders correctly.

**Step 8: Commit**

```bash
git add lib/features/create_news/
git commit -m "feat: build 4-step news creation wizard with voice, details, media, review"
```

---

### Task 9: Submissions Screen

**Files:**
- Modify: `lib/features/submissions/screens/submissions_screen.dart`
- Create: `lib/features/submissions/screens/news_detail_screen.dart`
- Create: `lib/features/submissions/providers/submissions_provider.dart`

**Step 1: Build submissions list with tab filters**

- Tab bar: All / Draft / Submitted / Approved / Rejected / Published
- Each tab shows filtered list of NewsCard widgets
- Empty state with illustration text
- Pull-to-refresh gesture

**Step 2: Build news detail screen**

- Hero gradient header with category
- Full article body
- Status timeline (Draft → Submitted → Approved/Rejected → Published)
- Media gallery
- Rejection reason card (if rejected)
- Edit button (if draft)

**Step 3: Add route for detail screen**

Add to app_router.dart: `/submissions/:id` → NewsDetailScreen

**Step 4: Verify + Commit**

```bash
git add lib/features/submissions/ lib/core/router/app_router.dart
git commit -m "feat: build submissions list with filters and news detail screen"
```

---

### Task 10: Profile Screen

**Files:**
- Modify: `lib/features/profile/screens/profile_screen.dart`

**Step 1: Build profile screen**

- Avatar circle with gradient border
- Name, phone, email
- Organization badge
- Stats row: Total submissions, Approved, Published
- Settings list (Notifications, Language, Help, Logout)
- Each setting row with lucide icon

**Step 2: Verify + Commit**

```bash
git add lib/features/profile/
git commit -m "feat: build profile screen with stats and settings"
```

---

### Task 11: Polish & Final Verification

**Step 1: Run full analysis**

Run: `cd /Users/admin/Desktop/newsflow && flutter analyze`
Expected: No errors, minimal warnings

**Step 2: Run on web**

Launch `newsflow-web` and verify:
- [ ] Home screen loads with gradient header
- [ ] Category chips scroll horizontally
- [ ] News cards display correctly
- [ ] Bottom nav works (Home, My News, Profile)
- [ ] Create button opens wizard
- [ ] Wizard steps navigate correctly
- [ ] Back/Next buttons work
- [ ] Voice button animates
- [ ] Submissions show with status tabs
- [ ] Profile shows stats

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete NewsFlow reporter app v1 with all screens"
```
