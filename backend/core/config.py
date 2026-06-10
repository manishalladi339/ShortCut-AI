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

    S3_BACKEND: str = os.environ.get("S3_BACKEND", "stub")
    STUB_STORAGE_DIR: str = os.environ.get("STUB_STORAGE_DIR", "/tmp/shortcut_storage")
    APP_PUBLIC_URL: str = os.environ.get("APP_PUBLIC_URL", "http://localhost:8001")

    EMERGENT_AUTH_SESSION_URL: str = os.environ.get(
        "EMERGENT_AUTH_SESSION_URL",
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
    )

    STRIPE_PAID_PLANS_ENABLED: bool = (
        os.environ.get("STRIPE_PAID_PLANS_ENABLED", "false").lower() == "true"
    )


settings = Settings()
