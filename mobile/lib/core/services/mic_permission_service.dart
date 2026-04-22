// Single source of truth for microphone permission state.
//
// Why this exists: `record.AudioRecorder.hasPermission()` collapses three very
// different states into a bool — "never asked", "asked once and denied", and
// "permanently denied" all return false. The user experience for each is
// different:
//   • never asked          → just request; the OS prompt does the work
//   • denied this session  → show a rationale, then re-request
//   • permanently denied   → in-app prompt is gone forever; we MUST send the
//                            user to system Settings or they're stuck
//
// `permission_handler` exposes the real status. We wrap it in a tiny enum so
// callers can branch on UX cleanly without dragging the whole package into
// every screen.

import 'package:permission_handler/permission_handler.dart';

enum MicPermissionResult {
  /// User granted (or already had) microphone access — proceed.
  granted,

  /// User declined this session. We can ask again; show rationale next time.
  denied,

  /// User checked "Don't ask again" (Android) or denied twice (iOS). The OS
  /// will never re-prompt — only `openAppSettings()` recovers from here.
  permanentlyDenied,

  /// Parental controls / MDM blocks the mic entirely. Same UX as
  /// permanentlyDenied (point to Settings) but messaging may want to differ.
  restricted,
}

class MicPermissionService {
  const MicPermissionService();

  /// Check current state without prompting. Use when you want to *display*
  /// permission status (e.g. a settings row) rather than start recording.
  Future<MicPermissionResult> check() async {
    final status = await Permission.microphone.status;
    return _map(status);
  }

  /// Request microphone permission, prompting the OS if needed.
  ///
  /// Behaviour by current state:
  ///   granted             → returns granted immediately, no prompt
  ///   denied (askable)    → triggers OS prompt
  ///   permanentlyDenied   → returns permanentlyDenied WITHOUT a prompt
  ///                         (the OS would no-op the prompt anyway)
  ///   restricted          → returns restricted
  ///
  /// Callers should branch on the result and surface the appropriate UI.
  Future<MicPermissionResult> request() async {
    // Always check first — request() on permanentlyDenied/restricted on iOS
    // can return `denied` instead of the real status, which would lie to the
    // caller about whether the OS prompt is still available.
    final current = await Permission.microphone.status;
    if (current.isPermanentlyDenied) return MicPermissionResult.permanentlyDenied;
    if (current.isRestricted) return MicPermissionResult.restricted;
    if (current.isGranted) return MicPermissionResult.granted;

    final result = await Permission.microphone.request();
    return _map(result);
  }

  /// Open the system Settings app, scoped to this app on iOS or to the app
  /// info screen on Android. Used as the recovery path when permission is
  /// permanently denied.
  Future<bool> openSystemSettings() => openAppSettings();

  MicPermissionResult _map(PermissionStatus s) {
    if (s.isGranted || s.isLimited) return MicPermissionResult.granted;
    if (s.isPermanentlyDenied) return MicPermissionResult.permanentlyDenied;
    if (s.isRestricted) return MicPermissionResult.restricted;
    return MicPermissionResult.denied;
  }
}

const micPermissionService = MicPermissionService();
