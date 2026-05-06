import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'app.dart';
import 'core/router/app_router.dart';
import 'core/router/deep_link_mapper.dart';
import 'core/services/local_drafts_store.dart';
import 'core/services/local_profile_cache.dart';
import 'core/services/local_stories_cache.dart';
import 'core/services/sentry_setup.dart';

void main() async {
  // Sentry must wrap runApp so uncaught Dart errors AND Flutter framework
  // errors are reported. SentrySetup.init no-ops when no DSN is provided
  // at build time, so the app still launches in dev / pre-Sentry-account
  // builds. The async initialization of Hive boxes happens INSIDE the
  // appRunner so any failure during box-open is captured too.
  await SentrySetup.init(() async {
    WidgetsFlutterBinding.ensureInitialized();
    // Local-first auth + drafts + stories: open Hive boxes before any
    // provider that touches them. Profile cache is needed by
    // AuthNotifier.tryAutoLogin which fires from the splash screen, so
    // it must be open before the first widget tree builds.
    await Hive.initFlutter();
    await LocalDraftsStore.init();
    await LocalStoriesCache.init();
    await LocalProfileCache.init();
    runApp(
      const ProviderScope(child: _AppLinksScope(child: NewsFlowApp())),
    );
  });
}

/// Wraps the app to listen for vrittant.in/r/* Universal Links / App Links
/// (cold-start via getInitialLink and runtime via uriLinkStream) and dispatch
/// them through the GoRouter. Pure mapping lives in deep_link_mapper.dart.
///
/// Note: if the user is unauthenticated when a link fires, the global
/// redirect in app_router.dart bounces them to /login and the deep-link
/// target is silently dropped. Acceptable for v1 — a follow-up can stash
/// the pending link in a provider and replay it post-login.
class _AppLinksScope extends ConsumerStatefulWidget {
  const _AppLinksScope({required this.child});
  final Widget child;
  @override
  ConsumerState<_AppLinksScope> createState() => _AppLinksScopeState();
}

class _AppLinksScopeState extends ConsumerState<_AppLinksScope> {
  late final AppLinks _appLinks;
  StreamSubscription<Uri>? _sub;

  @override
  void initState() {
    super.initState();
    _appLinks = AppLinks();
    _initDeepLinks();
  }

  Future<void> _initDeepLinks() async {
    // Cold-start link
    try {
      final initial = await _appLinks.getInitialLink();
      if (initial != null) {
        // Defer to after first frame so GoRouter is ready
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _route(initial);
        });
      }
    } catch (_) {
      // Best-effort — never crash app launch on a malformed cold-start link
    }
    // Runtime stream (foregrounded link taps)
    _sub = _appLinks.uriLinkStream.listen(
      (uri) => _route(uri),
      onError: (_) {},
    );
  }

  void _route(Uri uri) {
    final loc = mapUniversalLinkToLocation(uri);
    if (loc == null) return;
    final router = ref.read(appRouterProvider);
    router.go(loc);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
