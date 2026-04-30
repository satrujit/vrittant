import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'app.dart';
import 'core/services/local_drafts_store.dart';
import 'core/services/local_profile_cache.dart';
import 'core/services/local_stories_cache.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Local-first auth + drafts + stories: open Hive boxes before any
  // provider that touches them. Profile cache is needed by
  // AuthNotifier.tryAutoLogin which fires from the splash screen, so
  // it must be open before the first widget tree builds.
  await Hive.initFlutter();
  await LocalDraftsStore.init();
  await LocalStoriesCache.init();
  await LocalProfileCache.init();
  runApp(const ProviderScope(child: NewsFlowApp()));
}
