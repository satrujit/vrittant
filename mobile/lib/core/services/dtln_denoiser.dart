import 'dart:math' as math;
import 'dart:typed_data';

import 'package:fftea/fftea.dart';
import 'package:tflite_flutter/tflite_flutter.dart';

/// On-device speech enhancement using the DTLN (Dual-signal Transformation
/// LSTM Network) model. Processes 16kHz 16-bit PCM mono audio in real-time.
///
/// Two-stage architecture:
///   Stage 1 (model_1): STFT magnitude → LSTM → mask estimation
///   Stage 2 (model_2): Time-domain block → LSTM → enhanced signal
///
/// Usage:
///   final denoiser = DtlnDenoiser();
///   await denoiser.init();
///   final enhanced = denoiser.process(rawPcmBytes);
///   denoiser.dispose();
class DtlnDenoiser {
  static const int _blockSize = 512; // FFT frame size in samples
  static const int _hopSize = 128; // Hop size in samples (8ms at 16kHz)
  static const int _fftBins = _blockSize ~/ 2 + 1; // 257 RFFT output bins

  // TFLite interpreters
  Interpreter? _model1;
  Interpreter? _model2;

  // Persistent sliding-window buffers
  late Float64List _inBuffer;
  late Float64List _outBuffer;

  // LSTM hidden states: shape [1, 2, 128, 2]
  // (batch=1, 2 LSTM layers, 128 units, 2 for h+c)
  late List<List<List<List<double>>>> _lstmState1;
  late List<List<List<List<double>>>> _lstmState2;

  // Reusable FFT instance
  late FFT _fft;

  bool _initialized = false;

  /// Whether the denoiser loaded successfully and is ready to process audio.
  bool get isInitialized => _initialized;

  /// Load TFLite models and allocate buffers. Returns false on failure.
  Future<bool> init() async {
    try {
      _model1 =
          await Interpreter.fromAsset('assets/models/model_quant_1.tflite');
      _model2 =
          await Interpreter.fromAsset('assets/models/model_quant_2.tflite');

      _fft = FFT(_blockSize);
      _inBuffer = Float64List(_blockSize);
      _outBuffer = Float64List(_blockSize);
      _lstmState1 = _zeroState();
      _lstmState2 = _zeroState();

      _initialized = true;
      return true;
    } catch (e) {
      _initialized = false;
      return false;
    }
  }

  /// Process a chunk of raw PCM16-LE bytes and return denoised PCM16-LE bytes.
  /// If not initialized or on error, returns the input unchanged.
  Uint8List process(List<int> pcmBytes) {
    if (!_initialized || _model1 == null || _model2 == null) {
      return Uint8List.fromList(pcmBytes);
    }

    try {
      final samples = _pcm16ToFloat64(pcmBytes);
      final outputSamples = Float64List(samples.length);
      int outIdx = 0;

      for (int i = 0; i + _hopSize <= samples.length; i += _hopSize) {
        // Shift in_buffer left by hopSize, append new hop
        for (int j = 0; j < _blockSize - _hopSize; j++) {
          _inBuffer[j] = _inBuffer[j + _hopSize];
        }
        for (int j = 0; j < _hopSize; j++) {
          _inBuffer[_blockSize - _hopSize + j] = samples[i + j];
        }

        // --- Stage 1: Frequency-domain mask estimation ---
        // RFFT → 257 complex bins
        final spectrum = _fft.realFft(_inBuffer);

        // Extract magnitude and phase
        final magnitude = List<double>.filled(_fftBins, 0.0);
        final phase = Float64List(_fftBins);
        for (int k = 0; k < _fftBins; k++) {
          final re = spectrum[k].x;
          final im = spectrum[k].y;
          magnitude[k] = math.sqrt(re * re + im * im);
          phase[k] = math.atan2(im, re);
        }

        // Model 1 inference: [magnitude(1,1,257), state(1,2,128,2)]
        //                  → [mask(1,1,257), newState(1,2,128,2)]
        final magInput = [
          [magnitude]
        ]; // shape [1,1,257]
        final maskOutput = [
          [List<double>.filled(_fftBins, 0.0)]
        ];
        final newState1 = _zeroState();

        _model1!.runForMultipleInputs(
          [magInput, _lstmState1],
          {0: maskOutput, 1: newState1},
        );
        _lstmState1 = newState1;

        // Apply mask and reconstruct complex spectrum
        final enhanced = Float64x2List(_fftBins);
        for (int k = 0; k < _fftBins; k++) {
          final estMag = magnitude[k] * maskOutput[0][0][k];
          enhanced[k] =
              Float64x2(estMag * math.cos(phase[k]), estMag * math.sin(phase[k]));
        }

        // iRFFT → 512 time-domain samples
        final timeBlock = _fft.realInverseFft(enhanced);

        // --- Stage 2: Time-domain enhancement ---
        // Model 2 inference: [block(1,1,512), state(1,2,128,2)]
        //                  → [enhanced(1,1,512), newState(1,2,128,2)]
        final timeInput = [
          [timeBlock.toList()]
        ]; // shape [1,1,512]
        final enhancedOutput = [
          [List<double>.filled(_blockSize, 0.0)]
        ];
        final newState2 = _zeroState();

        _model2!.runForMultipleInputs(
          [timeInput, _lstmState2],
          {0: enhancedOutput, 1: newState2},
        );
        _lstmState2 = newState2;

        // --- Overlap-add reconstruction ---
        final outBlock = enhancedOutput[0][0];

        // Add overlapping portion to out_buffer
        for (int j = 0; j < _blockSize - _hopSize; j++) {
          _outBuffer[j] += outBlock[j];
        }

        // Extract first hopSize samples as output
        if (outIdx + _hopSize <= outputSamples.length) {
          for (int j = 0; j < _hopSize; j++) {
            outputSamples[outIdx + j] = _outBuffer[j];
          }
        }
        outIdx += _hopSize;

        // Shift out_buffer: copy tail of outBlock, zero the end
        for (int j = 0; j < _blockSize - _hopSize; j++) {
          _outBuffer[j] = outBlock[_hopSize + j];
        }
        for (int j = _blockSize - _hopSize; j < _blockSize; j++) {
          _outBuffer[j] = 0.0;
        }
      }

      // Pass through any remaining samples that don't fill a full hop
      final processed = (samples.length ~/ _hopSize) * _hopSize;
      for (int i = processed; i < samples.length; i++) {
        if (outIdx < outputSamples.length) {
          outputSamples[outIdx++] = samples[i];
        }
      }

      return _float64ToPcm16(outputSamples);
    } catch (e) {
      return Uint8List.fromList(pcmBytes);
    }
  }

  /// Reset buffers and LSTM states between recording sessions.
  void reset() {
    if (!_initialized) return;
    _inBuffer.fillRange(0, _blockSize, 0.0);
    _outBuffer.fillRange(0, _blockSize, 0.0);
    _lstmState1 = _zeroState();
    _lstmState2 = _zeroState();
  }

  /// Release TFLite interpreters and free resources.
  void dispose() {
    _model1?.close();
    _model2?.close();
    _model1 = null;
    _model2 = null;
    _initialized = false;
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Create a zero-initialized LSTM state tensor: shape [1, 2, 128, 2].
  static List<List<List<List<double>>>> _zeroState() {
    return List.generate(
      1,
      (_) => List.generate(
        2,
        (_) => List.generate(128, (_) => List<double>.filled(2, 0.0)),
      ),
    );
  }

  /// Convert PCM16 little-endian bytes to Float64 samples in [-1.0, 1.0].
  static Float64List _pcm16ToFloat64(List<int> bytes) {
    final count = bytes.length ~/ 2;
    final out = Float64List(count);
    final bd = ByteData.sublistView(Uint8List.fromList(bytes));
    for (int i = 0; i < count; i++) {
      out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
    }
    return out;
  }

  /// Convert Float64 samples in [-1.0, 1.0] to PCM16 little-endian bytes.
  static Uint8List _float64ToPcm16(Float64List samples) {
    final bytes = Uint8List(samples.length * 2);
    final bd = ByteData.sublistView(bytes);
    for (int i = 0; i < samples.length; i++) {
      final clamped = samples[i].clamp(-1.0, 1.0);
      bd.setInt16(i * 2, (clamped * 32767.0).round(), Endian.little);
    }
    return bytes;
  }
}
