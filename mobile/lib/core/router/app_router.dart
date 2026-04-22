import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/providers/auth_provider.dart';
import '../../features/auth/screens/login_screen.dart';
import '../../features/auth/screens/splash_screen.dart';
import '../../features/force_update/screens/force_update_screen.dart';
import '../../features/profile/screens/voice_enrollment_screen.dart';
import '../../features/create_news/screens/notepad_screen.dart';
import '../services/version_check_service.dart';
import '../widgets/app_bottom_nav.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();

final appRouterProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authProvider);
  // Watch the version check so a forceUpdate result triggers a redirect
  // re-evaluation. The check runs once, lazily, on first read of this
  // provider — splash mounts and triggers it.
  final versionCheck = ref.watch(versionCheckProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/splash',
    redirect: (context, state) {
      final loc = state.matchedLocation;

      // Force-update gate: if the server says this client is below the
      // minimum supported version, lock the user on /force-update no matter
      // what else they try to navigate to. This MUST run before any auth
      // logic so unauthenticated users on a stale build aren't dumped into
      // a broken login flow.
      final mustUpdate = versionCheck.maybeWhen(
        data: (o) => o.result == VersionCheckResult.forceUpdate,
        orElse: () => false,
      );
      if (mustUpdate) {
        return loc == '/force-update' ? null : '/force-update';
      }
      // Once we're past the gate, never let users get back to /force-update
      // by deep-link or back-button — bounce them to splash to re-resolve.
      if (loc == '/force-update') return '/splash';

      // While auth is checking, stay on splash — don't navigate elsewhere
      if (!auth.initialized) {
        if (loc == '/splash') return null;
        return '/splash';
      }

      // Auth resolved — leave splash for the right destination
      if (loc == '/splash') {
        return auth.isLoggedIn ? '/home' : '/login';
      }

      // Normal auth guards
      final isLoggedIn = auth.isLoggedIn;
      final isOnLogin = loc == '/login';

      if (!isLoggedIn && !isOnLogin) return '/login';
      if (isLoggedIn && isOnLogin) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/', redirect: (_, __) => '/home'),
      GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
      GoRoute(
        path: '/force-update',
        builder: (_, __) => const ForceUpdateScreen(),
      ),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),

      // Main tabbed shell — swiping between tabs handled by PageView inside
      GoRoute(path: '/home', builder: (_, __) => const AppShell()),

      // Full-screen routes (outside the tab shell)
      GoRoute(
        path: '/create',
        builder: (_, state) {
          final storyId = state.uri.queryParameters['storyId'];
          return NotepadScreen(storyId: storyId);
        },
      ),
      GoRoute(
        path: '/voice-enrollment',
        builder: (_, __) => const VoiceEnrollmentScreen(),
      ),
    ],
  );
});
