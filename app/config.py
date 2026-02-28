from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — defaults to SQLite for local dev, set to PostgreSQL in production
    DATABASE_URL: str = "sqlite:///./newsflow.db"

    # Auth
    SECRET_KEY: str = "newsflow-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 90

    # CORS — comma-separated origins, "*" for dev
    CORS_ORIGINS: str = "*"

    # Firebase
    FIREBASE_PROJECT_ID: str = "vrittant-f5ef2"

    # External APIs
    SARVAM_API_KEY: str = ""
    SARVAM_BASE_URL: str = "https://api.sarvam.ai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # File storage — "local" or "gcs"
    STORAGE_BACKEND: str = "local"
    GCS_BUCKET: str = ""

    # Legacy — kept for backward compat, not used with Firebase auth
    HARDCODED_OTP: str = "123456"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
