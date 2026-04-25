import 'dart:developer' as developer;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_config.dart';

// -- Response models --

class OrgInfo {
  final String id;
  final String name;
  final String slug;
  final String? logoUrl;
  final String? themeColor;
  /// Master list of allowed category keys for this organization. When
  /// non-empty, the create-news UI must constrain category selection (and
  /// LLM auto-inference) to these keys only. Backend exposes via
  /// `categories: ["politics","sports",...]`. Falls back to the global
  /// hardcoded list when null/empty.
  final List<String> categories;

  const OrgInfo({
    required this.id,
    required this.name,
    required this.slug,
    this.logoUrl,
    this.themeColor,
    this.categories = const [],
  });

  factory OrgInfo.fromJson(Map<String, dynamic> json) {
    final raw = json['categories'];
    final cats = raw is List
        ? raw.whereType<String>().toList(growable: false)
        : const <String>[];
    return OrgInfo(
      id: json['id'] as String,
      name: json['name'] as String,
      slug: json['slug'] as String,
      logoUrl: json['logo_url'] as String?,
      themeColor: json['theme_color'] as String?,
      categories: cats,
    );
  }
}

class ReporterProfile {
  final String id;
  final String name;
  final String phone;
  final String areaName;
  final String organization;
  final String? organizationId;
  final OrgInfo? org;

  const ReporterProfile({
    required this.id,
    required this.name,
    required this.phone,
    required this.areaName,
    required this.organization,
    this.organizationId,
    this.org,
  });

  factory ReporterProfile.fromJson(Map<String, dynamic> json) {
    return ReporterProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String,
      areaName: json['area_name'] as String? ?? '',
      organization: json['organization'] as String? ?? '',
      organizationId: json['organization_id'] as String?,
      org: json['org'] != null
          ? OrgInfo.fromJson(json['org'] as Map<String, dynamic>)
          : null,
    );
  }
}

class StoryDto {
  final String id;
  final String reporterId;
  final String headline;
  final String? category;
  final String? location;
  final List<Map<String, dynamic>> paragraphs;
  final String status;
  final DateTime? submittedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  const StoryDto({
    required this.id,
    required this.reporterId,
    required this.headline,
    this.category,
    this.location,
    required this.paragraphs,
    required this.status,
    this.submittedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory StoryDto.fromJson(Map<String, dynamic> json) {
    return StoryDto(
      id: json['id'] as String,
      reporterId: json['reporter_id'] as String,
      headline: json['headline'] as String? ?? '',
      category: json['category'] as String?,
      location: json['location'] as String?,
      paragraphs: (json['paragraphs'] as List<dynamic>?)
              ?.map((p) => Map<String, dynamic>.from(p as Map))
              .toList() ??
          [],
      status: json['status'] as String? ?? 'draft',
      submittedAt: json['submitted_at'] != null
          ? DateTime.parse(json['submitted_at'] as String).toLocal()
          : null,
      createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
      updatedAt: DateTime.parse(json['updated_at'] as String).toLocal(),
    );
  }
}

// -- API Service --

class ApiService {
  late final Dio _dio;
  String? _token;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        // Server lag instrumentation: stamp request start time so we can
        // compute round-trip duration when the response (or error) returns.
        options.extra['_t0'] = DateTime.now();
        handler.next(options);
      },
      onResponse: (response, handler) {
        _logLag(response.requestOptions, response.statusCode);
        handler.next(response);
      },
      onError: (err, handler) {
        _logLag(err.requestOptions, err.response?.statusCode, error: err.type.name);
        handler.next(err);
      },
    ));
  }

  /// Logs the wall-clock duration of an HTTP request. Anything over 2s is
  /// flagged as `[SLOW]`; over 5s as `[VERY-SLOW]`. Only logs in debug mode
  /// so production users are not spammed.
  static void _logLag(RequestOptions opts, int? status, {String? error}) {
    if (!kDebugMode) return;
    final start = opts.extra['_t0'];
    if (start is! DateTime) return;
    final ms = DateTime.now().difference(start).inMilliseconds;
    String tag = '[api-lag]';
    if (ms > 5000) tag = '[api-lag][VERY-SLOW]';
    else if (ms > 2000) tag = '[api-lag][SLOW]';
    final method = opts.method;
    final path = opts.path;
    final st = error != null ? 'ERR=$error' : 'HTTP=$status';
    developer.log('$tag ${ms}ms $method $path $st', name: 'api');
  }

  String? get token => _token;
  String get baseUrl => ApiConfig.baseUrl;
  void setToken(String? token) => _token = token;

  /// Download raw bytes from an absolute URL.
  Future<Uint8List> downloadBytes(String url) async {
    final resp = await _dio.get<List<int>>(
      url,
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(resp.data!);
  }

  // -- Auth --

  /// Sends OTP and returns the reqId needed for verify/resend.
  Future<String> requestOtp(String phone) async {
    final res =
        await _dio.post('/auth/request-otp', data: {'phone': phone});
    return (res.data['req_id'] as String?) ?? '';
  }

  Future<({String token, ReporterProfile reporter})> verifyOtp(
      String phone, String otp, {String reqId = ''}) async {
    final res = await _dio.post('/auth/verify-otp',
        data: {'phone': phone, 'otp': otp, 'req_id': reqId});
    final token = res.data['access_token'] as String;
    _token = token;

    final meRes = await _dio.get('/auth/me');
    final reporter =
        ReporterProfile.fromJson(meRes.data as Map<String, dynamic>);
    return (token: token, reporter: reporter);
  }

  Future<void> resendOtp(String phone, {String reqId = ''}) async {
    await _dio.post('/auth/resend-otp',
        data: {'phone': phone, 'req_id': reqId});
  }

  Future<ReporterProfile> getMe() async {
    final res = await _dio.get('/auth/me');
    return ReporterProfile.fromJson(res.data as Map<String, dynamic>);
  }

  // -- Stories --

  Future<StoryDto> createStory({
    String headline = '',
    String? category,
    String? location,
    List<Map<String, dynamic>> paragraphs = const [],
  }) async {
    final res = await _dio.post('/stories', data: {
      'headline': headline,
      'category': category,
      'location': location,
      'paragraphs': paragraphs,
    });
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<StoryDto> updateStory(
    String storyId, {
    String? headline,
    String? category,
    String? location,
    List<Map<String, dynamic>>? paragraphs,
  }) async {
    final data = <String, dynamic>{};
    if (headline != null) data['headline'] = headline;
    if (category != null) data['category'] = category;
    if (location != null) data['location'] = location;
    if (paragraphs != null) data['paragraphs'] = paragraphs;

    final res = await _dio.put('/stories/$storyId', data: data);
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<StoryDto> getStory(String storyId) async {
    final res = await _dio.get('/stories/$storyId');
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  /// Lists stories with optional filters and pagination.
  Future<List<StoryDto>> listStories({
    String? status,
    String? category,
    String? search,
    String? dateFrom,
    String? dateTo,
    int offset = 0,
    int limit = 50,
  }) async {
    final queryParams = <String, dynamic>{
      'offset': offset,
      'limit': limit,
    };
    if (status != null) queryParams['status'] = status;
    if (category != null) queryParams['category'] = category;
    if (search != null && search.isNotEmpty) queryParams['search'] = search;
    if (dateFrom != null) queryParams['date_from'] = dateFrom;
    if (dateTo != null) queryParams['date_to'] = dateTo;

    final response = await _dio.get(
      '/stories',
      queryParameters: queryParams,
    );
    return (response.data as List)
        .map((json) => StoryDto.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<StoryDto> submitStory(String storyId) async {
    final res = await _dio.post('/stories/$storyId/submit');
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> deleteStory(String storyId) async {
    await _dio.delete('/stories/$storyId');
  }

  // -- Files --

  /// Upload a file to the server. Returns the file metadata including URL.
  Future<Map<String, dynamic>> uploadFile(
    List<int> bytes,
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
    });
    final res = await _dio.post('/files/upload', data: formData);
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// Upload an audio recording for the always-upload pipeline.
  ///
  /// Sent to `/api/stt/upload-audio`. The server stores the audio, attaches
  /// the path to the paragraph, and runs Sarvam STT in a background task —
  /// returning immediately. Set [isAttachment] true for long-press recordings
  /// (audio also surfaces as a playable media block on the paragraph);
  /// false for tap recordings (silent backup, used only if the live WS
  /// transcript came back empty).
  ///
  /// Returns the parsed JSON body (status, audio_url, is_attachment).
  Future<Map<String, dynamic>> uploadStoryAudio({
    required List<int> bytes,
    required String filename,
    required String storyId,
    required String paragraphId,
    required bool isAttachment,
    String languageCode = 'od-IN',
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
      'story_id': storyId,
      'paragraph_id': paragraphId,
      'is_attachment': isAttachment.toString(),
      'language_code': languageCode,
    });
    final res = await _dio.post('/api/stt/upload-audio', data: formData);
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// Re-run STT against a paragraph's stored audio. Returns the new transcript.
  Future<String> retranscribeParagraph({
    required String storyId,
    required String paragraphId,
    String languageCode = 'od-IN',
  }) async {
    final formData = FormData.fromMap({
      'story_id': storyId,
      'paragraph_id': paragraphId,
      'language_code': languageCode,
    });
    final res = await _dio.post('/api/stt/retranscribe', data: formData);
    return (res.data as Map)['transcript'] as String? ?? '';
  }

  /// List all media files across all stories for the current reporter.
  Future<List<Map<String, dynamic>>> listFiles() async {
    final res = await _dio.get('/files');
    return (res.data as List)
        .map((f) => Map<String, dynamic>.from(f as Map))
        .toList();
  }

  // -- Speaker Enrollment --

  /// Sync the on-device voice enrollment to the backend for backup.
  Future<void> syncEnrollment(List<double> embedding, int sampleCount) async {
    await _dio.put('/api/speaker/enrollment', data: {
      'embedding': embedding,
      'sample_count': sampleCount,
    });
  }

  /// Retrieve the stored enrollment from the backend (for device migration).
  /// Returns `null` if no enrollment exists.
  Future<({List<double> embedding, int sampleCount})?> getEnrollment() async {
    try {
      final res = await _dio.get('/api/speaker/enrollment');
      final data = res.data as Map<String, dynamic>;
      final emb = (data['embedding'] as List).cast<num>();
      return (
        embedding: emb.map((n) => n.toDouble()).toList(),
        sampleCount: data['sample_count'] as int,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  /// Delete enrollment from the backend.
  Future<void> deleteEnrollment() async {
    await _dio.delete('/api/speaker/enrollment');
  }
}

// -- Provider --

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());
