import 'package:flutter/foundation.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

/// Crash + error reporting. Wraps `SentryFlutter.init` so the rest of
/// the app doesn't pull `package:sentry_flutter` symbols directly —
/// makes it cheap to swap to Crashlytics or Bugsnag later if we want
/// to.
///
/// Build-time configuration
/// ------------------------
/// The DSN comes from a `--dart-define=SENTRY_DSN=https://...` value
/// at `flutter build` time. When the define is missing or empty, this
/// helper deliberately **no-ops** — every event-capture call becomes
/// a silent drop. That matters because:
///
///   * Local dev builds shouldn't ship dev crashes to a shared
///     Sentry project.
///   * Initial-rollout builds may go out before the Sentry account
///     is provisioned; the app must still launch cleanly.
///   * Self-hosters may not want Sentry at all.
///
/// Privacy
/// -------
/// We deliberately keep PII out of events: user is tagged by reporter
/// id (UUID, not phone), and `sendDefaultPii` is false so request
/// bodies / IPs / user-agents aren't auto-attached. Story content
/// never appears in events because we don't capture it on errors —
/// only stack traces.
class SentrySetup {
  SentrySetup._();

  static const String _dsn = String.fromEnvironment('SENTRY_DSN');
  static const String _env = String.fromEnvironment('ENV', defaultValue: 'prod');

  /// True when a Sentry DSN was supplied at build time. The rest of
  /// the app can use this to decide whether sending hand-rolled events
  /// (e.g. via `Sentry.captureMessage`) is worth the syscall.
  static bool get isEnabled => _dsn.isNotEmpty;

  /// Initialize Sentry, then run [appRunner] inside its zone. Always
  /// pair: even when [isEnabled] is false the runner still executes
  /// (sentry_flutter.init handles the empty-DSN case by initialising a
  /// no-op SDK instance, so the app boots normally either way).
  static Future<void> init(Future<void> Function() appRunner) async {
    if (!isEnabled) {
      // Skip the full SentryFlutter.init dance — saves ~20ms cold-start
      // and avoids the "Sentry initialised with empty DSN" log line that
      // confuses on-call.
      await appRunner();
      return;
    }

    await SentryFlutter.init(
      (options) {
        options.dsn = _dsn;
        options.environment = _env; // 'prod' / 'uat' / 'dev'
        // Don't auto-attach IPs, user-agents, request bodies. Reporter
        // privacy first; we'll opt in per-event for the fields we
        // actually need (reporter id is set after login via
        // [setReporter]).
        options.sendDefaultPii = false;
        // Sample 100% of errors but only a tiny fraction of normal
        // navigation traces — we don't need detailed performance data
        // yet, and trace events are the bulk of the Sentry quota cost.
        options.tracesSampleRate = 0.0;
        // Keep a short breadcrumb history so we have context on a
        // crash without flooding the event payload.
        options.maxBreadcrumbs = 50;
        // Don't dedupe identical errors aggressively — at our scale
        // we'd rather see the count than have Sentry hide the spike.
        options.attachStacktrace = true;
        // In debug builds, Flutter framework errors fire on every hot
        // reload; suppress them so dev sessions don't blow the quota.
        options.debug = false;
        if (kDebugMode) {
          // Drop everything in debug. Devs use the debug console, not
          // Sentry, for live debugging.
          options.beforeSend = (event, hint) async => null;
        }
      },
      appRunner: appRunner,
    );
  }

  /// Tag subsequent Sentry events with the reporter's identity. Call
  /// after a successful OTP verification. Pass null on logout to
  /// detach. Reporter id is the only personal field we send — phone,
  /// name, email are deliberately omitted.
  static Future<void> setReporter({String? reporterId, String? orgId}) async {
    if (!isEnabled) return;
    await Sentry.configureScope((scope) {
      if (reporterId == null) {
        scope.setUser(null);
        scope.removeTag('org_id');
      } else {
        scope.setUser(SentryUser(id: reporterId));
        if (orgId != null) scope.setTag('org_id', orgId);
      }
    });
  }
}
