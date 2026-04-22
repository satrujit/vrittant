# Cross-Platform + Backend Proxy Design

**Date:** 2026-02-26
**Status:** Approved

## Problem

1. Flutter app uses web-only APIs (`dart:js_interop`, `package:web`) in 3 service files — won't compile for iOS/Android.
2. Sarvam API key is hardcoded in client code (`sarvam_config.dart`) — security risk for distributable packages.

## Decision

**Approach 1: Backend Proxy + Conditional Imports**

- Route ALL Sarvam API calls through the existing FastAPI backend.
- Use Dart conditional imports for platform-specific mic/file access.
- Zero API keys on client. Zero latency compromise (streaming WebSocket proxy).

## Backend Changes (FastAPI)

### New Endpoints

| Endpoint | Type | Purpose |
|----------|------|---------|
| `GET /ws/stt` | WebSocket | Transparent bidirectional proxy: client sends PCM audio chunks, backend relays to `wss://api.sarvam.ai/speech-to-text/ws`, returns transcript segments back. Zero buffering — immediate forwarding both directions. |
| `POST /api/llm/chat` | REST | Proxy LLM calls. Accepts `{messages, temperature, max_tokens}`, calls Sarvam `/v1/chat/completions`, returns response. |

### API Key Management

- `SARVAM_API_KEY` stored in backend `.env` / `config.py`
- Removed from Flutter `sarvam_config.dart`
- All endpoints require JWT auth (existing middleware)

### WebSocket STT Proxy Flow

```
Mobile mic → record pkg (PCM 16kHz) → WS to backend /ws/stt
                                        ↓
                                Backend relays PCM → Sarvam WSS
                                        ↓
                                Sarvam returns transcript
                                        ↓
                                Backend sends → Mobile UI (real-time)
```

Added latency: ~5-20ms (one extra hop). Transcript updates live, same UX as web.

## Flutter Service Architecture

### Conditional Imports Pattern

```
lib/core/services/
├── stt_service.dart              ← abstract interface + factory
├── stt_service_web.dart          ← existing WebSocket-to-Sarvam (web)
├── stt_service_native.dart       ← record pkg + WS-to-backend (iOS/Android)
├── file_picker_service.dart      ← abstract interface + factory
├── file_picker_service_web.dart  ← existing browser file input
├── file_picker_service_native.dart ← file_picker/image_picker packages
├── sarvam_api.dart               ← REWRITTEN: calls backend /api/llm/chat
└── sarvam_config.dart            ← language codes + model names only, NO API KEY
```

### Abstract STT Interface

```dart
abstract class SttService {
  Future<Stream<SttSegment>> start();
  Future<void> stop();
  void dispose();
}
```

- **Web impl:** Keeps existing direct-to-Sarvam WebSocket code (unchanged).
- **Native impl:** Uses `record` package for mic → streams PCM via `web_socket_channel` to backend `/ws/stt` → receives transcript segments.
- Provider/screen code unchanged — only interacts with abstract `SttService`.

### Native Audio Recording

- Package: `record` (cross-platform, supports streaming PCM)
- Format: PCM signed 16-bit LE, 16kHz mono
- WebSocket: Dart `web_socket_channel` (no JS interop)
- Auth: JWT token sent as query parameter or first message

### File Picker

- **Web:** Existing `ocr_service_web.dart` browser file input
- **Native:** `file_picker` + `image_picker` (already in pubspec)
- Same `FilePickResult` return type, conditional import pattern

### LLM Calls (All Platforms)

`sarvam_api.dart` rewritten to call backend `/api/llm/chat` instead of Sarvam directly. Uses existing `ApiService` with JWT auth. All platforms take the same code path.

## What Gets Deleted

- API key from `sarvam_config.dart`
- Direct Sarvam HTTP calls from `sarvam_api.dart`
- `dart:js_interop` imports from provider (services abstracted away)

## What Stays

- `sarvam_config.dart` — language codes, model names (no secret)
- Web STT implementation — still connects directly to Sarvam WSS (no backend needed for web)
- All UI code — unchanged, uses abstract service interfaces
