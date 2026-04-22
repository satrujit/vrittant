import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Tracks whether there is an active phone call (mic would be occupied).
/// Uses Android's TelephonyManager via a method channel.
class PhoneCallNotifier extends Notifier<bool> {
  static const _channel = MethodChannel('com.attentionstack.vrittant/telephony');
  Timer? _pollTimer;

  @override
  bool build() {
    if (Platform.isAndroid) {
      // Poll call state every 3 seconds
      _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _check());
      _check();
      ref.onDispose(() => _pollTimer?.cancel());
    }
    return false;
  }

  Future<void> _check() async {
    try {
      final inCall = await _channel.invokeMethod<bool>('isInCall') ?? false;
      if (state != inCall) state = inCall;
    } on MissingPluginException {
      // Channel not available — ignore
    } catch (_) {}
  }
}

final phoneCallProvider =
    NotifierProvider<PhoneCallNotifier, bool>(PhoneCallNotifier.new);
