"""Backend configuration loaded from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

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
    WORKER_POLL_INTERVAL_SEC: float = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "1.0"))
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

    EMERGENT_AUTH_SESSION_URL: str = os.environ.get(
        "EMERGENT_AUTH_SESSION_URL",
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
    )

    STRIPE_PAID_PLANS_ENABLED: bool = (
        os.environ.get("STRIPE_PAID_PLANS_ENABLED", "false").lower() == "true"
    )


settings = Settings()
