"""Production runtime validation tests."""
import pytest

from core.config import settings


def _valid_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 48)
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://app.shortcut.example"])
    monkeypatch.setattr(settings, "APP_PUBLIC_URL", "https://api.shortcut.example")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "shortcut-production")
    monkeypatch.setattr(settings, "TRANSCRIPTION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-production-key")


def test_valid_production_configuration_passes(monkeypatch):
    _valid_production(monkeypatch)
    settings.validate_runtime()


def test_production_rejects_weak_jwt_secret(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "JWT_SECRET", "secret")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_runtime()


def test_production_rejects_wildcard_cors(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["*"])
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        settings.validate_runtime()


def test_production_requires_https_public_url(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "APP_PUBLIC_URL", "http://api.example.test")
    with pytest.raises(RuntimeError, match="https"):
        settings.validate_runtime()


def test_production_requires_shared_s3_storage(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    with pytest.raises(RuntimeError, match="STORAGE_BACKEND"):
        settings.validate_runtime()


def test_production_requires_ai_key_when_openai_enabled(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        settings.validate_runtime()
