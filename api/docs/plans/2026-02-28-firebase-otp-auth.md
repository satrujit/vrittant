# Firebase OTP Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hardcoded OTP ("123456") with real Firebase Phone Authentication across backend (FastAPI), reviewer panel (React), and reporter app (Flutter).

**Architecture:** Client-side Firebase SDK handles phone verification (SMS OTP). After Firebase auth, client sends Firebase ID token to a new backend endpoint (`POST /auth/firebase-login`). Backend verifies the token with Firebase Admin SDK, looks up user by phone number, and issues its own JWT. No auto-registration — users must be pre-registered in the database.

**Tech Stack:** Firebase Auth (Phone provider), firebase-admin (Python), firebase JS SDK (React), firebase_core + firebase_auth (Flutter), FastAPI, SQLAlchemy

---

## Firebase Project Details

- **Project:** Vrittant
- **Project ID:** `vrittant-f5ef2`
- **Android Package:** `com.newsflow.newsflow`
- **Web App ID:** `1:829303072442:web:47650a98e93a9fbfc04483`

## Auth Flow

```
┌──────────────────────────────────────────────────────────────┐
│  Client (Flutter / React)                                     │
│                                                               │
│  1. User enters phone number                                  │
│  2. Firebase SDK → verifyPhoneNumber() / signInWithPhoneNumber│
│  3. User enters SMS OTP code                                  │
│  4. Firebase SDK verifies → gets Firebase ID token             │
│  5. POST /auth/firebase-login { firebase_token: "..." }       │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                            │
│                                                               │
│  6. firebase_admin.auth.verify_id_token(token)                │
│  7. Extract phone_number from decoded token                   │
│  8. Look up User by phone — 404 if not registered             │
│  9. Issue backend JWT (same as current system)                 │
│  10. Return { access_token, token_type }                      │
└──────────────────────────────────────────────────────────────┘
```

---

## Task 1: Backend — Firebase Admin SDK Setup

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/requirements.txt`
- Modify: `/Users/admin/Desktop/newsflow-api/app/config.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/firebase_admin_setup.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/main.py`

**Step 1: Add firebase-admin to requirements.txt**

Add `firebase-admin==6.6.0` to the end of requirements.txt.

**Step 2: Install dependencies**

Run: `cd /Users/admin/Desktop/newsflow-api && pip install firebase-admin==6.6.0`

**Step 3: Add FIREBASE_PROJECT_ID to config.py**

Add to Settings class in `app/config.py`:
```python
FIREBASE_PROJECT_ID: str = "vrittant-f5ef2"
```

**Step 4: Create firebase_admin_setup.py**

```python
"""
Firebase Admin SDK initialization.
Uses Application Default Credentials when available (production),
falls back to project-ID-only init for ID token verification (development).
"""
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

from .config import settings


def init_firebase():
    """Initialize Firebase Admin SDK. Safe to call multiple times."""
    if firebase_admin._apps:
        return  # already initialized

    try:
        # Try ADC (works on GCP / with GOOGLE_APPLICATION_CREDENTIALS env var)
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            "projectId": settings.FIREBASE_PROJECT_ID,
        })
    except Exception:
        # Fallback: initialize with just project ID (sufficient for verify_id_token)
        firebase_admin.initialize_app(options={
            "projectId": settings.FIREBASE_PROJECT_ID,
        })


def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.
    Raises firebase_admin.auth.InvalidIdTokenError on failure.
    """
    return firebase_auth.verify_id_token(id_token)
```

**Step 5: Initialize Firebase in main.py**

Add after line 12 (`Base.metadata.create_all(bind=engine)`) in `app/main.py`:
```python
from .firebase_admin_setup import init_firebase
init_firebase()
```

**Step 6: Commit**

```bash
git add requirements.txt app/config.py app/firebase_admin_setup.py app/main.py
git commit -m "feat(auth): add Firebase Admin SDK setup for ID token verification"
```

---

## Task 2: Backend — New Firebase Login Endpoint

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/schemas/auth.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/auth.py`

**Step 1: Add FirebaseLoginRequest schema**

Add to `app/schemas/auth.py` after `OTPVerify` class:

```python
class FirebaseLoginRequest(BaseModel):
    firebase_token: str
```

**Step 2: Add firebase-login endpoint**

Add to `app/routers/auth.py`:

```python
from ..firebase_admin_setup import verify_firebase_token
from ..schemas.auth import FirebaseLoginRequest  # add to existing import
```

Then add endpoint after the existing `verify_otp` endpoint:

```python
@router.post("/firebase-login", response_model=Token)
def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    Verify a Firebase ID token and issue a backend JWT.
    The user must already exist in the database (no auto-registration).
    """
    try:
        decoded = verify_firebase_token(body.firebase_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
        )

    # Firebase phone auth puts the phone in the token claims
    phone = decoded.get("phone_number")
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a phone number",
        )

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered. Contact admin for access.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)
```

**Step 3: Verify backend starts**

Run: `cd /Users/admin/Desktop/newsflow-api && python -c "from app.main import app; print('OK')"`

**Step 4: Commit**

```bash
git add app/schemas/auth.py app/routers/auth.py
git commit -m "feat(auth): add POST /auth/firebase-login endpoint"
```

---

## Task 3: React — Firebase SDK Setup

**Files:**
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/services/firebase.js`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/package.json` (via npm install)

**Step 1: Install Firebase JS SDK**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npm install firebase`

**Step 2: Create firebase.js config**

```javascript
import { initializeApp } from 'firebase/app';
import { getAuth, RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "AIzaSyAF4icr8tWg9QYIBqncegivtcohX1y2XAc",
  authDomain: "vrittant-f5ef2.firebaseapp.com",
  projectId: "vrittant-f5ef2",
  storageBucket: "vrittant-f5ef2.firebasestorage.app",
  messagingSenderId: "829303072442",
  appId: "1:829303072442:web:47650a98e93a9fbfc04483",
  measurementId: "G-JZHPF2D9T1",
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

export { auth, RecaptchaVerifier, signInWithPhoneNumber };
```

**Step 3: Commit**

```bash
git add package.json package-lock.json src/services/firebase.js
git commit -m "feat(auth): add Firebase JS SDK and config for reviewer panel"
```

---

## Task 4: React — Rewrite LoginPage for Firebase OTP

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/services/api.js`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/LoginPage.jsx`

**Step 1: Add firebaseLogin API function**

Add to `api.js` in the Auth API section (after verifyOTP):

```javascript
export async function firebaseLogin(firebaseToken) {
  return apiFetch('/auth/firebase-login', {
    method: 'POST',
    body: JSON.stringify({ firebase_token: firebaseToken }),
  });
}
```

**Step 2: Rewrite LoginPage.jsx**

The login flow changes to:
1. **Phone step**: User enters phone → Firebase `signInWithPhoneNumber()` sends real SMS
2. **OTP step**: User enters OTP → Firebase `confirmationResult.confirm(otp)` verifies with Firebase
3. **Backend exchange**: Get Firebase ID token → `POST /auth/firebase-login` → get backend JWT
4. **Session**: `login(backendJWT)` → navigate to dashboard

Key changes:
- Import `auth, RecaptchaVerifier, signInWithPhoneNumber` from `../services/firebase`
- Import `firebaseLogin` from `../services/api` (instead of requestOTP/verifyOTP)
- Add `confirmationRef` state to hold Firebase's ConfirmationResult
- `handleSendOTP`: create invisible reCAPTCHA, call `signInWithPhoneNumber(auth, phone, recaptcha)`
- `handleVerifyOTP`: call `confirmationRef.confirm(otp)`, get `user.getIdToken()`, call `firebaseLogin(idToken)`, then `login(backendJWT)`
- Add a `<div id="recaptcha-container" />` in the JSX for the invisible reCAPTCHA widget

**Step 3: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`

**Step 4: Commit**

```bash
git add src/pages/LoginPage.jsx src/services/api.js
git commit -m "feat(auth): rewrite reviewer panel login to use Firebase Phone Auth"
```

---

## Task 5: Flutter — Firebase Core + Auth Setup

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/pubspec.yaml`
- Create: `/Users/admin/Desktop/newsflow/lib/firebase_options.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/main.dart`

**Step 1: Add Firebase dependencies to pubspec.yaml**

Add under `dependencies:` section:
```yaml
  firebase_core: ^3.12.1
  firebase_auth: ^5.5.1
```

**Step 2: Run flutter pub get**

Run: `cd /Users/admin/Desktop/newsflow && flutter pub get`

**Step 3: Create firebase_options.dart**

This file is normally generated by `flutterfire configure` but we'll create it manually from the known config:

```dart
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform, kIsWeb;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) return web;
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError('Unsupported platform');
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyAF4icr8tWg9QYIBqncegivtcohX1y2XAc',
    appId: '1:829303072442:web:47650a98e93a9fbfc04483',
    messagingSenderId: '829303072442',
    projectId: 'vrittant-f5ef2',
    authDomain: 'vrittant-f5ef2.firebaseapp.com',
    storageBucket: 'vrittant-f5ef2.firebasestorage.app',
    measurementId: 'G-JZHPF2D9T1',
  );

  // Android — requires google-services.json from Firebase Console
  // Run: flutterfire configure --project=vrittant-f5ef2 to auto-generate
  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyAF4icr8tWg9QYIBqncegivtcohX1y2XAc',
    appId: '1:829303072442:web:47650a98e93a9fbfc04483',  // placeholder — update after flutterfire configure
    messagingSenderId: '829303072442',
    projectId: 'vrittant-f5ef2',
    storageBucket: 'vrittant-f5ef2.firebasestorage.app',
  );

  // iOS — requires GoogleService-Info.plist from Firebase Console
  // Run: flutterfire configure --project=vrittant-f5ef2 to auto-generate
  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyAF4icr8tWg9QYIBqncegivtcohX1y2XAc',
    appId: '1:829303072442:web:47650a98e93a9fbfc04483',  // placeholder — update after flutterfire configure
    messagingSenderId: '829303072442',
    projectId: 'vrittant-f5ef2',
    storageBucket: 'vrittant-f5ef2.firebasestorage.app',
    iosBundleId: 'com.newsflow.newsflow',
  );
}
```

> **NOTE:** The Android and iOS options use placeholder appIds from the web config. These MUST be updated after running `flutterfire configure` which registers the native apps in Firebase and generates the correct appIds + downloads google-services.json / GoogleService-Info.plist. For development/testing with the web target, this works as-is.

**Step 4: Update main.dart to initialize Firebase**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';
import 'app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const ProviderScope(child: NewsFlowApp()));
}
```

**Step 5: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/firebase_options.dart lib/main.dart
git commit -m "feat(auth): add Firebase Core + Auth dependencies and config for Flutter"
```

---

## Task 6: Flutter — Rewrite Auth Provider + Login Screen for Firebase

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/services/api_service.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/features/auth/providers/auth_provider.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/features/auth/screens/login_screen.dart`

**Step 1: Add firebaseLogin method to ApiService**

Add to `api_service.dart` in the Auth section (after `verifyOtp`):

```dart
/// Exchange a Firebase ID token for a backend JWT.
Future<({String token, ReporterProfile reporter})> firebaseLogin(
    String firebaseToken) async {
  final res = await _dio.post(
    '/auth/firebase-login',
    data: {'firebase_token': firebaseToken},
  );
  final token = res.data['access_token'] as String;
  _token = token;

  final meRes = await _dio.get('/auth/me');
  final reporter =
      ReporterProfile.fromJson(meRes.data as Map<String, dynamic>);
  return (token: token, reporter: reporter);
}
```

**Step 2: Rewrite auth_provider.dart**

Replace `requestOtp` and `verifyOtp` methods with Firebase-based flow:

- Import `firebase_auth` package
- `requestOtp(phone)` → calls `FirebaseAuth.instance.verifyPhoneNumber()` with callbacks
- Store `verificationId` in state for later use
- `verifyOtp(phone, otp)` → create `PhoneAuthCredential` from verificationId + otp, sign in with Firebase, get ID token, call `_api.firebaseLogin(idToken)`
- Add `verificationId` field to AuthState
- Keep `tryAutoLogin()` and `logout()` as-is (they use backend JWT)
- Add `FirebaseAuth.instance.signOut()` to `logout()`

**Step 3: Update login_screen.dart**

Minimal changes needed since the UI stays the same — it's still phone input → OTP input. The underlying calls to `notifier.requestOtp()` and `notifier.verifyOtp()` are unchanged from the screen's perspective. Only the auth_provider internals change.

Remove the old unused `_otpController` single controller since we use `_otpControllers` array.

**Step 4: Verify Flutter build**

Run: `cd /Users/admin/Desktop/newsflow && flutter build apk --debug 2>&1 | tail -5`
(Or `flutter analyze` for a quick syntax check)

**Step 5: Commit**

```bash
git add lib/core/services/api_service.dart lib/features/auth/providers/auth_provider.dart lib/features/auth/screens/login_screen.dart
git commit -m "feat(auth): rewrite Flutter auth to use Firebase Phone Auth"
```

---

## Task 7: Enable Phone Auth in Firebase Console

**Manual step** (cannot be automated):

1. Go to https://console.firebase.google.com/project/vrittant-f5ef2/authentication
2. Click "Get started" if not already enabled
3. Go to "Sign-in method" tab
4. Enable "Phone" provider
5. (Optional) Add test phone numbers for development:
   - Phone: `+919876543210` → OTP: `123456`
   - Phone: `+919999999999` → OTP: `123456`

> **Test phone numbers** allow Firebase to bypass real SMS during development. The OTP is deterministic (you choose it), so existing dev workflow stays the same.

---

## Task 8: Verification

**Step 1: Backend health check**

Run: `cd /Users/admin/Desktop/newsflow-api && python -c "from app.main import app; print('Backend OK')"`

**Step 2: React build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds with 0 errors

**Step 3: Flutter analyze**

Run: `cd /Users/admin/Desktop/newsflow && flutter analyze`
Expected: No errors (warnings OK)

**Step 4: Manual testing checklist**

- [ ] Firebase Console: Phone auth enabled
- [ ] Firebase Console: Test phone numbers added (optional)
- [ ] Backend: `POST /auth/firebase-login` returns 401 for invalid token
- [ ] Backend: `POST /auth/firebase-login` returns JWT for valid token + registered phone
- [ ] Backend: `POST /auth/firebase-login` returns 404 for valid token + unregistered phone
- [ ] React: Login page shows reCAPTCHA, sends SMS, verifies OTP, logs in
- [ ] Flutter: Login screen triggers SMS, verifies OTP, navigates to home
- [ ] Old endpoints (`/auth/request-otp`, `/auth/verify-otp`) still work for backward compat

---

## Key Decisions

1. **Keep old endpoints**: `/auth/request-otp` and `/auth/verify-otp` are NOT removed. They remain for backward compatibility and can be removed later when all clients are updated.
2. **No database migration**: No `firebase_uid` column added to User model. The backend looks up users by phone number (which is already unique and indexed). Firebase UID is not needed since we only use Firebase for OTP verification, not as the identity provider.
3. **No auto-registration**: If a phone number isn't in the database, login fails with 404. Admin must pre-register users.
4. **Invisible reCAPTCHA**: React uses invisible reCAPTCHA (auto-solves for most users). Flutter uses Firebase's built-in SafetyNet/App Check.
5. **Test phone numbers**: Firebase Console supports test phone numbers that bypass real SMS — perfect for development.
