# Cross-Platform + Backend Proxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Flutter app compile and run on iOS/Android by abstracting web-only services behind conditional imports, and route all Sarvam API calls through the FastAPI backend so zero API keys ship in the client.

**Architecture:** Backend gets 2 new endpoints: a WebSocket STT proxy (`/ws/stt`) and a REST LLM proxy (`/api/llm/chat`). Flutter services are split into abstract interface + web impl + native impl using Dart conditional imports. The provider layer stays unchanged — it only touches abstract interfaces.

**Tech Stack:** FastAPI + websockets (Python), Flutter + record + web_socket_channel (Dart), Sarvam AI API

---

### Task 1: Backend — Add Sarvam API key to config

**Files:**
- Modify: `newsflow-api/app/config.py:1-10`
- Modify: `newsflow-api/requirements.txt`

**Step 1: Add SARVAM_API_KEY to Settings**

In `newsflow-api/app/config.py`, add the key:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./newsflow.db"
    SECRET_KEY: str = "newsflow-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    HARDCODED_OTP: str = "123456"
    SARVAM_API_KEY: str = "sk_1e8g5nqb_uSETUcaWKVZ9GLDDsHxq2HZe"
    SARVAM_BASE_URL: str = "https://api.sarvam.ai"

settings = Settings()
```

**Step 2: Add websockets + httpx to requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
pydantic-settings==2.5.0
websockets==13.1
httpx==0.27.2
```

**Step 3: Install deps**

Run: `cd newsflow-api && pip install -r requirements.txt`

**Step 4: Commit**

```bash
git add newsflow-api/app/config.py newsflow-api/requirements.txt
git commit -m "feat(api): add Sarvam API key to backend config"
```

---

### Task 2: Backend — WebSocket STT proxy endpoint

**Files:**
- Create: `newsflow-api/app/routers/sarvam.py`
- Modify: `newsflow-api/app/main.py:19-20`

**Step 1: Create the sarvam router with WebSocket STT proxy**

Create `newsflow-api/app/routers/sarvam.py`:

```python
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
import websockets

from ..config import settings

router = APIRouter()


def _authenticate_ws(token: str) -> str:
    """Validate JWT and return reporter_id. Raises on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        reporter_id = payload.get("sub")
        if reporter_id is None:
            raise ValueError("Invalid token")
        return reporter_id
    except JWTError:
        raise ValueError("Invalid token")


@router.websocket("/ws/stt")
async def stt_proxy(
    ws: WebSocket,
    token: str = Query(...),
    language_code: str = Query("od-IN"),
    model: str = Query("saaras:v3"),
):
    """
    Bidirectional WebSocket proxy for Sarvam streaming STT.

    Client sends binary PCM audio frames.
    Server relays them to Sarvam and forwards transcript JSON back.
    Zero buffering — immediate pass-through both directions.
    """
    # Authenticate
    try:
        _authenticate_ws(token)
    except ValueError:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()

    # Connect to Sarvam WSS
    sarvam_url = f"wss://api.sarvam.ai/speech-to-text/ws"
    sarvam_subprotocol = f"api-subscription-key.{settings.SARVAM_API_KEY}"

    try:
        async with websockets.connect(
            sarvam_url,
            subprotocols=[sarvam_subprotocol],
            additional_headers={"language_code": language_code, "model": model},
        ) as sarvam_ws:

            async def client_to_sarvam():
                """Forward audio from client → Sarvam."""
                try:
                    while True:
                        data = await ws.receive_bytes()
                        await sarvam_ws.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception:
                    pass

            async def sarvam_to_client():
                """Forward transcripts from Sarvam → client."""
                try:
                    async for message in sarvam_ws:
                        if isinstance(message, str):
                            await ws.send_text(message)
                        else:
                            await ws.send_bytes(message)
                except websockets.ConnectionClosed:
                    pass
                except Exception:
                    pass

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_sarvam()),
                    asyncio.create_task(sarvam_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        try:
            await ws.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
```

**Step 2: Register the router in main.py**

In `newsflow-api/app/main.py`, after line 20, add:

```python
from .routers import auth, stories, sarvam

# ... existing router includes ...
app.include_router(sarvam.router, tags=["sarvam"])
```

**Step 3: Test manually**

Run: `cd newsflow-api && uvicorn app.main:app --reload --port 8000`
Verify: `curl -s http://localhost:8000/docs` shows the new `/ws/stt` endpoint.

**Step 4: Commit**

```bash
git add newsflow-api/app/routers/sarvam.py newsflow-api/app/main.py
git commit -m "feat(api): add WebSocket STT proxy to Sarvam"
```

---

### Task 3: Backend — REST LLM chat proxy endpoint

**Files:**
- Modify: `newsflow-api/app/routers/sarvam.py`

**Step 1: Add LLM chat proxy to the sarvam router**

Append to `newsflow-api/app/routers/sarvam.py`:

```python
import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..deps import get_current_reporter
from ..models.reporter import Reporter


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str = "sarvam-m"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.post("/api/llm/chat")
async def llm_chat_proxy(
    body: ChatRequest,
    reporter: Reporter = Depends(get_current_reporter),
):
    """
    Proxy LLM chat completions to Sarvam.
    Requires JWT auth. API key never leaves the server.
    """
    payload = {
        "model": body.model,
        "messages": body.messages,
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{settings.SARVAM_BASE_URL}/v1/chat/completions",
                json=payload,
                headers={
                    "api-subscription-key": settings.SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Sarvam API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Sarvam API: {str(e)}",
            )
```

**Step 2: Test manually**

Run: `curl -X POST http://localhost:8000/api/llm/chat -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hello"}]}'`
Expected: JSON response from Sarvam LLM.

**Step 3: Commit**

```bash
git add newsflow-api/app/routers/sarvam.py
git commit -m "feat(api): add REST LLM chat proxy endpoint"
```

---

### Task 4: Flutter — Add native packages to pubspec.yaml

**Files:**
- Modify: `newsflow/pubspec.yaml`

**Step 1: Add record and web_socket_channel**

Add under `dependencies:` in `newsflow/pubspec.yaml`:

```yaml
  record: ^5.2.1
  web_socket_channel: ^3.0.1
```

**Step 2: Run pub get**

Run: `cd newsflow && flutter pub get`
Expected: No errors.

**Step 3: Commit**

```bash
git add pubspec.yaml pubspec.lock
git commit -m "feat: add record and web_socket_channel packages"
```

---

### Task 5: Flutter — Abstract STT service with conditional imports

**Files:**
- Create: `newsflow/lib/core/services/stt_service.dart` (interface + factory)
- Rename: `newsflow/lib/core/services/streaming_stt_web.dart` (keep as web impl, no changes needed)
- Create: `newsflow/lib/core/services/stt_service_native.dart` (native impl)
- Create: `newsflow/lib/core/services/stt_service_stub.dart` (stub for conditional import)

**Step 1: Create the stub file**

Create `newsflow/lib/core/services/stt_service_stub.dart`:

```dart
import 'dart:async';

/// Stub — should never be instantiated directly.
/// Conditional imports pick the real implementation.
class SttSegment {
  final String text;
  final bool isFinal;
  const SttSegment({required this.text, this.isFinal = false});
}

class StreamingSttService {
  StreamingSttService({String languageCode = 'od-IN', String model = 'saaras:v3'});

  Future<Stream<SttSegment>> start() => throw UnsupportedError('No STT on this platform');
  Future<void> stop() => throw UnsupportedError('No STT on this platform');
  void dispose() {}
}

class StreamingSttException implements Exception {
  final String message;
  const StreamingSttException(this.message);
  @override
  String toString() => 'StreamingSttException: $message';
}
```

**Step 2: Create the abstract interface + conditional import barrel**

Create `newsflow/lib/core/services/stt_service.dart`:

```dart
export 'stt_service_stub.dart'
    if (dart.library.html) 'streaming_stt_web.dart'
    if (dart.library.io) 'stt_service_native.dart';
```

**Step 3: Create the native implementation**

Create `newsflow/lib/core/services/stt_service_native.dart`:

```dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'api_config.dart';

/// A segment of transcript from the streaming STT service.
class SttSegment {
  final String text;
  final bool isFinal;
  const SttSegment({required this.text, this.isFinal = false});
}

/// Native streaming STT that records PCM audio via the `record` package
/// and streams it to the backend WebSocket proxy at /ws/stt.
///
/// The backend relays audio to Sarvam and returns transcript segments.
class StreamingSttService {
  StreamingSttService({
    this.languageCode = 'od-IN',
    this.model = 'saaras:v3',
  });

  final String languageCode;
  final String model;

  final AudioRecorder _recorder = AudioRecorder();
  WebSocketChannel? _channel;
  StreamController<SttSegment>? _transcriptController;
  StreamSubscription? _audioSubscription;
  StreamSubscription? _wsSubscription;

  // --- Accumulation state (mirrors web impl) ---
  String _committedText = '';
  String _currentWindowText = '';
  String _prevRawPartial = '';

  /// JWT token for auth — set before calling start().
  String? authToken;

  /// Starts recording and streaming to backend.
  /// Returns a stream of transcript segments.
  Future<Stream<SttSegment>> start() async {
    if (_transcriptController != null) {
      throw StreamingSttException('Already recording');
    }

    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
    _transcriptController = StreamController<SttSegment>.broadcast();

    // 1. Connect WebSocket to backend proxy
    final wsBase = ApiConfig.baseUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse(
      '$wsBase/ws/stt?token=${authToken ?? ""}&language_code=$languageCode&model=$model',
    );
    _channel = WebSocketChannel.connect(uri);

    // 2. Listen for transcript messages from backend
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

    // 3. Start recording PCM 16kHz mono
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

    // 4. Forward audio chunks to WebSocket as base64 (matching Sarvam format)
    _audioSubscription = audioStream.listen(
      (data) {
        if (_channel != null) {
          final base64Audio = base64Encode(data);
          _channel!.sink.add(base64Audio);
        }
      },
      onError: (error) {
        _transcriptController?.addError(
          StreamingSttException('Audio recording error: $error'),
        );
      },
    );

    return _transcriptController!.stream;
  }

  void _handleTranscriptMessage(String raw) {
    try {
      final json = jsonDecode(raw);

      // Handle Sarvam's transcript format
      if (json is Map<String, dynamic>) {
        if (json.containsKey('error')) {
          _transcriptController?.addError(
            StreamingSttException(json['error'].toString()),
          );
          return;
        }

        final type = json['type'] as String? ?? '';
        final text = (json['transcript'] as String? ?? '').trim();

        if (type == 'final' || (json['is_final'] == true)) {
          // Window finalized — commit
          if (text.isNotEmpty) {
            final deduped = _deduplicateAgainstPrev(text, _prevRawPartial);
            if (_committedText.isNotEmpty && deduped.isNotEmpty) {
              _committedText += ' $deduped';
            } else if (deduped.isNotEmpty) {
              _committedText = deduped;
            }
            _prevRawPartial = '';
          }
          _currentWindowText = '';
          _transcriptController?.add(SttSegment(
            text: _committedText,
            isFinal: true,
          ));
        } else {
          // Partial — update current window
          _currentWindowText = text;
          _prevRawPartial = text;
          final fullText = _committedText.isEmpty
              ? text
              : '$_committedText $text';
          _transcriptController?.add(SttSegment(
            text: fullText,
            isFinal: false,
          ));
        }
      }
    } catch (e) {
      // Non-JSON message — ignore
    }
  }

  String _deduplicateAgainstPrev(String finalText, String prevPartial) {
    if (prevPartial.isEmpty) return finalText;
    if (finalText == prevPartial) return finalText;
    // Simple: if final starts with what we already committed, return as-is
    return finalText;
  }

  /// Stops recording and closes the WebSocket.
  Future<void> stop() async {
    await _audioSubscription?.cancel();
    _audioSubscription = null;

    try {
      await _recorder.stop();
    } catch (_) {}

    // Send end-of-stream signal
    try {
      _channel?.sink.add(jsonEncode({"eos": true}));
    } catch (_) {}

    // Brief delay for final transcript
    await Future.delayed(const Duration(milliseconds: 500));

    await _wsSubscription?.cancel();
    _wsSubscription = null;

    await _channel?.sink.close();
    _channel = null;

    _transcriptController?.close();
    _transcriptController = null;
  }

  /// Defensively releases all resources.
  void dispose() {
    _audioSubscription?.cancel();
    _wsSubscription?.cancel();
    _channel?.sink.close();
    _transcriptController?.close();
    _recorder.dispose();

    _audioSubscription = null;
    _wsSubscription = null;
    _channel = null;
    _transcriptController = null;
    _committedText = '';
    _currentWindowText = '';
    _prevRawPartial = '';
  }
}

/// Exception thrown by the streaming STT service.
class StreamingSttException implements Exception {
  final String message;
  const StreamingSttException(this.message);
  @override
  String toString() => 'StreamingSttException: $message';
}
```

**Step 4: Commit**

```bash
git add lib/core/services/stt_service.dart lib/core/services/stt_service_stub.dart lib/core/services/stt_service_native.dart
git commit -m "feat: add cross-platform STT service with conditional imports"
```

---

### Task 6: Flutter — Abstract file picker service with conditional imports

**Files:**
- Create: `newsflow/lib/core/services/file_picker_service.dart` (barrel)
- Create: `newsflow/lib/core/services/file_picker_service_stub.dart`
- Create: `newsflow/lib/core/services/file_picker_service_native.dart`
- Keep: `newsflow/lib/core/services/ocr_service_web.dart` (web impl, rename export classes)

**Step 1: Create stub**

Create `newsflow/lib/core/services/file_picker_service_stub.dart`:

```dart
/// Stub — conditional imports pick the real implementation.

enum MediaType { photo, video, audio, document }

class FilePickResult {
  final String dataUrl;
  final String fileName;
  const FilePickResult({required this.dataUrl, required this.fileName});
}

class OcrResult {
  final String text;
  final String imageDataUrl;
  const OcrResult({required this.text, required this.imageDataUrl});
}

class OcrException implements Exception {
  final String message;
  const OcrException(this.message);
  @override
  String toString() => 'OcrException: $message';
}

class OcrService {
  Future<FilePickResult?> pickFile(MediaType type) =>
      throw UnsupportedError('No file picker on this platform');

  Future<OcrResult?> pickAndRecognize({void Function(double)? onProgress}) =>
      throw UnsupportedError('No file picker on this platform');
}
```

**Step 2: Create native implementation**

Create `newsflow/lib/core/services/file_picker_service_native.dart`:

```dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart' as fp;
import 'package:image_picker/image_picker.dart';

// Re-export types that consumers need
enum MediaType { photo, video, audio, document }

class FilePickResult {
  final String dataUrl;
  final String fileName;
  const FilePickResult({required this.dataUrl, required this.fileName});
}

class OcrResult {
  final String text;
  final String imageDataUrl;
  const OcrResult({required this.text, required this.imageDataUrl});
}

class OcrException implements Exception {
  final String message;
  const OcrException(this.message);
  @override
  String toString() => 'OcrException: $message';
}

/// Native file/media picker using image_picker and file_picker packages.
class OcrService {
  final ImagePicker _imagePicker = ImagePicker();

  Future<FilePickResult?> pickFile(MediaType type) async {
    switch (type) {
      case MediaType.photo:
        return _pickImage();
      case MediaType.video:
        return _pickVideo();
      case MediaType.audio:
        return _pickGeneric(['mp3', 'wav', 'aac', 'm4a', 'ogg']);
      case MediaType.document:
        return _pickGeneric(['pdf', 'doc', 'docx', 'txt', 'odt', 'rtf']);
    }
  }

  Future<FilePickResult?> _pickImage() async {
    final xfile = await _imagePicker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
    );
    if (xfile == null) return null;
    return _xfileToResult(xfile);
  }

  Future<FilePickResult?> _pickVideo() async {
    final xfile = await _imagePicker.pickVideo(source: ImageSource.gallery);
    if (xfile == null) return null;
    return _xfileToResult(xfile);
  }

  Future<FilePickResult?> _pickGeneric(List<String> extensions) async {
    final result = await fp.FilePicker.platform.pickFiles(
      type: fp.FileType.custom,
      allowedExtensions: extensions,
    );
    if (result == null || result.files.isEmpty) return null;
    final file = result.files.first;
    if (file.path == null) return null;

    final bytes = await File(file.path!).readAsBytes();
    final mime = _guessMime(file.name);
    final dataUrl = 'data:$mime;base64,${base64Encode(bytes)}';
    return FilePickResult(dataUrl: dataUrl, fileName: file.name);
  }

  Future<FilePickResult?> _xfileToResult(XFile xfile) async {
    final bytes = await xfile.readAsBytes();
    final mime = _guessMime(xfile.name);
    final dataUrl = 'data:$mime;base64,${base64Encode(bytes)}';
    return FilePickResult(dataUrl: dataUrl, fileName: xfile.name);
  }

  String _guessMime(String name) {
    final ext = name.split('.').last.toLowerCase();
    const mimes = {
      'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
      'gif': 'image/gif', 'webp': 'image/webp',
      'mp4': 'video/mp4', 'mov': 'video/quicktime',
      'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'aac': 'audio/aac',
      'pdf': 'application/pdf', 'doc': 'application/msword',
      'txt': 'text/plain',
    };
    return mimes[ext] ?? 'application/octet-stream';
  }

  Future<OcrResult?> pickAndRecognize({void Function(double)? onProgress}) async {
    final result = await pickFile(MediaType.photo);
    if (result == null) return null;
    return OcrResult(text: '', imageDataUrl: result.dataUrl);
  }
}
```

**Step 3: Create barrel with conditional imports**

Create `newsflow/lib/core/services/file_picker_service.dart`:

```dart
export 'file_picker_service_stub.dart'
    if (dart.library.html) 'ocr_service_web.dart'
    if (dart.library.io) 'file_picker_service_native.dart';
```

**Step 4: Move MediaType out of create_news_provider**

The `MediaType` enum is currently defined inside `create_news_provider.dart` and imported by `ocr_service_web.dart`. This creates a circular dependency. Move it to the stub/native files (already done above — each file defines its own `MediaType`). Update `ocr_service_web.dart` to define `MediaType` locally instead of importing from provider.

In `newsflow/lib/core/services/ocr_service_web.dart`, replace line 6:
```dart
// REMOVE: import '../../features/create_news/providers/create_news_provider.dart' show MediaType;

// ADD at top of file:
enum MediaType { photo, video, audio, document }
```

And remove the `MediaType` enum from `create_news_provider.dart` (it will be imported from the file picker service barrel instead).

**Step 5: Commit**

```bash
git add lib/core/services/file_picker_service.dart lib/core/services/file_picker_service_stub.dart lib/core/services/file_picker_service_native.dart lib/core/services/ocr_service_web.dart
git commit -m "feat: add cross-platform file picker with conditional imports"
```

---

### Task 7: Flutter — Rewrite sarvam_api.dart to call backend instead of Sarvam directly

**Files:**
- Modify: `newsflow/lib/core/services/sarvam_api.dart:1-220`
- Modify: `newsflow/lib/core/services/sarvam_config.dart:1-51`

**Step 1: Strip API key and direct URL from sarvam_config.dart**

Rewrite `newsflow/lib/core/services/sarvam_config.dart`:

```dart
/// Configuration for Sarvam AI models and language codes.
/// API key is NOT stored here — it lives on the backend.
class SarvamConfig {
  SarvamConfig._();

  // Default models
  static const String sttModel = 'saaras:v3';
  static const String ttsModel = 'bulbul:v3';
  static const String translateModel = 'sarvam-translate:v1';
  static const String chatModel = 'sarvam-m';

  // Language codes
  static const String odiaCode = 'od-IN';
  static const String englishCode = 'en-IN';
  static const String hindiCode = 'hi-IN';
}
```

**Step 2: Rewrite SarvamApiService to proxy through backend**

In `newsflow/lib/core/services/sarvam_api.dart`, replace the `SarvamApiService` class (lines 206-445). Keep all model classes (lines 1-193) unchanged. Replace the service class:

```dart
/// Client that proxies Sarvam AI calls through the backend.
/// No API keys on the client — the backend holds the key.
class SarvamApiService {
  late final Dio _dio;

  SarvamApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
  }

  /// Set the JWT token for authenticated requests.
  void setToken(String? token) {
    if (token != null) {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    } else {
      _dio.options.headers.remove('Authorization');
    }
  }

  /// Sends chat messages to the backend LLM proxy.
  Future<ChatResponse> chat({
    required List<ChatMessage> messages,
    String model = SarvamConfig.chatModel,
    double? temperature,
    int? maxTokens,
  }) async {
    try {
      final body = <String, dynamic>{
        'model': model,
        'messages': messages.map((m) => m.toJson()).toList(),
        if (temperature != null) 'temperature': temperature,
        if (maxTokens != null) 'max_tokens': maxTokens,
      };

      final response = await _dio.post<Map<String, dynamic>>(
        '/api/llm/chat',
        data: body,
        options: Options(contentType: 'application/json'),
      );

      return ChatResponse.fromJson(response.data!);
    } on DioException catch (e) {
      throw _handleDioError(e, 'Chat');
    } catch (e) {
      throw SarvamApiException(message: 'Chat request failed: $e');
    }
  }

  SarvamApiException _handleDioError(DioException e, String operation) {
    final statusCode = e.response?.statusCode;
    final responseData = e.response?.data;

    String message;
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        message = '$operation request timed out.';
      case DioExceptionType.connectionError:
        message = 'Unable to connect to server.';
      case DioExceptionType.badResponse:
        final serverMsg = responseData is Map ? responseData['detail'] : null;
        message = '$operation failed (${statusCode ?? '?'}): ${serverMsg ?? 'Unknown error'}';
      default:
        message = '$operation request failed: ${e.message}';
    }

    return SarvamApiException(
      message: message,
      statusCode: statusCode,
      responseData: responseData,
    );
  }
}
```

Also add import for `api_config.dart` at the top of the file and update the provider to accept a token setter. The provider initialization will need to wire up the auth token — this happens in Task 8.

**Step 3: Commit**

```bash
git add lib/core/services/sarvam_config.dart lib/core/services/sarvam_api.dart
git commit -m "feat: rewrite sarvam_api to proxy through backend, remove API key from client"
```

---

### Task 8: Flutter — Update provider imports and wire auth token

**Files:**
- Modify: `newsflow/lib/features/create_news/providers/create_news_provider.dart:1-9`
- Modify: `newsflow/lib/features/create_news/providers/create_news_provider.dart` (MediaType, StreamingSttService references)

**Step 1: Update imports in create_news_provider.dart**

Replace the web-specific imports (lines 7-9):

```dart
// BEFORE:
import '../../../core/services/ocr_service_web.dart';
import '../../../core/services/sarvam_api.dart';
import '../../../core/services/streaming_stt_web.dart';

// AFTER:
import '../../../core/services/file_picker_service.dart';
import '../../../core/services/sarvam_api.dart';
import '../../../core/services/stt_service.dart';
```

**Step 2: Remove MediaType enum from provider**

The `MediaType` enum should now come from the file picker service barrel. Find and remove the `enum MediaType { ... }` definition from `create_news_provider.dart`.

**Step 3: Wire auth token to SarvamApiService**

In the `NotepadNotifier.build()` or `init()` method, set the JWT token on the SarvamApiService so it can authenticate with the backend. Find where `_sarvam` is accessed and ensure the token is set:

```dart
// In NotepadNotifier, where _sarvam is used:
SarvamApiService get _sarvam {
  final sarvam = ref.read(sarvamApiProvider);
  // Ensure auth token is set from the API service
  final apiService = ref.read(apiServiceProvider);
  // Token is already managed by apiService — we need to share it
  return sarvam;
}
```

The cleanest approach: update the `sarvamApiProvider` to read the token from shared state. Or have the SarvamApiService share the Dio instance with ApiService. Pick the simplest: make `sarvamApiProvider` a family that accepts a token, or just set the token in the notifier's `build()`.

**Step 4: Wire auth token for native STT**

In `NotepadNotifier`, when creating `StreamingSttService`, set the auth token:

```dart
_streamingStt = StreamingSttService();
// On native, the service needs the auth token for the backend WebSocket
// The web impl ignores this property (connects directly to Sarvam)
if (_streamingStt is StreamingSttService) {
  // authToken is a field on the native impl, doesn't exist on web
  // Use a try/catch or conditional to handle this
}
```

The cleanest approach: add an `authToken` setter to the stub and web impl that's a no-op, so the provider can always call it.

**Step 5: Commit**

```bash
git add lib/features/create_news/providers/create_news_provider.dart
git commit -m "feat: update provider to use cross-platform service imports"
```

---

### Task 9: Flutter — iOS permissions and build verification

**Files:**
- Modify: `newsflow/ios/Runner/Info.plist`

**Step 1: Add microphone permission to Info.plist**

Add these keys inside the `<dict>` in `ios/Runner/Info.plist`:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Microphone access is needed for voice dictation of news stories</string>
<key>NSSpeechRecognitionUsageDescription</key>
<string>Speech recognition is used for transcribing news stories</string>
```

**Step 2: Build for iOS**

Run: `cd newsflow && flutter build ios --simulator --no-tree-shake-icons`
Expected: Build succeeds with zero web-only import errors.

**Step 3: Run on simulator**

Run: `flutter run -d <iPhone-17-Pro-ID>`
Expected: App launches, navigation works.

**Step 4: Commit**

```bash
git add ios/Runner/Info.plist
git commit -m "feat: add iOS microphone permissions for native STT"
```

---

### Task 10: Integration test — end-to-end STT on iOS simulator

**Step 1: Start the backend**

Run: `cd newsflow-api && uvicorn app.main:app --reload --port 8000`

**Step 2: Verify ApiConfig.baseUrl**

Ensure `newsflow/lib/core/services/api_config.dart` points to the Mac's IP (not localhost, since the simulator can't reach host localhost):

```dart
class ApiConfig {
  ApiConfig._();
  static const String baseUrl = 'http://127.0.0.1:8000'; // or Mac's local IP
}
```

Note: iOS simulator CAN reach `127.0.0.1` / `localhost` on the host machine. Android emulator requires `10.0.2.2`.

**Step 3: Test the full flow**

1. Open app on iOS simulator
2. Log in (OTP flow)
3. Create new story
4. Tap record button
5. Speak in Odia
6. Verify real-time transcript appears
7. Stop recording
8. Tap a paragraph → verify action chips work (move up/down, AI improve, delete)

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: cross-platform backend proxy — iOS/Android ready"
```
