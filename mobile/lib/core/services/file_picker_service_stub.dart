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
  Future<FilePickResult?> pickFile(MediaType type, {bool fromCamera = false}) =>
      throw UnsupportedError('No file picker on this platform');
  Future<OcrResult?> pickAndRecognize({void Function(double)? onProgress}) =>
      throw UnsupportedError('No file picker on this platform');
}
