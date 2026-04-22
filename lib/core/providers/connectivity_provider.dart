import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Tracks whether the device has an active internet connection.
class ConnectivityNotifier extends Notifier<bool> {
  StreamSubscription<List<ConnectivityResult>>? _sub;

  @override
  bool build() {
    _sub = Connectivity().onConnectivityChanged.listen((results) {
      final connected = results.any((r) => r != ConnectivityResult.none);
      state = connected;
    });

    // Check immediately
    Connectivity().checkConnectivity().then((results) {
      state = results.any((r) => r != ConnectivityResult.none);
    });

    ref.onDispose(() => _sub?.cancel());
    return true; // assume connected initially
  }
}

final connectivityProvider =
    NotifierProvider<ConnectivityNotifier, bool>(ConnectivityNotifier.new);
