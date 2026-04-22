import 'dart:io';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter/services.dart' show rootBundle;
import 'package:path_provider/path_provider.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;

/// On-device speaker verification using the 3D-Speaker CAM++ model via
/// sherpa-onnx.  Extracts 192-dim speaker embeddings and compares them
/// with cosine similarity.
///
/// Usage:
///   final sv = SpeakerVerificationService();
///   await sv.init();
///   final emb = sv.extractEmbedding(pcm16kMonoBytes);
///   final (ok, score) = sv.verify(pcm16kMonoBytes, enrolledEmbedding);
///   sv.dispose();
class SpeakerVerificationService {
  static const String _modelAsset =
      'assets/models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx';

  static const double defaultThreshold = 0.55;

  /// Energy threshold for silence detection (RMS).  Chunks below this
  /// are considered silence and skipped by the VAD gate, saving the cost
  /// of a full embedding extraction (~30-80ms).
  static const double silenceRmsThreshold = 80.0;

  sherpa.SpeakerEmbeddingExtractor? _extractor;
  bool _initialized = false;

  /// Resolved filesystem path of the ONNX model (needed by isolate).
  String? _modelPath;

  /// Whether the model loaded successfully and is ready.
  bool get isInitialized => _initialized;

  /// Embedding dimensionality (available after [init]).
  int get embeddingDim => _extractor?.dim ?? 0;

  /// Load the ONNX model from Flutter assets.
  ///
  /// Flutter sandboxing prevents direct asset-path access, so we copy the
  /// model to a temporary directory first (same approach documented in
  /// sherpa-onnx issue #1761).
  Future<bool> init() async {
    if (_initialized) return true;
    try {
      // Step 1: Initialise sherpa-onnx native bindings (must be called once)
      sherpa.initBindings();

      // Step 2: Copy model from Flutter assets to temp dir
      _modelPath = await _copyAssetToTemp(_modelAsset);
      debugPrint('[SV] Model copied to $_modelPath');

      // Step 3: Verify the model file exists and is not truncated
      final modelFile = File(_modelPath!);
      final modelSize = await modelFile.length();
      debugPrint('[SV] Model file size: $modelSize bytes');
      if (modelSize < 1000000) {
        // Model is suspiciously small — likely truncated; re-copy
        debugPrint('[SV] Model file too small, re-copying from assets');
        await modelFile.delete();
        _modelPath = await _copyAssetToTemp(_modelAsset);
      }

      // Step 4: Create the ONNX embedding extractor
      final config = sherpa.SpeakerEmbeddingExtractorConfig(
        model: _modelPath!,
        numThreads: 2,
        debug: false,
        provider: 'cpu',
      );

      _extractor = sherpa.SpeakerEmbeddingExtractor(config: config);
      _initialized = true;
      debugPrint('[SV] Initialised OK — embedding dim = ${_extractor!.dim}');
      return true;
    } catch (e) {
      debugPrint('[SV] Init FAILED: $e');
      _initialized = false;
      return false;
    }
  }

  /// Extract a speaker embedding from raw PCM16 little-endian 16kHz mono
  /// audio bytes.  Returns an empty list on failure.
  Float32List extractEmbedding(Uint8List pcm16Bytes) {
    if (!_initialized || _extractor == null) {
      debugPrint('[SV] extractEmbedding: not initialized');
      return Float32List(0);
    }

    try {
      final samples = _pcm16ToFloat32(pcm16Bytes);
      if (samples.length < 1600) {
        debugPrint('[SV] extractEmbedding: audio too short (${samples.length} samples)');
        return Float32List(0);
      }

      debugPrint('[SV] extractEmbedding: ${samples.length} samples (${(samples.length / 16000.0).toStringAsFixed(1)}s)');

      final stream = _extractor!.createStream();
      stream.acceptWaveform(samples: samples, sampleRate: 16000);
      stream.inputFinished();

      if (!_extractor!.isReady(stream)) {
        debugPrint('[SV] extractEmbedding: stream not ready');
        stream.free();
        return Float32List(0);
      }

      final embedding = _extractor!.compute(stream);
      stream.free();
      debugPrint('[SV] extractEmbedding: OK — dim=${embedding.length}');
      return embedding;
    } catch (e) {
      debugPrint('[SV] extractEmbedding EXCEPTION: $e');
      return Float32List(0);
    }
  }

  /// Verify whether [pcm16Bytes] belongs to the same speaker whose
  /// enrollment embedding is [enrolled].
  ///
  /// Returns `(verified, similarityScore)`.
  (bool, double) verify(
    Uint8List pcm16Bytes,
    List<double> enrolled, {
    double threshold = defaultThreshold,
  }) {
    final embedding = extractEmbedding(pcm16Bytes);
    if (embedding.isEmpty || enrolled.isEmpty) return (false, 0.0);

    final score = cosineSimilarity(
      embedding.toList(),
      enrolled,
    );
    return (score >= threshold, score);
  }

  /// Cosine similarity between two embedding vectors.  Returns a value
  /// in [-1, 1]; higher means more similar.
  static double cosineSimilarity(List<double> a, List<double> b) {
    if (a.length != b.length || a.isEmpty) return 0.0;

    double dot = 0, normA = 0, normB = 0;
    for (int i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    final denom = math.sqrt(normA) * math.sqrt(normB);
    return denom == 0 ? 0.0 : dot / denom;
  }

  /// Average multiple embeddings into one (used during enrollment).
  static List<double> averageEmbeddings(List<List<double>> embeddings) {
    if (embeddings.isEmpty) return [];
    final dim = embeddings.first.length;
    final avg = List<double>.filled(dim, 0.0);
    for (final emb in embeddings) {
      for (int i = 0; i < dim; i++) {
        avg[i] += emb[i];
      }
    }
    for (int i = 0; i < dim; i++) {
      avg[i] /= embeddings.length;
    }
    // L2-normalise the averaged embedding.
    double norm = 0;
    for (int i = 0; i < dim; i++) {
      norm += avg[i] * avg[i];
    }
    norm = math.sqrt(norm);
    if (norm > 0) {
      for (int i = 0; i < dim; i++) {
        avg[i] /= norm;
      }
    }
    return avg;
  }

  /// Quick energy check on raw PCM16 audio.  Returns `true` if the chunk
  /// has enough energy to plausibly contain speech.  Use this as a cheap
  /// gate before the more expensive embedding extraction.
  static bool hasSpeechEnergy(Uint8List pcm16Bytes, {
    double threshold = silenceRmsThreshold,
  }) {
    final count = pcm16Bytes.length ~/ 2;
    if (count == 0) return false;
    final bd = ByteData.sublistView(pcm16Bytes);
    double sumSq = 0;
    for (int i = 0; i < count; i++) {
      final s = bd.getInt16(i * 2, Endian.little).toDouble();
      sumSq += s * s;
    }
    return math.sqrt(sumSq / count) >= threshold;
  }

  /// Run speaker verification in a background isolate so the main thread
  /// is not blocked by the ~30-80ms embedding extraction.
  ///
  /// Returns `(verified, similarityScore)`.  Falls back to main-thread
  /// verification if the isolate fails.
  Future<(bool, double)> verifyInIsolate(
    Uint8List pcm16Bytes,
    List<double> enrolled, {
    double threshold = defaultThreshold,
  }) async {
    if (!_initialized || _modelPath == null) return (false, 0.0);

    try {
      final result = await Isolate.run(() {
        return _isolateVerify(
          pcm16Bytes,
          enrolled,
          _modelPath!,
          threshold,
        );
      });
      return result;
    } catch (_) {
      // Fallback to synchronous verify on main thread
      return verify(pcm16Bytes, enrolled, threshold: threshold);
    }
  }

  /// Isolate entry point — creates its own extractor, runs verification,
  /// then tears down.  This avoids passing non-sendable sherpa objects
  /// across isolate boundaries.
  static (bool, double) _isolateVerify(
    Uint8List pcm16Bytes,
    List<double> enrolled,
    String modelPath,
    double threshold,
  ) {
    sherpa.SpeakerEmbeddingExtractor? extractor;
    try {
      // Isolates have separate memory — must init bindings in each isolate
      sherpa.initBindings();

      final config = sherpa.SpeakerEmbeddingExtractorConfig(
        model: modelPath,
        numThreads: 1, // single thread in isolate
        debug: false,
        provider: 'cpu',
      );
      extractor = sherpa.SpeakerEmbeddingExtractor(config: config);

      final samples = _pcm16ToFloat32(pcm16Bytes);
      if (samples.length < 1600) return (false, 0.0);

      final stream = extractor.createStream();
      stream.acceptWaveform(samples: samples, sampleRate: 16000);
      stream.inputFinished();

      if (!extractor.isReady(stream)) {
        stream.free();
        return (false, 0.0);
      }

      final embedding = extractor.compute(stream);
      stream.free();

      if (embedding.isEmpty) return (false, 0.0);
      final score = cosineSimilarity(embedding.toList(), enrolled);
      return (score >= threshold, score);
    } catch (_) {
      return (false, 0.0);
    } finally {
      extractor?.free();
    }
  }

  /// Release the ONNX runtime and free native memory.
  void dispose() {
    _extractor?.free();
    _extractor = null;
    _initialized = false;
    _modelPath = null;
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Expected model file size (used to detect truncated copies).
  static const int _expectedModelSize = 29596978;

  /// Copy a Flutter asset file to a temporary directory and return the
  /// filesystem path.  Re-uses the cached copy if it already exists and
  /// has the expected size.
  static Future<String> _copyAssetToTemp(String assetPath) async {
    final dir = await getTemporaryDirectory();
    final filename = assetPath.split('/').last;
    final file = File('${dir.path}/$filename');

    // Re-copy if missing or truncated (e.g. app crashed during first copy)
    bool needsCopy = !file.existsSync();
    if (!needsCopy) {
      final size = await file.length();
      if (size != _expectedModelSize) {
        debugPrint('[SV] Model file size mismatch ($size != $_expectedModelSize), re-copying');
        needsCopy = true;
        await file.delete();
      }
    }

    if (needsCopy) {
      debugPrint('[SV] Copying model from assets to ${file.path}');
      final data = await rootBundle.load(assetPath);
      await file.writeAsBytes(
        data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
        flush: true,
      );
    }
    return file.path;
  }

  /// Convert PCM16 little-endian bytes to Float32 samples in [-1.0, 1.0].
  static Float32List _pcm16ToFloat32(Uint8List bytes) {
    final count = bytes.length ~/ 2;
    final out = Float32List(count);
    final bd = ByteData.sublistView(bytes);
    for (int i = 0; i < count; i++) {
      out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
    }
    return out;
  }
}
