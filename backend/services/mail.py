"""SMTP delivery. Tokens are never logged or stored as plaintext."""

import smtplib
import ssl
from email.message import EmailMessage
from core.config import settings


def send_reset_email(address: str, token: str) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError("Password reset email is not configured")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = address
    message["Subject"] = "Reset your ShortCut AI password"
    message.set_content(
        "Use this link to reset your password. It expires in one hour.\n\n"
        f"{settings.FRONTEND_PUBLIC_URL.rstrip('/')}/reset-password?token={token}\n\n"
        "If you did not request this, ignore this email."
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as client:
        if settings.SMTP_STARTTLS:
            client.starttls(context=ssl.create_default_context())
        if settings.SMTP_USERNAME:
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)
