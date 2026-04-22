import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

import 'api_config.dart';
import 'sarvam_config.dart';

/// A segment of transcript from the streaming STT service.
///
/// [text] always contains the FULL accumulated transcript so far
/// (all committed windows + current in-progress window). Consumers
/// should simply display this text directly — no manual accumulation needed.
///
/// [isFinal] is `true` when the latest VAD window was just finalised
/// (speaker paused). The text still contains everything accumulated.
class SttSegment {
  final String text;
  final bool isFinal;
  const SttSegment({required this.text, this.isFinal = false});
}

/// Real-time streaming speech-to-text via Sarvam WebSocket API.
///
/// Captures raw PCM audio from the microphone using AudioContext +
/// ScriptProcessorNode, downsamples to 16 kHz mono Int16, and streams
/// base64-encoded chunks over a WebSocket to Sarvam's streaming STT endpoint.
///
/// Usage:
/// ```dart
/// final stt = StreamingSttService();
/// final stream = await stt.start();
/// stream.listen((transcript) => print(transcript));
/// // ... later ...
/// await stt.stop();
/// ```
class StreamingSttService {
  StreamingSttService({
    this.languageCode = SarvamConfig.odiaCode,
    this.model = SarvamConfig.sttModel,
  });

  final String languageCode;
  final String model;
  String? authToken;
  void Function(bool isNoisy)? onNoisyChanged;
  void Function(bool isVerified, double similarity)? onSpeakerStatusChanged;

  // Audio pipeline
  JSObject? _audioContext;
  JSObject? _scriptProcessor;
  JSObject? _sourceNode;
  web.MediaStream? _mediaStream;

  // WebSocket
  JSObject? _webSocket;
  Completer<void>? _openCompleter;

  // Transcript stream
  StreamController<SttSegment>? _transcriptController;

  // --- Accumulation state ---
  // Text committed from all previous VAD windows (finalized).
  String _committedText = '';
  // Latest partial transcript within the current VAD window.
  String _currentWindowText = '';
  // Previous raw partial (for detecting window transitions).
  String _prevRawPartial = '';

  // PCM buffering
  final List<int> _pcmBuffer = [];
  Timer? _sendTimer;
  int _nativeSampleRate = 48000;

  bool _isActive = false;

  // Audio accumulation for WAV export (not fully supported on web but
  // keeps the interface compatible with the native service).
  bool _saveAudio = false;
  final List<int> _saveBuffer = [];

  /// Whether audio is being saved for WAV export.
  bool get isSavingAudio => _saveAudio;

  /// Returns the accumulated audio as WAV bytes (web: best-effort from
  /// the downsampled 16 kHz Int16 PCM that was also sent to the STT WS).
  Uint8List getRecordedWavBytes() {
    if (_saveBuffer.isEmpty) return Uint8List(0);

    const sampleRate = 16000;
    const numChannels = 1;
    const bitsPerSample = 16;
    final dataSize = _saveBuffer.length;
    final fileSize = 36 + dataSize;

    final header = ByteData(44);
    header.setUint8(0, 0x52); header.setUint8(1, 0x49);
    header.setUint8(2, 0x46); header.setUint8(3, 0x46);
    header.setUint32(4, fileSize, Endian.little);
    header.setUint8(8, 0x57); header.setUint8(9, 0x41);
    header.setUint8(10, 0x56); header.setUint8(11, 0x45);
    header.setUint8(12, 0x66); header.setUint8(13, 0x6D);
    header.setUint8(14, 0x74); header.setUint8(15, 0x20);
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little);
    header.setUint16(22, numChannels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, sampleRate * numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(32, numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);
    header.setUint8(36, 0x64); header.setUint8(37, 0x61);
    header.setUint8(38, 0x74); header.setUint8(39, 0x61);
    header.setUint32(40, dataSize, Endian.little);

    final wav = Uint8List(44 + dataSize);
    wav.setAll(0, header.buffer.asUint8List());
    wav.setAll(44, _saveBuffer);
    return wav;
  }

  /// Opens WebSocket, starts mic capture, returns a stream of transcript
  /// segments (each segment is a VAD-delimited utterance in Odia).
  Future<Stream<SttSegment>> start({
    bool saveAudio = false,
    bool verifySpeaker = false,
    List<double>? enrolledEmbedding,
  }) async {
    if (_isActive) throw StreamingSttException('Already active');
    _isActive = true;
    _saveAudio = saveAudio;
    _saveBuffer.clear();

    _transcriptController = StreamController<SttSegment>.broadcast();

    try {
      // 1. Get microphone access
      await _acquireMicrophone();

      // 2. Open WebSocket
      await _openWebSocket();

      // 3. Set up AudioContext + ScriptProcessorNode for PCM capture
      _setupAudioPipeline();

      // 4. Start periodic send timer (every 500ms)
      _sendTimer = Timer.periodic(const Duration(milliseconds: 500), (_) {
        _sendBufferedAudio();
      });

      return _transcriptController!.stream;
    } catch (e) {
      await _cleanup();
      rethrow;
    }
  }

  /// Stops recording, flushes remaining audio, waits for final transcript,
  /// and closes all resources.
  Future<void> stop() async {
    if (!_isActive) return;

    // Stop the send timer
    _sendTimer?.cancel();
    _sendTimer = null;

    // Flush remaining audio
    _sendBufferedAudio();

    // Send flush signal to force final transcript
    _sendFlush();

    // Wait briefly for final transcript to arrive
    await Future<void>.delayed(const Duration(milliseconds: 800));

    await _cleanup();
  }

  /// Clears accumulated text so the next segment starts fresh.
  void resetAccumulation() {
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
  }

  /// Defensively releases all resources.
  void dispose() {
    _sendTimer?.cancel();
    _sendTimer = null;
    _cleanup();
  }

  // ---------------------------------------------------------------------------
  // Microphone
  // ---------------------------------------------------------------------------

  Future<void> _acquireMicrophone() async {
    final navigator = globalContext['navigator'] as JSObject?;
    if (navigator == null) {
      throw StreamingSttException('navigator is not available');
    }

    final mediaDevices = navigator['mediaDevices'] as JSObject?;
    if (mediaDevices == null) {
      throw StreamingSttException(
        'mediaDevices is not available. '
        'Make sure you are on HTTPS or localhost.',
      );
    }

    final constraints = <String, dynamic>{'audio': true}.jsify() as JSObject;

    final promise = mediaDevices.callMethod(
      'getUserMedia'.toJS,
      constraints,
    ) as JSPromise<JSObject>;

    final jsStream = await promise.toDart.timeout(
      const Duration(seconds: 15),
      onTimeout: () {
        throw StreamingSttException(
          'Microphone permission timed out.',
        );
      },
    );

    _mediaStream = jsStream as web.MediaStream;
  }

  // ---------------------------------------------------------------------------
  // WebSocket
  // ---------------------------------------------------------------------------


  Future<void> _openWebSocket() async {
    // Connect to backend WebSocket proxy instead of Sarvam directly
    final wsBase = ApiConfig.baseUrl.replaceFirst('http', 'ws');
    final wsUrl = '$wsBase/ws/stt'
        '?token=${authToken ?? ""}'
        '&language_code=$languageCode'
        '&model=$model';

    final WebSocketClass = globalContext['WebSocket'] as JSFunction?;
    if (WebSocketClass == null) {
      throw StreamingSttException('WebSocket is not available');
    }

    _webSocket = WebSocketClass.callAsConstructor(
      wsUrl.toJS,
    ) as JSObject;

    _openCompleter = Completer<void>();


    _webSocket!['onopen'] = ((JSAny _) {
      if (_openCompleter != null && !_openCompleter!.isCompleted) {
        _openCompleter!.complete();
      }
    }).toJS;

    _webSocket!['onmessage'] = ((JSObject event) {
      final data = (event['data'] as JSString).toDart;
      _handleMessage(data);
    }).toJS;

    _webSocket!['onerror'] = ((JSAny error) {
      if (_openCompleter != null && !_openCompleter!.isCompleted) {
        _openCompleter!.completeError(
          StreamingSttException('WebSocket connection error'),
        );
      }
      _transcriptController?.addError(
        StreamingSttException('WebSocket error'),
      );
    }).toJS;

    _webSocket!['onclose'] = ((JSObject event) {
      final code = (event['code'] as JSNumber?)?.toDartInt;
      // If closed unexpectedly while active, notify via stream
      if (_isActive) {
        _transcriptController?.addError(
          StreamingSttException('WebSocket closed unexpectedly (code=$code)'),
        );
      }
    }).toJS;

    // Wait for connection with timeout
    await _openCompleter!.future.timeout(
      const Duration(seconds: 10),
      onTimeout: () {
        throw StreamingSttException(
          'WebSocket connection timed out.',
        );
      },
    );
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

  /// Emit the full accumulated text to the stream.
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

  /// Commit the current window's text into the accumulated buffer.
  void _commitCurrentWindow() {
    if (_currentWindowText.isNotEmpty) {
      _committedText = _committedText.isEmpty
          ? _currentWindowText
          : '$_committedText $_currentWindowText';
      _currentWindowText = '';
    }
    _prevRawPartial = '';
  }

  void _handleMessage(String data) {
    try {
      final json = jsonDecode(data) as Map<String, dynamic>;
      final type = json['type'] as String?;

      // --- Transcript data ---
      if (type == 'data') {
        final transcript =
            (json['data'] as Map<String, dynamic>?)?['transcript'] as String?;
        if (transcript != null && transcript.trim().isNotEmpty) {
          final newText = transcript.trim();

          // Determine if this is a new VAD window vs continuation.
          // We use the common-prefix ratio between consecutive raw partials.
          // If the new partial shares < 30% prefix with the previous one,
          // it's a new window and we should commit the previous window.
          if (_prevRawPartial.isNotEmpty && _prevRawPartial.length > 2) {
            final prefixLen = _commonPrefixLen(newText, _prevRawPartial);
            final overlapRatio = prefixLen / _prevRawPartial.length;

            if (overlapRatio < 0.3) {
              // New VAD window detected — commit previous window
              _commitCurrentWindow();
            }
          }

          // Update current window text (the API's partial is the latest
          // version of text for this window — cumulative or otherwise).
          _currentWindowText = newText;
          _prevRawPartial = newText;

          // Emit full accumulated text (committed + current window)
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
    } catch (_) {
      // Ignore malformed JSON silently
    }
  }

  void _sendFlush() {
    try {
      final readyState = (_webSocket?['readyState'] as JSNumber?)?.toDartInt;
      if (readyState == 1) {
        // OPEN
        final msg = jsonEncode({'type': 'flush'});
        _webSocket!.callMethod('send'.toJS, msg.toJS);
      }
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Audio Pipeline
  // ---------------------------------------------------------------------------

  void _setupAudioPipeline() {
    // Create AudioContext
    final AudioContextClass = globalContext['AudioContext'] as JSFunction? ??
        globalContext['webkitAudioContext'] as JSFunction?;

    if (AudioContextClass == null) {
      throw StreamingSttException('AudioContext is not available');
    }

    _audioContext = AudioContextClass.callAsConstructor() as JSObject;
    _nativeSampleRate =
        ((_audioContext!['sampleRate'] as JSNumber?)?.toDartDouble ?? 48000)
            .toInt();

    // Create MediaStreamSource from mic
    _sourceNode = _audioContext!.callMethod(
      'createMediaStreamSource'.toJS,
      _mediaStream!,
    ) as JSObject;

    // Create ScriptProcessorNode (4096 buffer, 1 in, 1 out)
    _scriptProcessor = _audioContext!.callMethod(
      'createScriptProcessor'.toJS,
      4096.toJS,
      1.toJS,
      1.toJS,
    ) as JSObject;

    // Set up audio processing callback
    _scriptProcessor!['onaudioprocess'] = ((JSObject event) {
      _processAudioChunk(event);
    }).toJS;

    // Connect: source → processor → destination
    _sourceNode!.callMethod('connect'.toJS, _scriptProcessor!);
    final destination = _audioContext!['destination'] as JSObject;
    _scriptProcessor!.callMethod('connect'.toJS, destination);
  }

  void _processAudioChunk(JSObject event) {
    try {
      final inputBuffer = event['inputBuffer'] as JSObject;
      final channelDataJS =
          inputBuffer.callMethod('getChannelData'.toJS, 0.toJS) as JSObject;

      // Convert Float32Array to Dart Float32List via ArrayBuffer
      final jsBuffer = channelDataJS['buffer'] as JSArrayBuffer;
      final byteOffset =
          (channelDataJS['byteOffset'] as JSNumber).toDartInt;
      final length = (channelDataJS['length'] as JSNumber).toDartInt;
      final dartBuffer = jsBuffer.toDart;
      final float32List = dartBuffer.asFloat32List(byteOffset, length);

      // Downsample from native rate to 16kHz and convert to Int16 LE
      final ratio = _nativeSampleRate / 16000;
      final outputLength = (length / ratio).floor();

      for (int i = 0; i < outputLength; i++) {
        final srcIndex = (i * ratio).floor();
        if (srcIndex >= length) break;

        final sample = float32List[srcIndex];
        final int16 = (sample * 32767).round().clamp(-32768, 32767);
        final lo = int16 & 0xFF;
        final hi = (int16 >> 8) & 0xFF;
        // Little-endian: low byte first
        _pcmBuffer.add(lo);
        _pcmBuffer.add(hi);
        // Also save for WAV export
        if (_saveAudio) {
          _saveBuffer.add(lo);
          _saveBuffer.add(hi);
        }
      }
    } catch (_) {
      // Silently skip bad chunks
    }
  }

  void _sendBufferedAudio() {
    if (_pcmBuffer.isEmpty) return;

    final readyState = (_webSocket?['readyState'] as JSNumber?)?.toDartInt;
    if (readyState != 1) return; // Not OPEN

    try {
      final bytes = Uint8List.fromList(_pcmBuffer);
      _pcmBuffer.clear();
      final b64 = base64Encode(bytes);

      final message = jsonEncode({
        'audio': {
          'data': b64,
          'sample_rate': 16000,
          'encoding': 'audio/wav',
        },
      });

      _webSocket!.callMethod('send'.toJS, message.toJS);
    } catch (_) {
      // If send fails, discard the buffer to prevent memory buildup
      _pcmBuffer.clear();
    }
  }

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  Future<void> _cleanup() async {
    _isActive = false;

    // Disconnect audio graph
    try {
      _scriptProcessor?.callMethod('disconnect'.toJS);
    } catch (_) {}
    try {
      _sourceNode?.callMethod('disconnect'.toJS);
    } catch (_) {}

    // Close AudioContext
    try {
      if (_audioContext != null) {
        final closePromise =
            _audioContext!.callMethod('close'.toJS) as JSPromise?;
        if (closePromise != null) {
          await closePromise.toDart.timeout(
            const Duration(seconds: 2),
            onTimeout: () => null,
          );
        }
      }
    } catch (_) {}

    // Stop media tracks
    if (_mediaStream != null) {
      try {
        final tracks = _mediaStream!.getTracks().toDart;
        for (final track in tracks) {
          track.stop();
        }
      } catch (_) {}
    }

    // Close WebSocket
    try {
      final readyState = (_webSocket?['readyState'] as JSNumber?)?.toDartInt;
      if (readyState == 1 || readyState == 0) {
        _webSocket?.callMethod('close'.toJS);
      }
    } catch (_) {}

    // Close stream controller
    try {
      await _transcriptController?.close();
    } catch (_) {}

    _audioContext = null;
    _scriptProcessor = null;
    _sourceNode = null;
    _mediaStream = null;
    _webSocket = null;
    _transcriptController = null;
    _openCompleter = null;
    _pcmBuffer.clear();
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
    _saveAudio = false;
    _saveBuffer.clear();
  }
}

/// Exception thrown by the streaming STT service.
class StreamingSttException implements Exception {
  final String message;
  const StreamingSttException(this.message);

  @override
  String toString() => 'StreamingSttException: $message';
}
