import 'dart:async';
import 'dart:typed_data';

class SttSegment {
  final String text;
  final bool isFinal;
  const SttSegment({required this.text, this.isFinal = false});
}

class StreamingSttService {
  StreamingSttService({String languageCode = 'od-IN', String model = 'saaras:v3'});
  String? authToken;
  void Function(bool isNoisy)? onNoisyChanged;
  void Function(bool isVerified, double similarity)? onSpeakerStatusChanged;
  bool get isSavingAudio => false;
  Future<Stream<SttSegment>> start({
    bool saveAudio = false,
    bool verifySpeaker = false,
    List<double>? enrolledEmbedding,
  }) => throw UnsupportedError('No STT on this platform');
  Future<void> stop() => throw UnsupportedError('No STT on this platform');
  Uint8List getRecordedWavBytes() => Uint8List(0);
  void resetAccumulation() {}
  void dispose() {}
}

class StreamingSttException implements Exception {
  final String message;
  const StreamingSttException(this.message);
  @override
  String toString() => 'StreamingSttException: $message';
}
