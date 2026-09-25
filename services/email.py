"""
Email Service Module.
Provides modular email sending functionality with Gmail SMTP for development.
Designed with a base interface so production email providers (e.g., SendGrid, Resend, AWS SES)
can be swapped in seamlessly without changing auth or business logic.
"""
import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv

import config

logger = logging.getLogger("foodshare.email")


class BaseEmailService(ABC):
    """Abstract base class for email delivery services."""

    @abstractmethod
    def send_verification_email(
        self,
        to_email: str,
        full_name: str,
        raw_token: str,
    ) -> bool:
        """Send account verification email to a newly registered user."""
        pass


class SMTPEmailService(BaseEmailService):
    """
    SMTP-based email service supporting Gmail SMTP and standard TLS.
    Dynamically loads credentials so updating .env takes effect immediately.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        use_tls: Optional[bool] = None,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._from_name = from_name
        self._use_tls = use_tls

    def _ensure_env_loaded(self):
        """Reloads .env if username or password is not currently present."""
        if not os.getenv("SMTP_USERNAME") or not os.getenv("SMTP_PASSWORD"):
            load_dotenv(override=True)

    @property
    def host(self) -> str:
        self._ensure_env_loaded()
        return self._host or os.getenv("SMTP_HOST") or getattr(config, "SMTP_HOST", "smtp.gmail.com")

    @property
    def port(self) -> int:
        if self._port is not None:
            return self._port
        self._ensure_env_loaded()
        return int(os.getenv("SMTP_PORT") or getattr(config, "SMTP_PORT", 587))

    @property
    def username(self) -> str:
        self._ensure_env_loaded()
        return self._username or os.getenv("SMTP_USERNAME") or getattr(config, "SMTP_USERNAME", "")

    @property
    def password(self) -> str:
        self._ensure_env_loaded()
        return self._password or os.getenv("SMTP_PASSWORD") or getattr(config, "SMTP_PASSWORD", "")

    @property
    def from_email(self) -> str:
        self._ensure_env_loaded()
        return (
            self._from_email
            or os.getenv("SMTP_FROM_EMAIL")
            or getattr(config, "SMTP_FROM_EMAIL", "")
            or self.username
            or "noreply@foodshare.app"
        )

    @property
    def from_name(self) -> str:
        return self._from_name or os.getenv("SMTP_FROM_NAME") or getattr(config, "SMTP_FROM_NAME", "FoodShare")

    @property
    def use_tls(self) -> bool:
        if self._use_tls is not None:
            return self._use_tls
        return (os.getenv("SMTP_USE_TLS") or "true").lower() == "true"

    def _render_verification_email(
        self,
        full_name: str,
        verification_url: str,
    ) -> tuple[str, str]:
        """
        Renders plain text and HTML versions of the verification email.
        """
        text_content = f"""Verify Your Email

Hello {full_name},

Thank you for registering with FoodShare.

Please click the link below to verify your email address:
{verification_url}

After verification, your account will be reviewed by an administrator.

If you did not create a FoodShare account, please ignore this email.
"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verify Your Email</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 30px 15px;">
  <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
    <!-- Header -->
    <tr>
      <td style="background-color: #10B981; padding: 28px 32px; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">FoodShare</h1>
      </td>
    </tr>
    <!-- Content -->
    <tr>
      <td style="padding: 36px 32px; color: #1f2937;">
        <h2 style="margin: 0 0 16px 0; color: #111827; font-size: 20px; font-weight: 600;">Verify Your Email</h2>
        <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #4b5563;">
          Hello <strong>{full_name}</strong>,
        </p>
        <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: #4b5563;">
          Thank you for registering. Please click the button below to verify your email address.
        </p>
        <!-- CTA Button -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 28px 0;">
          <tr>
            <td align="center">
              <a href="{verification_url}" target="_blank" style="background-color: #10B981; color: #ffffff; display: inline-block; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 8px; box-shadow: 0 2px 6px rgba(16, 185, 129, 0.35);">
                Verify Email
              </a>
            </td>
          </tr>
        </table>
        <!-- Notice -->
        <div style="background-color: #f0fdf4; border-left: 4px solid #10B981; padding: 14px 16px; border-radius: 4px; margin: 24px 0;">
          <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #166534;">
            <strong>Next step:</strong> After verification, your account will be reviewed by an administrator.
          </p>
        </div>
        <p style="margin: 28px 0 8px 0; font-size: 13px; line-height: 1.5; color: #6b7280;">
          If the button above does not work, copy and paste this link into your browser:
        </p>
        <p style="margin: 0; font-size: 12px; line-height: 1.5; word-break: break-all; color: #3b82f6;">
          <a href="{verification_url}" style="color: #2563eb; text-decoration: underline;">{verification_url}</a>
        </p>
      </td>
    </tr>
    <!-- Footer -->
    <tr>
      <td style="background-color: #f9fafb; padding: 20px 32px; text-align: center; border-top: 1px solid #e5e7eb;">
        <p style="margin: 0; font-size: 12px; color: #9ca3af;">
          If you did not create a FoodShare account, you can safely ignore this email.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        return text_content, html_content

    def send_verification_email(
        self,
        to_email: str,
        full_name: str,
        raw_token: str,
    ) -> bool:
        """
        Sends account verification email via SMTP.
        Does NOT log the raw token or credentials.
        """
        verification_url = f"{config.FRONTEND_URL}/verify-email?token={raw_token}"

        username = self.username
        password = self.password

        if not username or not password:
            warn_msg = (
                f"[FoodShare Email] WARNING: SMTP credentials (SMTP_USERNAME/SMTP_PASSWORD) are not set in .env. "
                f"Skipping actual email delivery for {to_email}."
            )
            print(warn_msg)
            logger.warning(warn_msg)
            return False

        text_content, html_content = self._render_verification_email(
            full_name=full_name,
            verification_url=verification_url,
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Verify Your Email - {self.from_name}"
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            print(f"[FoodShare Email] Connecting to {self.host}:{self.port} to send verification email to {to_email}...")
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                server.login(username, password)
                server.send_message(msg)
            print(f"[FoodShare Email] Verification email successfully sent to {to_email}")
            logger.info("Verification email sent successfully to %s", to_email)
            return True
        except Exception as exc:
            # Crucial: Log error message with type and text without logging password or raw token
            err_msg = f"[FoodShare Email] Failed to send verification email to {to_email}: {type(exc).__name__} - {exc}"
            print(err_msg)
            logger.error(err_msg)
            return False


# Default service instance for injection / direct usage
email_service: BaseEmailService = SMTPEmailService()
