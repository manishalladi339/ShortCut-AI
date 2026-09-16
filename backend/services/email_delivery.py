"""Transactional email delivery for security-sensitive account flows."""
from __future__ import annotations

from html import escape
from urllib.parse import quote

import httpx

from core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


def build_password_reset_url(token: str) -> str:
    template = settings.PASSWORD_RESET_URL_TEMPLATE
    if "{token}" not in template:
        raise EmailDeliveryError(
            "PASSWORD_RESET_URL_TEMPLATE must contain {token}"
        )
    return template.replace("{token}", quote(token, safe=""))


async def send_password_reset(email: str, token: str) -> bool:
    """Send a reset link.

    Returns False only when delivery is explicitly disabled (development/test).
    Raises EmailDeliveryError for configured-provider failures.
    """
    provider = settings.PASSWORD_RESET_EMAIL_PROVIDER
    if provider in {"", "disabled", "none"}:
        return False
    if provider != "resend":
        raise EmailDeliveryError(
            f"Unsupported password-reset email provider: {provider}"
        )
    if not settings.RESEND_API_KEY or not settings.PASSWORD_RESET_FROM_EMAIL:
        raise EmailDeliveryError("Resend email configuration is incomplete")

    reset_url = build_password_reset_url(token)
    safe_url = escape(reset_url, quote=True)
    payload = {
        "from": settings.PASSWORD_RESET_FROM_EMAIL,
        "to": [email],
        "subject": "Reset your ShortCut AI password",
        "text": (
            "A password reset was requested for your ShortCut AI account. "
            f"Open this link within one hour: {reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        "html": (
            "<p>A password reset was requested for your ShortCut AI account.</p>"
            f'<p><a href="{safe_url}">Reset your password</a></p>'
            "<p>This link expires in one hour. If you did not request this, "
            "you can ignore this email.</p>"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise EmailDeliveryError("Password-reset email provider is unreachable") from exc

    if response.status_code < 200 or response.status_code >= 300:
        raise EmailDeliveryError(
            f"Password-reset email provider returned HTTP {response.status_code}"
        )
    return True
