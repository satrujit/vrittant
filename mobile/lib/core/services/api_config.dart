import 'package:flutter/foundation.dart';

class ApiConfig {
  ApiConfig._();

  static const String _env = String.fromEnvironment(
    'ENV',
    defaultValue: 'prod',
  );

  static const String _devUrl = 'http://192.168.1.7:8000';
  static const String _uatUrl = 'https://vrittant-api-uat-pgvufpchiq-el.a.run.app';
  static const String _prodUrl = 'https://vrittant-api-829303072442.asia-south1.run.app';

  static String get baseUrl {
    switch (_env) {
      case 'prod':
        return _prodUrl;
      case 'uat':
        return _uatUrl;
      case 'dev':
        // Guard: a release build must never point at a LAN dev server. If
        // someone ships with --dart-define=ENV=dev by mistake, fail loud
        // instead of silently shipping a broken (and insecure) app.
        if (kReleaseMode) {
          throw StateError(
            'ENV=dev is not allowed in release builds. '
            'Use ENV=uat or ENV=prod.',
          );
        }
        return _devUrl;
      default:
        return _prodUrl;
    }
  }
}
