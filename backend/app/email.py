"""
Email sending. If SMTP is configured (any free provider works — Gmail app
passwords, Brevo's free tier, etc.), real emails go out. If it's not
configured, the email content is logged instead of sent, so registration,
password reset, and email verification all still work end-to-end during
local development or a first deploy — you just read the link from the
server log instead of your inbox until you wire up SMTP.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("clauseguard.email")

_SMTP_CONFIGURED = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body: str) -> None:
    if not _SMTP_CONFIGURED:
        logger.warning(
            f"[EMAIL NOT SENT — SMTP not configured] To: {to} | Subject: {subject}\n{body}"
        )
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        # Never let a broken SMTP config take down a request (e.g. a
        # registration) that would otherwise succeed. Log loudly instead.
        logger.error(f"Failed to send email to {to} ('{subject}'): {e}")


def send_verification_email(to: str, token: str, frontend_url: str) -> None:
    link = f"{frontend_url}/verify-email?token={token}"
    send_email(
        to,
        "Verify your ClauseGuard email",
        f"Confirm your email address to finish setting up your ClauseGuard account:\n\n{link}\n\n"
        f"This link expires in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.",
    )


def send_password_reset_email(to: str, token: str, frontend_url: str) -> None:
    link = f"{frontend_url}/reset-password?token={token}"
    send_email(
        to,
        "Reset your ClauseGuard password",
        f"Someone requested a password reset for this account. If that was you:\n\n{link}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. "
        f"If you didn't request this, you can safely ignore this email.",
    )
