export 'stt_service_stub.dart'
    if (dart.library.html) 'streaming_stt_web.dart'
    if (dart.library.io) 'stt_service_native.dart';
