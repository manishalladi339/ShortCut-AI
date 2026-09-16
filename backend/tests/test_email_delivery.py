"""Tests for safe password-reset URL construction."""
from services.email_delivery import build_password_reset_url
from core.config import settings


def test_reset_url_percent_encodes_token(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PASSWORD_RESET_URL_TEMPLATE",
        "https://app.example/reset?token={token}",
    )
    url = build_password_reset_url("abc+/=? &")
    assert url == "https://app.example/reset?token=abc%2B%2F%3D%3F%20%26"


def test_reset_url_supports_mobile_deep_link(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PASSWORD_RESET_URL_TEMPLATE",
        "shortcutai://reset-password?token={token}",
    )
    assert (
        build_password_reset_url("safe-token")
        == "shortcutai://reset-password?token=safe-token"
    )
