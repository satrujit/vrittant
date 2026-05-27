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

    # Speech-to-text provider — "sarvam" (default) or "gemini". Switching
    # to "gemini" routes services/stt.py.transcribe_audio to the Gemini
    # 2.5 Flash audio-input path (see services/gemini_stt.py). Sarvam
    # remains the default until offline eval shows Gemini's Odia
    # accuracy is acceptable. Cost ratio at current rates: Sarvam saaras
    # ~₹0.25 / 30s vs Gemini Flash ~₹0.08 / 30s — 3× cheaper, larger if
    # we move to Flash-Lite.
    STT_PROVIDER: str = "sarvam"
    # Default Gemini STT model when STT_PROVIDER=gemini. Override per
    # call site if needed; "gemini-2.5-flash-lite" is cheaper but
    # weaker on Indic audio.
    STT_GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    # Live-dictation silence gate. RMS (root-mean-square) is computed
    # per audio chunk; chunks below this energy threshold are dropped
    # before reaching Gemini — saves API spend AND structurally
    # prevents silent-audio hallucinations. Typical real-world values:
    #   true silence (mic muted)   : RMS ~0-10
    #   quiet room ambient noise   : RMS ~30-100
    #   AC/fan hum                 : RMS ~80-200
    #   quiet speech               : RMS ~300-800
    #   normal speech              : RMS ~500-3000
    # Default 200 catches most ambient noise while leaving even fairly
    # quiet speech comfortably above the bar. Tune with care — too high
    # drops real speech, too low lets noise hallucinate. Override per
    # deployment via env var.
    STT_SILENCE_RMS_THRESHOLD: int = 200
    # Dual-run mode: when True, every STT call invokes BOTH providers
    # in parallel, returns the primary (per STT_PROVIDER), and writes
    # the secondary's transcript + duration + cost into
    # sarvam_usage_log under service="stt_shadow_<other>". Use during
    # the rollout window to compare quality side-by-side. Doubles the
    # spend per call — turn off once you've decided.
    STT_DUAL_LOG: bool = False

    # MSG91 SendOTP
    MSG91_AUTHKEY: str = ""
    MSG91_TEMPLATE_ID: str = ""

    # Gupshup webhook HMAC-SHA256 shared secret. When set, every inbound
    # /webhooks/whatsapp/gupshup request must carry a matching signature
    # header — anything else is rejected as 403 (an unauthenticated caller
    # can't spoof reporter phone numbers, can't trigger outbound replies
    # to arbitrary destinations, and can't reach the media-fetch SSRF
    # surface). When EMPTY, signature verification is skipped — useful
    # during initial rollout (deploy code → configure secret on Gupshup
    # dashboard → set this env var) and during local/test runs. A startup
    # log line warns loudly when verification is off in prod.
    GUPSHUP_WEBHOOK_SECRET: str = ""

    # Sentry error tracking — empty DSN disables Sentry cleanly (dev/local).
    # Set to the full DSN URL in production: https://<key>@o<org>.ingest.sentry.io/<project>
    SENTRY_DSN: str = ""

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

    # Master flag for the WhatsApp self-service path (interactive buttons,
    # universal media buffer, today's-stories, add-to-existing-story).
    # When False, /webhooks/whatsapp/* uses the legacy ingest. Flip to True
    # only after the dispatcher handlers (Tasks 12-16) are all implemented
    # and UAT smoke-tested. Reversible: setting back to False routes traffic
    # to the legacy path again, no DB rollback needed.
    WHATSAPP_SELF_SERVICE_ENABLED: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
