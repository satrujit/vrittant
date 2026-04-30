/// Configuration for Sarvam AI models and language codes.
///
/// API key is NOT stored here — it lives on the backend.
///
/// Only STT/TTS/translate model names live on the client because the
/// Sarvam STT and TTS endpoints take the model in the request body
/// (the backend proxy forwards what we send). The CHAT model is owned
/// entirely by the backend — this file used to carry a `chatModel`
/// constant ("sarvam-30b") which the mobile app shipped on every
/// `/api/llm/chat` request. Now that LLM routing is Gemini-first with
/// Sarvam fallback, the server picks the model and the client must
/// stay model-agnostic. Don't add an LLM model constant back here.
class SarvamConfig {
  SarvamConfig._();

  // STT / TTS / Translate models (Sarvam-only domain — kept on client)
  static const String sttModel = 'saaras:v3';
  static const String ttsModel = 'bulbul:v3';
  static const String translateModel = 'sarvam-translate:v1';

  // Language codes
  static const String odiaCode = 'od-IN';
  static const String englishCode = 'en-IN';
  static const String hindiCode = 'hi-IN';
}
