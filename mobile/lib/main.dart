import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'app.dart';
import 'core/services/local_drafts_store.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Local-first drafts: open Hive before any provider that touches the box.
  await Hive.initFlutter();
  await LocalDraftsStore.init();
  runApp(const ProviderScope(child: NewsFlowApp()));
}
