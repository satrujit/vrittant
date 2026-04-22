/// Configuration for Sarvam AI models and language codes.
/// API key is NOT stored here — it lives on the backend.
class SarvamConfig {
  SarvamConfig._();

  // Default models
  static const String sttModel = 'saaras:v3';
  static const String ttsModel = 'bulbul:v3';
  static const String translateModel = 'sarvam-translate:v1';
  static const String chatModel = 'sarvam-30b';

  // Language codes
  static const String odiaCode = 'od-IN';
  static const String englishCode = 'en-IN';
  static const String hindiCode = 'hi-IN';
}
