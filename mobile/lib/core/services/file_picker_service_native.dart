import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart' as fp;
import 'package:image_picker/image_picker.dart';

enum MediaType { photo, video, audio, document }

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

class OcrResult {
  final String text;
  final String imageDataUrl;
  const OcrResult({required this.text, required this.imageDataUrl});
}

class OcrException implements Exception {
  final String message;
  const OcrException(this.message);
  @override
  String toString() => 'OcrException: $message';
}

class OcrService {
  final ImagePicker _imagePicker = ImagePicker();

  Future<FilePickResult?> pickFile(MediaType type, {bool fromCamera = false}) async {
    switch (type) {
      case MediaType.photo:
        return _pickImage(fromCamera: fromCamera);
      case MediaType.video:
        return _pickVideo();
      case MediaType.audio:
        return _pickGeneric(
          ['mp3', 'wav', 'aac', 'm4a', 'ogg'],
          resolvedType: MediaType.audio,
        );
      case MediaType.document:
        // Documents: PDF, DOCX, PPTX + audio files
        return _pickGeneric(
          ['pdf', 'docx', 'pptx', 'mp3', 'wav', 'aac', 'm4a', 'ogg'],
        );
    }
  }

  Future<FilePickResult?> _pickImage({bool fromCamera = false}) async {
    final source = fromCamera ? ImageSource.camera : ImageSource.gallery;
    final xfile = await _imagePicker.pickImage(source: source, imageQuality: 85);
    if (xfile == null) return null;
    return _xfileToResult(xfile, resolvedType: MediaType.photo);
  }

  Future<FilePickResult?> _pickVideo() async {
    final xfile = await _imagePicker.pickVideo(source: ImageSource.gallery);
    if (xfile == null) return null;
    return _xfileToResult(xfile, resolvedType: MediaType.video);
  }

  Future<FilePickResult?> _pickGeneric(
    List<String> extensions, {
    MediaType? resolvedType,
  }) async {
    final result = await fp.FilePicker.platform.pickFiles(
      type: fp.FileType.custom,
      allowedExtensions: extensions,
    );
    if (result == null || result.files.isEmpty) return null;
    final file = result.files.first;
    if (file.path == null) return null;
    final bytes = await File(file.path!).readAsBytes();
    final mime = _guessMime(file.name);
    final dataUrl = 'data:$mime;base64,${base64Encode(bytes)}';

    // Auto-detect type from extension if not explicitly set
    final actualType = resolvedType ?? _detectMediaType(file.name);
    return FilePickResult(
      dataUrl: dataUrl,
      fileName: file.name,
      resolvedType: actualType,
    );
  }

  Future<FilePickResult?> _xfileToResult(
    XFile xfile, {
    MediaType resolvedType = MediaType.document,
  }) async {
    final bytes = await xfile.readAsBytes();
    final mime = _guessMime(xfile.name);
    final dataUrl = 'data:$mime;base64,${base64Encode(bytes)}';
    return FilePickResult(
      dataUrl: dataUrl,
      fileName: xfile.name,
      resolvedType: resolvedType,
    );
  }

  /// Detect media type from file extension.
  MediaType _detectMediaType(String name) {
    final ext = name.split('.').last.toLowerCase();
    const audioExts = {'mp3', 'wav', 'aac', 'm4a', 'ogg'};
    if (audioExts.contains(ext)) return MediaType.audio;
    return MediaType.document;
  }

  String _guessMime(String name) {
    final ext = name.split('.').last.toLowerCase();
    const mimes = {
      'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
      'gif': 'image/gif', 'webp': 'image/webp', 'heic': 'image/heic',
      'mp4': 'video/mp4', 'mov': 'video/quicktime',
      'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'aac': 'audio/aac',
      'm4a': 'audio/mp4', 'ogg': 'audio/ogg',
      'pdf': 'application/pdf',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'txt': 'text/plain',
    };
    return mimes[ext] ?? 'application/octet-stream';
  }

  Future<OcrResult?> pickAndRecognize({void Function(double)? onProgress}) async {
    final result = await pickFile(MediaType.photo);
    if (result == null) return null;
    return OcrResult(text: '', imageDataUrl: result.dataUrl);
  }
}
