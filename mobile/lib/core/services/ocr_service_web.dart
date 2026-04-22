import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

enum MediaType { photo, video, audio, document }

/// Service for picking files from the browser file input.
/// Supports picking images, videos, audio, and documents.
class OcrService {
  /// Picks a file of the specified [type] using the browser file input.
  /// Returns a [FilePickResult] with the data URL and file name, or null if cancelled.
  Future<FilePickResult?> pickFile(MediaType type, {bool fromCamera = false}) async {
    final accept = _acceptForType(type);
    final completer = Completer<FilePickResult?>();

    // Create a file input element
    final input = web.document.createElement('input') as web.HTMLInputElement;
    input.type = 'file';
    input.accept = accept;

    // On mobile, enable camera for photos
    if (type == MediaType.photo && fromCamera) {
      input.setAttribute('capture', 'environment');
    }

    input.addEventListener(
      'change',
      ((web.Event event) {
        final files = input.files;
        if (files == null || files.length == 0) {
          completer.complete(null);
          return;
        }

        final file = files.item(0);
        if (file == null) {
          completer.complete(null);
          return;
        }

        final fileName = file.name;

        // Read file as data URL
        final reader = web.FileReader();
        reader.addEventListener(
          'load',
          ((web.Event _) {
            final result = reader.result;
            if (result != null) {
              final dataUrl = (result as dynamic).toString();
              final resolvedType = _detectMediaType(fileName, type);
              completer.complete(FilePickResult(
                dataUrl: dataUrl,
                fileName: fileName,
                resolvedType: resolvedType,
              ));
            } else {
              completer.complete(null);
            }
          }).toJS,
        );
        reader.addEventListener(
          'error',
          ((web.Event _) {
            completer.complete(null);
          }).toJS,
        );
        reader.readAsDataURL(file);
      }).toJS,
    );

    input.addEventListener(
      'cancel',
      ((web.Event _) {
        completer.complete(null);
      }).toJS,
    );

    input.click();

    return completer.future;
  }

  /// Backward-compatible: picks an image and returns OCR-like result.
  Future<OcrResult?> pickAndRecognize({
    void Function(double progress)? onProgress,
  }) async {
    final result = await pickFile(MediaType.photo);
    if (result == null) return null;
    return OcrResult(text: '', imageDataUrl: result.dataUrl);
  }

  MediaType _detectMediaType(String name, MediaType fallback) {
    final ext = name.split('.').last.toLowerCase();
    const audioExts = {'mp3', 'wav', 'aac', 'm4a', 'ogg'};
    if (audioExts.contains(ext)) return MediaType.audio;
    return fallback;
  }

  String _acceptForType(MediaType type) {
    switch (type) {
      case MediaType.photo:
        return 'image/*';
      case MediaType.video:
        return 'video/*';
      case MediaType.audio:
        return 'audio/*';
      case MediaType.document:
        return '.pdf,.docx,.pptx,.mp3,.wav,.aac,.m4a,.ogg';
    }
  }
}

/// Result from file picking.
class FilePickResult {
  final String dataUrl;
  final String fileName;
  final MediaType resolvedType;

  const FilePickResult({
    required this.dataUrl,
    required this.fileName,
    this.resolvedType = MediaType.document,
  });
}

/// Result from OCR processing (backward compat).
class OcrResult {
  final String text;
  final String imageDataUrl;

  const OcrResult({required this.text, required this.imageDataUrl});
}

/// Exception thrown by the OCR service.
class OcrException implements Exception {
  final String message;
  const OcrException(this.message);

  @override
  String toString() => 'OcrException: $message';
}
