import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_config.dart';

// =============================================================================
// Riverpod provider
// =============================================================================

/// Provides a singleton [SarvamApiService] instance via Riverpod.
final sarvamApiProvider = Provider<SarvamApiService>((ref) {
  return SarvamApiService();
});

// =============================================================================
// Response models
// =============================================================================

/// Response returned by the speech-to-text endpoint.
class SttResponse {
  final String transcript;
  final String languageCode;

  const SttResponse({
    required this.transcript,
    required this.languageCode,
  });

  factory SttResponse.fromJson(Map<String, dynamic> json) {
    return SttResponse(
      transcript: json['transcript'] as String? ?? '',
      languageCode: json['language_code'] as String? ?? '',
    );
  }

  @override
  String toString() =>
      'SttResponse(transcript: $transcript, languageCode: $languageCode)';
}

/// Response returned by the text-to-speech endpoint.
class TtsResponse {
  /// Base-64 encoded audio chunks returned by the API.
  final List<String> audiosBase64;

  const TtsResponse({required this.audiosBase64});

  factory TtsResponse.fromJson(Map<String, dynamic> json) {
    return TtsResponse(
      audiosBase64: (json['audios'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }

  /// Decodes the first audio chunk into raw bytes.
  ///
  /// Returns `null` when [audiosBase64] is empty.
  Uint8List? get firstAudioBytes {
    if (audiosBase64.isEmpty) return null;
    return base64Decode(audiosBase64.first);
  }

  @override
  String toString() => 'TtsResponse(audios: ${audiosBase64.length} chunk(s))';
}

/// Response returned by the translation endpoint.
class TranslateResponse {
  final String translatedText;

  const TranslateResponse({required this.translatedText});

  factory TranslateResponse.fromJson(Map<String, dynamic> json) {
    return TranslateResponse(
      translatedText: json['translated_text'] as String? ?? '',
    );
  }

  @override
  String toString() => 'TranslateResponse(translatedText: $translatedText)';
}

/// A single message in an LLM chat conversation.
class ChatMessage {
  final String role;
  final String content;

  const ChatMessage({required this.role, required this.content});

  Map<String, dynamic> toJson() => {'role': role, 'content': content};

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      role: json['role'] as String? ?? '',
      content: json['content'] as String? ?? '',
    );
  }

  @override
  String toString() => 'ChatMessage(role: $role, content: $content)';
}

/// Response returned by the chat completions endpoint.
///
/// Follows the OpenAI-compatible format used by Sarvam's LLM API.
class ChatResponse {
  final String id;
  final String model;
  final List<ChatChoice> choices;
  final Map<String, dynamic>? usage;

  const ChatResponse({
    required this.id,
    required this.model,
    required this.choices,
    this.usage,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      id: json['id'] as String? ?? '',
      model: json['model'] as String? ?? '',
      choices: (json['choices'] as List<dynamic>?)
              ?.map((e) => ChatChoice.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      usage: json['usage'] as Map<String, dynamic>?,
    );
  }

  /// Convenience accessor for the content of the first choice.
  /// Strips any `<think>…</think>` reasoning blocks from the response.
  String get firstMessageContent {
    if (choices.isEmpty) return '';
    final raw = choices.first.message.content;
    return raw
        .replaceAll(RegExp(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>'), '')
        .replaceAll(RegExp(r'<think(?:ing)?>[\s\S]*$'), '')
        .trim();
  }

  @override
  String toString() =>
      'ChatResponse(id: $id, model: $model, choices: ${choices.length})';
}

/// A single choice inside a [ChatResponse].
class ChatChoice {
  final int index;
  final ChatMessage message;
  final String? finishReason;

  const ChatChoice({
    required this.index,
    required this.message,
    this.finishReason,
  });

  factory ChatChoice.fromJson(Map<String, dynamic> json) {
    return ChatChoice(
      index: json['index'] as int? ?? 0,
      message: ChatMessage.fromJson(
        json['message'] as Map<String, dynamic>? ?? {},
      ),
      finishReason: json['finish_reason'] as String?,
    );
  }

  @override
  String toString() =>
      'ChatChoice(index: $index, finishReason: $finishReason, message: $message)';
}

/// A single segment from the OCR response (text block or table).
class OcrSegment {
  final String type; // "text" or "table"
  final String text;
  final List<List<String>>? tableData;

  const OcrSegment({required this.type, this.text = '', this.tableData});

  factory OcrSegment.fromJson(Map<String, dynamic> json) {
    List<List<String>>? tableData;
    final raw = json['table_data'];
    if (raw is List) {
      tableData = raw
          .map((row) => (row as List).map((c) => c.toString()).toList())
          .toList();
    }
    return OcrSegment(
      type: json['type'] as String? ?? 'text',
      text: json['text'] as String? ?? '',
      tableData: tableData,
    );
  }
}

/// Full OCR result with structured segments.
class OcrResult {
  final String text;
  final List<OcrSegment> segments;
  final String language;

  const OcrResult({
    required this.text,
    required this.segments,
    required this.language,
  });

  factory OcrResult.fromJson(Map<String, dynamic> json) {
    return OcrResult(
      text: json['text'] as String? ?? '',
      segments: (json['segments'] as List<dynamic>?)
              ?.map((e) => OcrSegment.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      language: json['language'] as String? ?? '',
    );
  }
}

// =============================================================================
// Custom exception
// =============================================================================

/// Exception thrown when a Sarvam API call fails.
class SarvamApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic responseData;

  const SarvamApiException({
    required this.message,
    this.statusCode,
    this.responseData,
  });

  @override
  String toString() =>
      'SarvamApiException(statusCode: $statusCode, message: $message)';
}

// =============================================================================
// Service class — calls the backend proxy, NOT Sarvam directly
// =============================================================================

/// Client for the backend-proxied Sarvam AI API.
///
/// Instead of calling Sarvam directly (which would expose the API key in the
/// client), this service calls the NewsFlow backend which proxies requests
/// to Sarvam with the API key stored server-side.
class SarvamApiService {
  late final Dio _dio;
  String? _token;

  SarvamApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 60),
      ),
    );

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        handler.next(options);
      },
    ));
  }

  /// Sets the JWT auth token for backend requests.
  void setToken(String? token) => _token = token;

  // ---------------------------------------------------------------------------
  // LLM Chat Completions (via backend proxy)
  // ---------------------------------------------------------------------------

  /// Sends a list of [messages] to the backend's LLM chat endpoint.
  ///
  /// The backend chooses the model — the client is intentionally
  /// model-agnostic so swapping providers (Sarvam → Gemini → whatever
  /// comes next) is a server-only deploy, never a forced app update.
  ///
  /// [temperature] ranges from 0 to 2 (default 0.2).
  ///
  /// Returns an OpenAI-compatible [ChatResponse].
  Future<ChatResponse> chat({
    required List<ChatMessage> messages,
    double? temperature,
    int? maxTokens,
  }) async {
    try {
      final body = <String, dynamic>{
        'messages': messages.map((m) => m.toJson()).toList(),
        if (temperature != null) 'temperature': temperature,
        if (maxTokens != null) 'max_tokens': maxTokens,
      };

      final response = await _dio.post<Map<String, dynamic>>(
        '/api/llm/chat',
        data: body,
        options: Options(contentType: 'application/json'),
      );

      return ChatResponse.fromJson(response.data!);
    } on DioException catch (e) {
      throw _handleDioError(e, 'Chat');
    } catch (e) {
      throw SarvamApiException(message: 'Chat request failed: $e');
    }
  }

  // ---------------------------------------------------------------------------
  // OCR via Sarvam Document Intelligence (backend proxy)
  // ---------------------------------------------------------------------------

  /// Runs OCR on image bytes via the backend's `/api/ocr` endpoint.
  ///
  /// Returns the extracted text as markdown/plain text.
  /// [imageBytes] — raw image bytes (JPEG/PNG).
  /// [fileName] — original filename (used for extension detection).
  /// [language] — BCP-47 language code (default: Odia).
  Future<String> ocr({
    required Uint8List imageBytes,
    required String fileName,
    String language = 'od-IN',
  }) async {
    try {
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          imageBytes,
          filename: fileName,
        ),
        'language': language,
      });

      final response = await _dio.post<Map<String, dynamic>>(
        '/api/ocr',
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          receiveTimeout: const Duration(seconds: 120),
        ),
      );

      return (response.data?['text'] as String?) ?? '';
    } on DioException catch (e) {
      throw _handleDioError(e, 'OCR');
    } catch (e) {
      throw SarvamApiException(message: 'OCR request failed: $e');
    }
  }

  /// Runs OCR and returns structured segments (text blocks + tables).
  Future<OcrResult> ocrWithSegments({
    required Uint8List imageBytes,
    required String fileName,
    String language = 'od-IN',
  }) async {
    try {
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          imageBytes,
          filename: fileName,
        ),
        'language': language,
      });

      final response = await _dio.post<Map<String, dynamic>>(
        '/api/ocr',
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          receiveTimeout: const Duration(seconds: 120),
        ),
      );

      return OcrResult.fromJson(response.data ?? {});
    } on DioException catch (e) {
      throw _handleDioError(e, 'OCR');
    } catch (e) {
      throw SarvamApiException(message: 'OCR request failed: $e');
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Converts a [DioException] into a human-readable [SarvamApiException].
  SarvamApiException _handleDioError(DioException e, String operation) {
    final statusCode = e.response?.statusCode;
    final responseData = e.response?.data;

    String message;

    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        message = '$operation request timed out. Please try again.';
        break;
      case DioExceptionType.connectionError:
        message =
            'Unable to connect to the server. Please check your internet connection.';
        break;
      case DioExceptionType.badResponse:
        final serverMsg = _extractServerMessage(responseData);
        message = '$operation failed '
            '(${statusCode ?? 'unknown'}): ${serverMsg ?? 'Unknown server error.'}';
        break;
      case DioExceptionType.cancel:
        message = '$operation request was cancelled.';
        break;
      default:
        message = '$operation request failed: ${e.message}';
    }

    return SarvamApiException(
      message: message,
      statusCode: statusCode,
      responseData: responseData,
    );
  }

  /// Attempts to pull a human-readable error message from the API response body.
  String? _extractServerMessage(dynamic data) {
    if (data is Map<String, dynamic>) {
      if (data.containsKey('error')) {
        final error = data['error'];
        if (error is Map<String, dynamic> && error.containsKey('message')) {
          return error['message'] as String?;
        }
        if (error is String) return error;
      }
      if (data.containsKey('message')) {
        return data['message'] as String?;
      }
      if (data.containsKey('detail')) {
        return data['detail'] as String?;
      }
    }
    if (data is String && data.isNotEmpty) return data;
    return null;
  }
}
