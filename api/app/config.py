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

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
