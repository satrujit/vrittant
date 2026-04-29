from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — defaults to SQLite for local dev, set to PostgreSQL in production
    DATABASE_URL: str = "sqlite:///./newsflow.db"

    # Environment — "dev" or "prod"
    ENV: str = "dev"

    # Auth
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 90

    # CORS — comma-separated origins, "*" for dev
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5175"

    # Firebase
    FIREBASE_PROJECT_ID: str = "vrittant-f5ef2"

    # External APIs
    SARVAM_API_KEY: str = ""
    SARVAM_BASE_URL: str = "https://api.sarvam.ai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Anthropic — used for /api/llm/generate-story (Haiku 4.5). The Sarvam
    # backend stays primary for everything else; Anthropic was added because
    # an A/B run on the generateStory prompt showed Haiku is faithful, fast,
    # and obeys formatting rules where Sarvam-30b hallucinates and corrupts
    # numeral scripts. See docs/ai-model-routing.md (TODO if we add more
    # routing decisions). Empty key = endpoint falls back to Sarvam-only.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # Gemini (Google AI Studio API). Created in vrittant-f5ef2 GCP
    # project so billing flows back to the same Cloud bill we're already
    # paying. Calls go to ``generativelanguage.googleapis.com`` directly
    # (no Vertex AI auth dance). Empty key = endpoints that have an
    # Anthropic/Sarvam fallback continue to work via the legacy path;
    # Gemini-only call sites (most of them after the migration) error
    # cleanly with a 503.
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    # Default model for chat / translate. Flash-Lite is ~3-4× cheaper
    # than Flash and quality has tested OK for Odia journalism. Override
    # per-call site (e.g. story generation can pass the heavier Flash
    # model) when needed.
    GEMINI_DEFAULT_MODEL: str = "gemini-2.5-flash-lite"

    # OTP provider — "twilio" (default) or "msg91". Switch via env without code changes.
    OTP_PROVIDER: str = "twilio"

    # MSG91 OTP (kept for web widget login — verifyAccessToken — and as a SMS fallback)
    MSG91_AUTHKEY: str = ""
    MSG91_TEMPLATE_ID: str = ""
    MSG91_WIDGET_ID: str = ""
    MSG91_TOKEN_AUTH: str = ""

    # Twilio Verify (mobile OTP)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_VERIFY_SERVICE_SID: str = ""

    # File storage — "local" or "gcs"
    STORAGE_BACKEND: str = "local"
    GCS_BUCKET: str = ""

    # Shared secret for /internal/* endpoints. Set in Cloud Run; Cloud
    # Scheduler jobs send it via the X-Internal-Token header. Empty by
    # default so dev environments without it fall back to "any caller wins"
    # (you don't want to ship a real value here).
    INTERNAL_TOKEN: str = ""

    # Inbound email parsing (SendGrid Inbound Parse → /internal/email/inbound).
    # The local part of the To: address selects the org; the domain part
    # must match this setting exactly. Production MX is set on the
    # desk.vrittant.in subdomain (apex stays on Mailer91 for MSG91), so
    # reporters mail pragativadi@desk.vrittant.in, sambad@desk.vrittant.in,
    # etc.
    INBOUND_EMAIL_DOMAIN: str = "desk.vrittant.in"

    # ── Mobile force-update gate ─────────────────────────────────────────
    # The mobile app fetches /version/min-supported on cold start. If its
    # current version is below `min`, the app blocks with an "Update required"
    # screen. Bumping these env vars rolls out a forced update to all
    # installed clients without an app rebuild.
    #
    # `latest` is informational ("there's a newer version available, here's
    # the link") — non-blocking. Use it for soft prompts.
    #
    # Use semver (MAJOR.MINOR.PATCH). Empty string disables the gate for
    # that platform, which is the default so dev/UAT never accidentally
    # forces upgrades.
    MIN_VERSION_IOS: str = ""
    MIN_VERSION_ANDROID: str = ""
    LATEST_VERSION_IOS: str = ""
    LATEST_VERSION_ANDROID: str = ""

    # Store URLs returned to the client so the "Update Now" button can deep-
    # link out. Provided by config (not hardcoded in the app) because the
    # iOS App Store ID is not known until first TestFlight build, and we
    # don't want to ship a follow-up release just to fix a broken link.
    APP_STORE_URL_IOS: str = ""
    APP_STORE_URL_ANDROID: str = (
        "https://play.google.com/store/apps/details?id=com.attentionstack.vrittant"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
