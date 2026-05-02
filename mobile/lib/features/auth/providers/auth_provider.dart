import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/services/api_service.dart';
import '../../../core/services/local_profile_cache.dart';
import '../../../core/services/local_stories_cache.dart';
import '../../../core/services/sentry_setup.dart';

class AuthState {
  final ReporterProfile? reporter;
  final String? token;
  final bool isLoading;
  final String? error;
  final bool otpSent;
  final bool initialized;

  const AuthState({
    this.reporter,
    this.token,
    this.isLoading = false,
    this.error,
    this.otpSent = false,
    this.initialized = false,
  });

  /// Logged in = we have a token. Reporter profile is just data — it
  /// can be null on first launch when /me hasn't returned yet, or when
  /// the device is offline at boot. Conflating "no profile loaded" with
  /// "not authenticated" used to dump offline users at the login screen
  /// even though their session was valid; the router now keeps them in
  /// the app and lets the background /me retry hydrate the profile.
  bool get isLoggedIn => token != null;

  /// Profile-ready flag for screens that genuinely need reporter data
  /// (e.g. profile screen, name in the header). Use this — not
  /// isLoggedIn — when the UI requires the loaded profile.
  bool get hasProfile => reporter != null;

  AuthState copyWith({
    ReporterProfile? reporter,
    String? token,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool? otpSent,
    bool clearAll = false,
    bool? initialized,
  }) {
    if (clearAll) return const AuthState(initialized: true);
    return AuthState(
      reporter: reporter ?? this.reporter,
      token: token ?? this.token,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      otpSent: otpSent ?? this.otpSent,
      initialized: initialized ?? this.initialized,
    );
  }
}

class AuthNotifier extends Notifier<AuthState> {
  static const _tokenKey = 'jwt_token';

  /// Secure storage backend.
  /// - iOS: Keychain (survives app reinstall unless device-restored)
  /// - Android: EncryptedSharedPreferences (AES via Keystore)
  ///
  /// Older builds wrote the JWT to plain SharedPreferences. We read-and-migrate
  /// on first launch after upgrade so existing logged-in users don't get kicked
  /// out, then clear the legacy plaintext copy.
  static const _secure = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  /// Stores reqId from send_otp for use in verify/resend.
  String _reqId = '';

  @override
  AuthState build() {
    Future.microtask(() => tryAutoLogin());
    return const AuthState();
  }

  ApiService get _api => ref.read(apiServiceProvider);

  /// Read token from secure storage; if absent, fall back to legacy
  /// SharedPreferences and migrate transparently.
  Future<String?> _readToken() async {
    final secureToken = await _secure.read(key: _tokenKey);
    if (secureToken != null) return secureToken;

    // Legacy fallback — migrate on read.
    final prefs = await SharedPreferences.getInstance();
    final legacyToken = prefs.getString(_tokenKey);
    if (legacyToken == null) return null;

    await _secure.write(key: _tokenKey, value: legacyToken);
    await prefs.remove(_tokenKey);
    return legacyToken;
  }

  Future<void> _writeToken(String token) async {
    await _secure.write(key: _tokenKey, value: token);
    // Make sure no plaintext copy lingers from a pre-migration build.
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Future<void> _clearToken() async {
    await _secure.delete(key: _tokenKey);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Future<bool> tryAutoLogin() async {
    state = state.copyWith(isLoading: true, clearError: true);
    final storedToken = await _readToken();
    if (storedToken == null) {
      state = state.copyWith(isLoading: false, initialized: true);
      return false;
    }

    _api.setToken(storedToken);

    // Hydrate the reporter from disk first. This means the home screen
    // sees a fully-populated AuthState the moment splash exits — name
    // in the header, org categories for the create-news flow, area
    // name for story attribution. The user can open the notepad and
    // start typing before /me has even returned. If the device is
    // offline, this is the entirety of what we'll show until network
    // comes back; if online, the network response below replaces it.
    final cached = ref.read(localProfileCacheProvider).read();

    try {
      final me = await _api.getMe();
      // Persist the fresh raw JSON so the next cold start hydrates
      // the latest profile, not a stale snapshot.
      await ref.read(localProfileCacheProvider).writeRaw(me.raw);
      state = AuthState(
        reporter: me.reporter,
        token: storedToken,
        initialized: true,
      );
      // Tag Sentry events with this reporter's id so we can correlate
      // crashes / errors back to a specific user when triaging.
      await SentrySetup.setReporter(
        reporterId: me.reporter.id,
        orgId: me.reporter.organizationId,
      );
      return true;
    } catch (e) {
      // Only clear token + cache on 401 (expired/invalid). For network
      // errors, keep the session alive AND the cached profile so the
      // user keeps working offline.
      final is401 = e is DioException && e.response?.statusCode == 401;
      if (is401) {
        await _clearToken();
        await ref.read(localProfileCacheProvider).clear();
        _api.setToken(null);
        state = const AuthState(initialized: true);
        return false;
      }
      // Network error — keep token + cached reporter, retry /me in
      // background so the moment connectivity returns we refresh.
      state = AuthState(
        reporter: cached, // null on a truly cold install; otherwise hydrates
        token: storedToken,
        initialized: true,
      );
      _retryGetMe(storedToken);
      return cached != null;
    }
  }

  /// Retry fetching profile after a network failure during auto-login.
  Future<void> _retryGetMe(String token) async {
    await Future.delayed(const Duration(seconds: 3));
    try {
      final me = await _api.getMe();
      await ref.read(localProfileCacheProvider).writeRaw(me.raw);
      state = AuthState(
        reporter: me.reporter,
        token: token,
        initialized: true,
      );
    } catch (_) {
      // Still failing — leave cached reporter (if any) in place. The
      // user is already inside the app; next API call that triggers a
      // refresh (or the next cold start) will retry.
    }
  }

  Future<void> requestOtp(String phone) async {
    state = state.copyWith(isLoading: true, clearError: true, otpSent: false);
    try {
      _reqId = await _api.requestOtp(phone);
      state = state.copyWith(isLoading: false, otpSent: true);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
    }
  }

  Future<bool> verifyOtp(String phone, String otp) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _api.verifyOtp(phone, otp, reqId: _reqId);
      await _writeToken(result.token);
      // Cache the fresh profile so the next cold start (even offline)
      // boots straight into the home screen without a network round-trip.
      await ref.read(localProfileCacheProvider).writeRaw(result.reporterRaw);
      _reqId = '';
      state = AuthState(
          reporter: result.reporter, token: result.token, initialized: true);
      await SentrySetup.setReporter(
        reporterId: result.reporter.id,
        orgId: result.reporter.organizationId,
      );
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
      return false;
    }
  }

  Future<void> resendOtp(String phone) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await _api.resendOtp(phone, reqId: _reqId);
      state = state.copyWith(isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
    }
  }

  void resetOtpState() {
    _reqId = '';
    state = state.copyWith(otpSent: false, clearError: true);
  }

  Future<void> logout() async {
    await _clearToken();
    _api.setToken(null);
    // Clear cached server stories AND the cached reporter profile so a
    // different user signing in on this device doesn't see the previous
    // user's list flashing or their name in the header for a moment.
    await ref.read(localStoriesCacheProvider).clear();
    await ref.read(localProfileCacheProvider).clear();
    // Detach Sentry user context — the next reporter on this device
    // shouldn't see crashes attributed to the previous one.
    await SentrySetup.setReporter(reporterId: null);
    _reqId = '';
    state = const AuthState();
  }

  String _extractError(dynamic e) {
    if (e is DioException) {
      // Server returned an error response
      if (e.response?.data != null) {
        final data = e.response!.data;
        if (data is Map && data['detail'] != null) {
          return data['detail'].toString();
        }
      }
      // Network / timeout / connection errors
      switch (e.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
          return 'Connection timed out. Please check your internet and try again.';
        case DioExceptionType.connectionError:
          return 'Unable to connect to server. Please check your internet connection.';
        default:
          break;
      }
    }
    return 'Something went wrong. Please try again.';
  }
}

final authProvider =
    NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);
