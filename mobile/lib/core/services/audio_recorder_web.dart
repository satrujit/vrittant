import 'dart:async';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

/// A web-based audio recorder that uses the browser's MediaRecorder API.
///
/// Uses raw dart:js_interop for getUserMedia to avoid package:web Promise issues.
class WebAudioRecorder {
  web.MediaRecorder? _mediaRecorder;
  web.MediaStream? _stream;
  final List<web.Blob> _chunks = [];
  Completer<Uint8List>? _stopCompleter;

  bool get isRecording => _mediaRecorder?.state == 'recording';

  /// Requests microphone access and starts recording audio.
  ///
  /// Returns `true` if recording started successfully.
  /// Throws if the browser denies microphone access.
  Future<bool> start() async {
    try {
      _chunks.clear();

      // Use raw JS interop to call getUserMedia — avoids package:web Promise issues
      final navigator = globalContext['navigator'] as JSObject?;
      if (navigator == null) {
        throw AudioRecorderException('navigator is not available');
      }

      final mediaDevices = navigator['mediaDevices'] as JSObject?;
      if (mediaDevices == null) {
        throw AudioRecorderException(
          'mediaDevices is not available. '
          'Make sure you are on HTTPS or localhost.',
        );
      }

      // Build constraints as a plain JS object
      final constraints = <String, dynamic>{'audio': true}.jsify() as JSObject;

      // Call getUserMedia via raw JS interop
      final promise = mediaDevices.callMethod(
        'getUserMedia'.toJS,
        constraints,
      ) as JSPromise<JSObject>;

      // Await with a timeout so it doesn't hang forever
      final jsStream = await promise.toDart.timeout(
        const Duration(seconds: 15),
        onTimeout: () {
          throw AudioRecorderException(
            'Microphone permission timed out. '
            'Please check the permission popup in your browser address bar.',
          );
        },
      );

      _stream = jsStream as web.MediaStream;

      // Create MediaRecorder with webm/opus format
      final options = web.MediaRecorderOptions(
        mimeType: 'audio/webm;codecs=opus',
      );

      _mediaRecorder = web.MediaRecorder(_stream!, options);

      // Listen for data chunks
      _mediaRecorder!.ondataavailable = ((web.BlobEvent event) {
        if (event.data.size > 0) {
          _chunks.add(event.data);
        }
      }).toJS;

      // Start recording — request data every 250ms for responsive waveform
      _mediaRecorder!.start(250);

      return true;
    } on AudioRecorderException {
      rethrow;
    } catch (e) {
      throw AudioRecorderException('Failed to start recording: $e');
    }
  }

  /// Stops the recording and returns the audio as raw bytes (WebM/Opus format).
  Future<Uint8List> stop() async {
    if (_mediaRecorder == null || _mediaRecorder!.state != 'recording') {
      throw AudioRecorderException('No active recording to stop.');
    }

    _stopCompleter = Completer<Uint8List>();

    // Listen for the stop event which fires after all data is flushed.
    // The callback must be synchronous for JS interop.
    _mediaRecorder!.onstop = ((web.Event _) {
      _processRecordedChunks();
    }).toJS;

    _mediaRecorder!.stop();

    return _stopCompleter!.future;
  }

  /// Cancels the current recording without returning data.
  void cancel() {
    if (_mediaRecorder?.state == 'recording') {
      _mediaRecorder!.stop();
    }
    _cleanup();
    _chunks.clear();
    if (_stopCompleter != null && !_stopCompleter!.isCompleted) {
      _stopCompleter!.completeError(
        AudioRecorderException('Recording cancelled.'),
      );
    }
  }

  /// Asynchronous processing triggered by the synchronous onstop callback.
  Future<void> _processRecordedChunks() async {
    try {
      final blob = web.Blob(
        _chunks.map((c) => c as JSObject).toList().toJS,
        web.BlobPropertyBag(type: 'audio/webm'),
      );

      final arrayBuffer = await blob.arrayBuffer().toDart;
      final bytes = arrayBuffer.toDart.asUint8List();

      _cleanup();

      if (_stopCompleter != null && !_stopCompleter!.isCompleted) {
        _stopCompleter!.complete(bytes);
      }
    } catch (e) {
      if (_stopCompleter != null && !_stopCompleter!.isCompleted) {
        _stopCompleter!.completeError(
          AudioRecorderException('Failed to process recording: $e'),
        );
      }
    }
  }

  void _cleanup() {
    if (_stream != null) {
      final tracks = _stream!.getTracks().toDart;
      for (final track in tracks) {
        track.stop();
      }
    }
    _stream = null;
    _mediaRecorder = null;
    _chunks.clear();
  }

  /// Releases all resources.
  void dispose() {
    cancel();
  }
}

/// Exception thrown by the audio recorder.
class AudioRecorderException implements Exception {
  final String message;
  const AudioRecorderException(this.message);

  @override
  String toString() => 'AudioRecorderException: $message';
}
