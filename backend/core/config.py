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
    MEDIA_PROBE_TIMEOUT_SEC: int = int(os.environ.get("MEDIA_PROBE_TIMEOUT_SEC", "30"))
    WORKER_POLL_INTERVAL_SEC: float = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "1.0"))

    EMERGENT_AUTH_SESSION_URL: str = os.environ.get(
        "EMERGENT_AUTH_SESSION_URL",
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
    )

    STRIPE_PAID_PLANS_ENABLED: bool = (
        os.environ.get("STRIPE_PAID_PLANS_ENABLED", "false").lower() == "true"
    )


settings = Settings()
