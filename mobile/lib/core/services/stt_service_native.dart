import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'api_config.dart';
import 'dtln_denoiser.dart';
import 'speaker_verification_service.dart';

class SttSegment {
  final String text;
  final bool isFinal;
  const SttSegment({required this.text, this.isFinal = false});
}

class StreamingSttService {
  StreamingSttService({
    this.languageCode = 'od-IN',
    this.model = 'saaras:v3',
  });

  final String languageCode;
  final String model;
  String? authToken;

  /// Called when ambient noise level changes between noisy/quiet.
  void Function(bool isNoisy)? onNoisyChanged;

  /// Called when speaker verification status changes (only when speaker
  /// filtering is active).
  void Function(bool isVerified, double similarity)? onSpeakerStatusChanged;

  final AudioRecorder _recorder = AudioRecorder();
  final DtlnDenoiser _denoiser = DtlnDenoiser();
  WebSocketChannel? _channel;
  StreamController<SttSegment>? _transcriptController;
  StreamSubscription? _audioSubscription;
  StreamSubscription? _wsSubscription;

  String _committedText = '';
  String _currentWindowText = '';

  // Audio accumulation for WAV export
  bool _saveAudio = false;
  final List<int> _audioBuffer = [];

  // Noise detection
  static const int _noiseRmsThreshold = 500;
  static const int _noiseWindowSize = 25; // ~3s worth of chunks
  final List<double> _rmsWindow = [];
  bool _isNoisy = false;

  // Speaker verification
  bool _verifySpeaker = false;
  List<double>? _enrolledEmbedding;
  SpeakerVerificationService? _speakerSv;
  final List<int> _svBuffer = []; // accumulate ~0.5s of PCM for verification
  // 0.5 second of 16kHz 16-bit mono = 16000 bytes (halved for faster response)
  static const int _svBufferTarget = 16000;
  bool _lastSpeakerVerified = true;
  bool _svBusy = false; // prevents overlapping isolate calls

  /// Whether audio is being saved for WAV export.
  bool get isSavingAudio => _saveAudio;

  Future<Stream<SttSegment>> start({
    bool saveAudio = false,
    bool verifySpeaker = false,
    List<double>? enrolledEmbedding,
  }) async {
    if (_transcriptController != null) {
      throw StreamingSttException('Already recording');
    }

    _saveAudio = saveAudio;
    _audioBuffer.clear();
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
    _transcriptController = StreamController<SttSegment>.broadcast();

    // Speaker verification setup
    _verifySpeaker = verifySpeaker && enrolledEmbedding != null;
    _enrolledEmbedding = enrolledEmbedding;
    _svBuffer.clear();
    _lastSpeakerVerified = true;

    if (_verifySpeaker) {
      _speakerSv = SpeakerVerificationService();
      final initOk = await _speakerSv!.init();
      if (!initOk) {
        debugPrint('[STT] Speaker verification init failed — disabling filter');
        _verifySpeaker = false;
        _speakerSv?.dispose();
        _speakerSv = null;
      }
    }

    // Connect WebSocket to backend proxy. The handshake (DNS + TCP +
    // TLS + WS upgrade) can take 1–3s on a cold connection. We start it
    // FIRST and run mic + denoiser setup in parallel so the slow paths
    // overlap; then await readiness before pumping audio.
    final wsBase = ApiConfig.baseUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse(
      '$wsBase/ws/stt?token=${authToken ?? ""}&language_code=$languageCode&model=$model',
    );
    _channel = WebSocketChannel.connect(uri);

    // Listen for transcript messages from backend
    _wsSubscription = _channel!.stream.listen(
      (message) {
        if (message is String) {
          _handleTranscriptMessage(message);
        }
      },
      onError: (error) {
        _transcriptController?.addError(
          StreamingSttException('WebSocket error: $error'),
        );
      },
      onDone: () {
        _transcriptController?.close();
      },
    );

    // Start recording PCM 16kHz mono
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      throw StreamingSttException('Microphone permission denied');
    }

    final audioStream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      ),
    );

    // Initialize on-device speech enhancement (fail-safe)
    await _denoiser.init();

    // CRITICAL: wait for the WebSocket handshake to complete before
    // pumping audio. Without this, audio chunks sent during the cold
    // handshake either get dropped at the proxy or arrive before the
    // upstream Sarvam session is set up — Sarvam silently discards them
    // and the user sees zero transcripts during the FIRST recording.
    // Subsequent recordings worked because TLS session resumption made
    // the handshake fast enough that audio start happened to land after
    // it. The 10s timeout exits the recording with a clear error rather
    // than hanging forever on a broken connection.
    final wsStartedAt = DateTime.now();
    try {
      await _channel!.ready.timeout(const Duration(seconds: 10));
      final ms = DateTime.now().difference(wsStartedAt).inMilliseconds;
      debugPrint('[STT] WebSocket ready in ${ms}ms');
    } on TimeoutException {
      throw StreamingSttException(
        'Could not connect to transcription server. Check your internet.',
      );
    }

    // Forward audio chunks to WebSocket as JSON (Sarvam expected format).
    // Audio captured during the await above is buffered in [audioStream]
    // (single-subscription stream) and flushes here in a burst — no
    // speech is lost as long as the user started speaking after recorder
    // start and before the burst.
    _audioSubscription = audioStream.listen(
      (data) {
        // Check ambient noise level on raw audio
        _updateNoiseDetection(data);

        // Apply DTLN denoising (no-op if init failed)
        final enhanced = _denoiser.process(data);

        // Accumulate enhanced PCM if saving audio
        if (_saveAudio) {
          _audioBuffer.addAll(enhanced);
        }

        // Speaker verification gate
        if (_verifySpeaker) {
          _handleSpeakerVerifiedAudio(enhanced);
        } else {
          _sendToBackend(enhanced);
        }
      },
      onError: (error) {
        _transcriptController?.addError(
          StreamingSttException('Audio error: $error'),
        );
      },
    );

    return _transcriptController!.stream;
  }

  /// Run speaker verification in the background as an **advisory** indicator.
  ///
  /// Audio is ALWAYS sent to the backend immediately so streaming
  /// transcription is never interrupted.  Speaker verification runs
  /// asynchronously on accumulated chunks and reports results via
  /// [onSpeakerStatusChanged] — it does NOT gate audio forwarding.
  ///
  /// Optimisations:
  ///   1. **VAD gate** — silence chunks skip the expensive SV entirely.
  ///   2. **0.5s buffer** — finer-grained SV feedback.
  ///   3. **Isolate** — embedding extraction runs in a background isolate.
  ///   4. **Timeout** — prevents a stuck isolate from blocking future checks.
  void _handleSpeakerVerifiedAudio(Uint8List enhanced) {
    // ---- Always send audio to backend immediately ----
    _sendToBackend(enhanced);

    // ---- Accumulate a copy for background speaker verification ----
    _svBuffer.addAll(enhanced);

    if (_svBuffer.length >= _svBufferTarget && !_svBusy) {
      final chunk = Uint8List.fromList(_svBuffer);
      _svBuffer.clear();

      // --- VAD gate: skip verification on silence ---
      if (!SpeakerVerificationService.hasSpeechEnergy(chunk)) {
        return;
      }

      // --- Isolate-based verification (advisory only) ---
      _svBusy = true;
      _speakerSv!
          .verifyInIsolate(chunk, _enrolledEmbedding!)
          .timeout(const Duration(seconds: 3), onTimeout: () {
        debugPrint('[STT] SV isolate timeout — resetting busy flag');
        return (true, 0.0); // assume verified on timeout
      }).then((result) {
        _svBusy = false;
        final (verified, score) = result;

        // Notify UI if status changed
        if (verified != _lastSpeakerVerified) {
          _lastSpeakerVerified = verified;
          onSpeakerStatusChanged?.call(verified, score);
        }
      }).catchError((_) {
        _svBusy = false;
      });
    }
  }

  void _sendToBackend(Uint8List enhanced) {
    if (_channel != null) {
      final base64Audio = base64Encode(enhanced);
      final message = jsonEncode({
        'audio': {
          'data': base64Audio,
          'sample_rate': 16000,
          'encoding': 'audio/wav',
        },
      });
      _channel!.sink.add(message);
    }
  }

  /// Returns the accumulated audio as WAV bytes. Only valid after [stop]
  /// when [saveAudio] was true during [start].
  Uint8List getRecordedWavBytes() {
    if (_audioBuffer.isEmpty) return Uint8List(0);

    const sampleRate = 16000;
    const numChannels = 1;
    const bitsPerSample = 16;
    final dataSize = _audioBuffer.length;
    final fileSize = 36 + dataSize;

    final header = ByteData(44);
    // RIFF header
    header.setUint8(0, 0x52); // R
    header.setUint8(1, 0x49); // I
    header.setUint8(2, 0x46); // F
    header.setUint8(3, 0x46); // F
    header.setUint32(4, fileSize, Endian.little);
    header.setUint8(8, 0x57);  // W
    header.setUint8(9, 0x41);  // A
    header.setUint8(10, 0x56); // V
    header.setUint8(11, 0x45); // E
    // fmt sub-chunk
    header.setUint8(12, 0x66); // f
    header.setUint8(13, 0x6D); // m
    header.setUint8(14, 0x74); // t
    header.setUint8(15, 0x20); // (space)
    header.setUint32(16, 16, Endian.little); // sub-chunk size
    header.setUint16(20, 1, Endian.little);  // PCM format
    header.setUint16(22, numChannels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, sampleRate * numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(32, numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);
    // data sub-chunk
    header.setUint8(36, 0x64); // d
    header.setUint8(37, 0x61); // a
    header.setUint8(38, 0x74); // t
    header.setUint8(39, 0x61); // a
    header.setUint32(40, dataSize, Endian.little);

    final wav = Uint8List(44 + dataSize);
    wav.setAll(0, header.buffer.asUint8List());
    wav.setAll(44, _audioBuffer);
    return wav;
  }

  /// Clears accumulated text so the next segment starts fresh.
  /// Used for auto-paragraph: commit current text, then reset.
  void resetAccumulation() {
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
  }

  void _updateNoiseDetection(List<int> pcmBytes) {
    final count = pcmBytes.length ~/ 2;
    if (count == 0) return;
    final bd = ByteData.sublistView(Uint8List.fromList(pcmBytes));
    double sumSq = 0;
    for (int i = 0; i < count; i++) {
      final s = bd.getInt16(i * 2, Endian.little).toDouble();
      sumSq += s * s;
    }
    final rms = math.sqrt(sumSq / count);
    _rmsWindow.add(rms);
    if (_rmsWindow.length > _noiseWindowSize) _rmsWindow.removeAt(0);
    if (_rmsWindow.length >= _noiseWindowSize ~/ 2) {
      final sorted = List<double>.from(_rmsWindow)..sort();
      // 25th percentile ≈ ambient noise floor (captures pauses)
      final noiseFloor = sorted[sorted.length ~/ 4];
      final wasNoisy = _isNoisy;
      _isNoisy = noiseFloor > _noiseRmsThreshold;
      if (_isNoisy != wasNoisy) onNoisyChanged?.call(_isNoisy);
    }
  }

  /// Compute the length of the common prefix between two strings.
  int _commonPrefixLen(String a, String b) {
    int i = 0;
    final limit = a.length < b.length ? a.length : b.length;
    while (i < limit && a.codeUnitAt(i) == b.codeUnitAt(i)) {
      i++;
    }
    return i;
  }

  String _prevRawPartial = '';

  void _commitCurrentWindow() {
    if (_currentWindowText.isNotEmpty) {
      _committedText = _committedText.isEmpty
          ? _currentWindowText
          : '$_committedText $_currentWindowText';
      _currentWindowText = '';
    }
    _prevRawPartial = '';
  }

  void _emit({bool isFinal = false}) {
    final full = _committedText.isEmpty
        ? _currentWindowText
        : _currentWindowText.isEmpty
            ? _committedText
            : '$_committedText $_currentWindowText';
    if (full.isNotEmpty) {
      _transcriptController?.add(SttSegment(text: full, isFinal: isFinal));
    }
  }

  void _handleTranscriptMessage(String raw) {
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final type = json['type'] as String?;

      // --- Transcript data (Sarvam format: {"type":"data","data":{"transcript":"..."}}) ---
      if (type == 'data') {
        final transcript =
            (json['data'] as Map<String, dynamic>?)?['transcript'] as String?;
        if (transcript != null && transcript.trim().isNotEmpty) {
          final newText = transcript.trim();
          debugPrint('[STT] transcript chunk len=${newText.length} preview="${newText.length > 30 ? newText.substring(0, 30) : newText}"');

          // Detect new VAD window via common-prefix ratio
          if (_prevRawPartial.isNotEmpty && _prevRawPartial.length > 2) {
            final prefixLen = _commonPrefixLen(newText, _prevRawPartial);
            final overlapRatio = prefixLen / _prevRawPartial.length;
            if (overlapRatio < 0.3) {
              _commitCurrentWindow();
            }
          }

          _currentWindowText = newText;
          _prevRawPartial = newText;
          _emit(isFinal: false);
        }
      }

      // --- VAD events ---
      if (type == 'events') {
        final eventData = json['data'] as Map<String, dynamic>?;
        final event = eventData?['event'] as String?;
        if (event == 'vad_end' && _currentWindowText.isNotEmpty) {
          _commitCurrentWindow();
          _emit(isFinal: true);
        }
      }

      // --- Error ---
      if (type == 'error') {
        final errorData = json['data'] as Map<String, dynamic>?;
        final errorMsg = errorData?['message'] as String? ??
            errorData?['error'] as String?;
        _transcriptController?.addError(
          StreamingSttException(errorMsg ?? 'Unknown streaming error'),
        );
      }
    } catch (_) {}
  }

  Future<void> stop() async {
    await _audioSubscription?.cancel();
    _audioSubscription = null;

    try { await _recorder.stop(); } catch (_) {}
    _denoiser.reset();
    _rmsWindow.clear();
    _isNoisy = false;

    // Clear SV buffer (audio was already sent in real-time)
    _svBuffer.clear();

    try { _channel?.sink.add(jsonEncode({"type": "flush"})); } catch (_) {}
    await Future.delayed(const Duration(milliseconds: 500));

    await _wsSubscription?.cancel();
    _wsSubscription = null;
    await _channel?.sink.close();
    _channel = null;

    _transcriptController?.close();
    _transcriptController = null;

    // Clean up speaker verification
    _speakerSv?.dispose();
    _speakerSv = null;
    _verifySpeaker = false;
    _enrolledEmbedding = null;
    _lastSpeakerVerified = true;
    _svBusy = false;
  }

  void dispose() {
    _audioSubscription?.cancel();
    _wsSubscription?.cancel();
    _channel?.sink.close();
    _transcriptController?.close();
    _recorder.dispose();
    _denoiser.dispose();
    _speakerSv?.dispose();
    _audioSubscription = null;
    _wsSubscription = null;
    _channel = null;
    _transcriptController = null;
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
    _saveAudio = false;
    _audioBuffer.clear();
    _rmsWindow.clear();
    _isNoisy = false;
    _verifySpeaker = false;
    _enrolledEmbedding = null;
    _speakerSv = null;
    _svBuffer.clear();
    _lastSpeakerVerified = true;
    _svBusy = false;
  }
}

class StreamingSttException implements Exception {
  final String message;
  const StreamingSttException(this.message);
  @override
  String toString() => 'StreamingSttException: $message';
}
