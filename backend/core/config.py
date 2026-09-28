"""Backend configuration loaded from .env."""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


def _csv_env(name: str, default: str = "") -> list[str]:
    return [
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    ]


class Settings:
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development").strip().lower()
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    CORS_ORIGINS: list[str] = _csv_env(
        "CORS_ORIGINS",
        "http://localhost:8081,http://localhost:19006,http://localhost:3000",
    )

    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = int(
        os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
    )

    JWT_SECRET: str = os.environ["JWT_SECRET"]
    JWT_ALG: str = os.environ.get("JWT_ALG", "HS256")
    JWT_ACCESS_TTL_MIN: int = int(os.environ.get("JWT_ACCESS_TTL_MIN", "60"))
    JWT_REFRESH_TTL_DAYS: int = int(os.environ.get("JWT_REFRESH_TTL_DAYS", "30"))

    APP_PUBLIC_URL: str = os.environ.get("APP_PUBLIC_URL", "http://localhost:8001")

    # Storage
    STORAGE_BACKEND: str = os.environ.get(
        "STORAGE_BACKEND", os.environ.get("S3_BACKEND", "local")
    )
    STUB_STORAGE_DIR: str = os.environ.get("STUB_STORAGE_DIR", "/tmp/shortcut_storage")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "")
    AWS_REGION: str = os.environ.get("AWS_REGION", "ap-south-1")
    S3_ENDPOINT_URL: str = os.environ.get("S3_ENDPOINT_URL", "")

    # Media workers
    FFPROBE_PATH: str = os.environ.get("FFPROBE_PATH", "ffprobe")
    FFMPEG_PATH: str = os.environ.get("FFMPEG_PATH", "ffmpeg")
    MEDIA_PROBE_TIMEOUT_SEC: int = int(os.environ.get("MEDIA_PROBE_TIMEOUT_SEC", "30"))
    MEDIA_DERIVATIVE_TIMEOUT_SEC: int = int(os.environ.get("MEDIA_DERIVATIVE_TIMEOUT_SEC", "180"))
    RENDER_TIMEOUT_SEC: int = int(os.environ.get("RENDER_TIMEOUT_SEC", "900"))
    AUDIO_MASTERING_ENABLED: bool = (
        os.environ.get("AUDIO_MASTERING_ENABLED", "true").lower() == "true"
    )
    AUDIO_TARGET_LUFS: float = float(os.environ.get("AUDIO_TARGET_LUFS", "-14.0"))
    AUDIO_TRUE_PEAK_DBTP: float = float(
        os.environ.get("AUDIO_TRUE_PEAK_DBTP", "-1.5")
    )
    AUDIO_TARGET_LRA: float = float(os.environ.get("AUDIO_TARGET_LRA", "11.0"))
    WORKER_POLL_INTERVAL_SEC: float = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "1.0"))
    JOB_LEASE_SECONDS: int = int(os.environ.get("JOB_LEASE_SECONDS", "1200"))

    # Public-release safety limits
    MAX_UPLOAD_BYTES: int = int(os.environ.get("MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
    MAX_USER_STORAGE_BYTES: int = int(
        os.environ.get("MAX_USER_STORAGE_BYTES", str(10 * 1024 * 1024 * 1024))
    )
    MAX_VIDEO_DURATION_SEC: int = int(os.environ.get("MAX_VIDEO_DURATION_SEC", "3600"))
    MAX_AUDIO_DURATION_SEC: int = int(os.environ.get("MAX_AUDIO_DURATION_SEC", "7200"))
    MAX_ACTIVE_RENDERS_PER_USER: int = int(
        os.environ.get("MAX_ACTIVE_RENDERS_PER_USER", "2")
    )

    AUTH_LOGIN_RATE_LIMIT: int = int(os.environ.get("AUTH_LOGIN_RATE_LIMIT", "10" if ENVIRONMENT == "production" else "10000"))
    AUTH_SIGNUP_RATE_LIMIT: int = int(os.environ.get("AUTH_SIGNUP_RATE_LIMIT", "5" if ENVIRONMENT == "production" else "10000"))
    AUTH_RESET_RATE_LIMIT: int = int(os.environ.get("AUTH_RESET_RATE_LIMIT", "5" if ENVIRONMENT == "production" else "10000"))
    AUTH_RATE_WINDOW_SEC: int = int(os.environ.get("AUTH_RATE_WINDOW_SEC", "3600"))
    AI_PLAN_RATE_LIMIT: int = int(os.environ.get("AI_PLAN_RATE_LIMIT", "20" if ENVIRONMENT == "production" else "10000"))
    ANALYZE_RATE_LIMIT: int = int(os.environ.get("ANALYZE_RATE_LIMIT", "30" if ENVIRONMENT == "production" else "10000"))
    RENDER_RATE_LIMIT: int = int(os.environ.get("RENDER_RATE_LIMIT", "10" if ENVIRONMENT == "production" else "10000"))
    UPLOAD_REQUEST_RATE_LIMIT: int = int(os.environ.get("UPLOAD_REQUEST_RATE_LIMIT", "60" if ENVIRONMENT == "production" else "10000"))
    EXPENSIVE_ACTION_RATE_WINDOW_SEC: int = int(
        os.environ.get("EXPENSIVE_ACTION_RATE_WINDOW_SEC", "3600")
    )
    MEDIA_INTELLIGENCE_TIMEOUT_SEC: int = int(
        os.environ.get("MEDIA_INTELLIGENCE_TIMEOUT_SEC", "900")
    )
    SCENE_DETECTION_THRESHOLD: float = float(
        os.environ.get("SCENE_DETECTION_THRESHOLD", "0.35")
    )
    SILENCE_NOISE_DB: float = float(
        os.environ.get("SILENCE_NOISE_DB", "-35")
    )
    SILENCE_MIN_DURATION_SEC: float = float(
        os.environ.get("SILENCE_MIN_DURATION_SEC", "0.35")
    )
    SILENCE_SNAP_WINDOW_SEC: float = float(
        os.environ.get("SILENCE_SNAP_WINDOW_SEC", "0.75")
    )
    RHYTHM_WINDOW_MS: float = float(
        os.environ.get("RHYTHM_WINDOW_MS", "50")
    )
    RHYTHM_BASELINE_SEC: float = float(
        os.environ.get("RHYTHM_BASELINE_SEC", "0.4")
    )
    RHYTHM_ENERGY_RATIO: float = float(
        os.environ.get("RHYTHM_ENERGY_RATIO", "1.8")
    )
    RHYTHM_MIN_RMS: float = float(
        os.environ.get("RHYTHM_MIN_RMS", "300")
    )
    RHYTHM_MIN_INTERVAL_SEC: float = float(
        os.environ.get("RHYTHM_MIN_INTERVAL_SEC", "0.25")
    )

    # Speech / AI providers
    TRANSCRIPTION_PROVIDER: str = os.environ.get("TRANSCRIPTION_PROVIDER", "openai")
    TRANSCRIPTION_MODEL: str = os.environ.get(
        "TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize"
    )
    VISION_PROVIDER: str = os.environ.get("VISION_PROVIDER", "openai")
    VISION_MODEL: str = os.environ.get("VISION_MODEL", "gpt-4o")
    MAX_VISION_FRAMES: int = int(os.environ.get("MAX_VISION_FRAMES", "8"))
    EMBEDDING_PROVIDER: str = os.environ.get("EMBEDDING_PROVIDER", "openai")
    EMBEDDING_MODEL: str = os.environ.get(
        "EMBEDDING_MODEL", "text-embedding-3-small"
    )
    NARRATIVE_PROVIDER: str = os.environ.get("NARRATIVE_PROVIDER", "deterministic")
    NARRATIVE_MODEL: str = os.environ.get("NARRATIVE_MODEL", "gpt-5-mini")
    AI_PLANNER_TIMEOUT_SEC: int = int(os.environ.get("AI_PLANNER_TIMEOUT_SEC", "120"))
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_API_BASE: str = os.environ.get(
        "OPENAI_API_BASE", "https://api.openai.com/v1"
    )

    # Transactional email for password-reset delivery.
    PASSWORD_RESET_EMAIL_PROVIDER: str = os.environ.get(
        "PASSWORD_RESET_EMAIL_PROVIDER", "disabled"
    ).strip().lower()
    PASSWORD_RESET_URL_TEMPLATE: str = os.environ.get(
        "PASSWORD_RESET_URL_TEMPLATE", ""
    )
    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")
    PASSWORD_RESET_FROM_EMAIL: str = os.environ.get(
        "PASSWORD_RESET_FROM_EMAIL", ""
    )

    GOOGLE_AUTH_ENABLED: bool = (
        os.environ.get("GOOGLE_AUTH_ENABLED", "false").lower() == "true"
    )
    GOOGLE_CLIENT_IDS: list[str] = _csv_env("GOOGLE_CLIENT_IDS")

    STRIPE_PAID_PLANS_ENABLED: bool = (
        os.environ.get("STRIPE_PAID_PLANS_ENABLED", "false").lower() == "true"
    )

    # Incident controls: operators can disable cost-generating/public entry paths
    # without rebuilding the application.
    SIGNUPS_ENABLED: bool = os.environ.get("SIGNUPS_ENABLED", "true").lower() == "true"
    AI_FEATURES_ENABLED: bool = (
        os.environ.get("AI_FEATURES_ENABLED", "true").lower() == "true"
    )
    RENDERS_ENABLED: bool = os.environ.get("RENDERS_ENABLED", "true").lower() == "true"

    # Observability. Sentry is optional for private beta but expected before public launch.
    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "").strip()
    SENTRY_TRACES_SAMPLE_RATE: float = float(
        os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05")
    )
    TERMS_VERSION: str = os.environ.get("TERMS_VERSION", "2026-09-28").strip()

    def validate_runtime(self) -> None:
        if self.ENVIRONMENT not in {"development", "test", "staging", "production"}:
            raise RuntimeError(
                "ENVIRONMENT must be development, test, staging, or production"
            )

        if not self.CORS_ORIGINS:
            raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin")

        if self.ENVIRONMENT == "production":
            weak_secrets = {
                "replace-with-a-long-random-secret",
                "local-development-secret-change-me",
                "changeme",
                "secret",
            }
            if len(self.JWT_SECRET) < 32 or self.JWT_SECRET.lower() in weak_secrets:
                raise RuntimeError(
                    "Production JWT_SECRET must be a strong random value of at least 32 characters"
                )
            if "*" in self.CORS_ORIGINS:
                raise RuntimeError("Production CORS_ORIGINS cannot contain '*'")

            public = urlparse(self.APP_PUBLIC_URL)
            if public.scheme != "https" or not public.netloc:
                raise RuntimeError(
                    "Production APP_PUBLIC_URL must be an absolute https URL"
                )

            if self.STORAGE_BACKEND.lower() != "s3":
                raise RuntimeError(
                    "Production STORAGE_BACKEND must be s3 so API/workers share durable media"
                )
            if not self.S3_BUCKET:
                raise RuntimeError("Production S3_BUCKET is required")

            uses_openai = any(
                provider.lower() == "openai"
                for provider in (
                    self.TRANSCRIPTION_PROVIDER,
                    self.VISION_PROVIDER,
                    self.EMBEDDING_PROVIDER,
                )
            )
            if uses_openai and (
                not self.OPENAI_API_KEY
                or self.OPENAI_API_KEY.upper().startswith("REPLACE_WITH")
            ):
                raise RuntimeError(
                    "OPENAI_API_KEY is required for configured production AI providers"
                )

            if self.PASSWORD_RESET_EMAIL_PROVIDER != "resend":
                raise RuntimeError(
                    "Production PASSWORD_RESET_EMAIL_PROVIDER must be 'resend'"
                )
            if (
                not self.RESEND_API_KEY
                or self.RESEND_API_KEY.upper().startswith("REPLACE_WITH")
            ):
                raise RuntimeError("Production RESEND_API_KEY is required")
            if not self.PASSWORD_RESET_FROM_EMAIL:
                raise RuntimeError(
                    "Production PASSWORD_RESET_FROM_EMAIL is required"
                )
            if "{token}" not in self.PASSWORD_RESET_URL_TEMPLATE:
                raise RuntimeError(
                    "Production PASSWORD_RESET_URL_TEMPLATE must contain {token}"
                )

            if self.GOOGLE_AUTH_ENABLED and not self.GOOGLE_CLIENT_IDS:
                raise RuntimeError(
                    "GOOGLE_CLIENT_IDS is required when GOOGLE_AUTH_ENABLED=true"
                )

            if self.MAX_UPLOAD_BYTES <= 0 or self.MAX_USER_STORAGE_BYTES < self.MAX_UPLOAD_BYTES:
                raise RuntimeError(
                    "Production storage limits are invalid: MAX_USER_STORAGE_BYTES must be >= MAX_UPLOAD_BYTES"
                )
            if self.MAX_ACTIVE_RENDERS_PER_USER < 1:
                raise RuntimeError("MAX_ACTIVE_RENDERS_PER_USER must be at least 1")
            if not (
                self.SENTRY_DSN
                and not self.SENTRY_DSN.upper().startswith("REPLACE_WITH")
            ):
                raise RuntimeError("Production SENTRY_DSN is required for public-release monitoring")
            if not (0.0 <= self.SENTRY_TRACES_SAMPLE_RATE <= 1.0):
                raise RuntimeError("SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1")
            if not self.TERMS_VERSION:
                raise RuntimeError("TERMS_VERSION is required in production")




settings = Settings()
