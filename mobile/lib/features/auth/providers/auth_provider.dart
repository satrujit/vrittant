import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/services/api_service.dart';
import '../../../core/services/local_stories_cache.dart';

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

  bool get isLoggedIn => token != null && reporter != null;

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
    try {
      final reporter = await _api.getMe();
      state = AuthState(
        reporter: reporter,
        token: storedToken,
        initialized: true,
      );
      return true;
    } catch (e) {
      // Only clear token on 401 (expired/invalid). For network errors,
      // keep the session alive so the user isn't logged out on flaky connections.
      final is401 = e is DioException && e.response?.statusCode == 401;
      if (is401) {
        await _clearToken();
        _api.setToken(null);
        state = const AuthState(initialized: true);
        return false;
      }
      // Network error — keep token, retry /me in background
      state = state.copyWith(isLoading: false, initialized: true);
      _retryGetMe(storedToken);
      return false;
    }
  }

  /// Retry fetching profile after a network failure during auto-login.
  Future<void> _retryGetMe(String token) async {
    await Future.delayed(const Duration(seconds: 3));
    try {
      final reporter = await _api.getMe();
      state = AuthState(
        reporter: reporter,
        token: token,
        initialized: true,
      );
    } catch (_) {
      // Still failing — user will see login screen, can manually retry
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
      _reqId = '';
      state = AuthState(
          reporter: result.reporter, token: result.token, initialized: true);
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
    // Clear cached server stories so a different user signing in on this
    // device doesn't briefly see the previous user's list.
    await ref.read(localStoriesCacheProvider).clear();
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
