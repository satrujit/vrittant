/// Configuration for Sarvam AI models and language codes.
/// API key is NOT stored here — it lives on the backend.
class SarvamConfig {
  SarvamConfig._();

  // Default models
  static const String sttModel = 'saaras:v3';
  static const String ttsModel = 'bulbul:v3';
  static const String translateModel = 'sarvam-translate:v1';
  // sarvam-105b is Sarvam's flagship model. Materially better Odia
  // proper-noun handling than sarvam-30b at ~1.6x the cost (~₹0.03 vs
  // ₹0.02 per call). Used for headline gen, polish, generate-story —
  // all editorial drafting where output quality is what matters.
  static const String chatModel = 'sarvam-105b';

  // Language codes
  static const String odiaCode = 'od-IN';
  static const String englishCode = 'en-IN';
  static const String hindiCode = 'hi-IN';
}
