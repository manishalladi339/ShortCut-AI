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
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setattr(settings, "TERMS_VERSION", "2026-09-28")
    monkeypatch.setattr(settings, "PASSWORD_RESET_EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    monkeypatch.setattr(
        settings,
        "PASSWORD_RESET_FROM_EMAIL",
        "ShortCut AI <security@shortcut.example>",
    )
    monkeypatch.setattr(
        settings,
        "PASSWORD_RESET_URL_TEMPLATE",
        "https://app.shortcut.example/reset-password?token={token}",
    )


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



def test_production_requires_reset_email_provider(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "PASSWORD_RESET_EMAIL_PROVIDER", "disabled")
    with pytest.raises(RuntimeError, match="PASSWORD_RESET_EMAIL_PROVIDER"):
        settings.validate_runtime()


def test_production_reset_url_template_must_contain_token(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(
        settings,
        "PASSWORD_RESET_URL_TEMPLATE",
        "https://app.shortcut.example/reset-password",
    )
    with pytest.raises(RuntimeError, match=r"\{token\}"):
        settings.validate_runtime()


def test_production_google_auth_requires_client_ids(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "GOOGLE_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_IDS", [])
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_IDS"):
        settings.validate_runtime()


def test_production_rejects_invalid_storage_limits(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(settings, "MAX_USER_STORAGE_BYTES", 512)
    with pytest.raises(RuntimeError, match="storage limits"):
        settings.validate_runtime()


def test_production_rejects_placeholder_openai_key(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "REPLACE_WITH_PROVIDER_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        settings.validate_runtime()


def test_production_requires_sentry(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    with pytest.raises(RuntimeError, match="SENTRY_DSN"):
        settings.validate_runtime()


def test_production_rejects_placeholder_sentry(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "SENTRY_DSN", "REPLACE_WITH_SENTRY_DSN")
    with pytest.raises(RuntimeError, match="SENTRY_DSN"):
        settings.validate_runtime()


def test_production_rejects_placeholder_resend_key(monkeypatch):
    _valid_production(monkeypatch)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "REPLACE_WITH_RESEND_KEY")
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        settings.validate_runtime()
