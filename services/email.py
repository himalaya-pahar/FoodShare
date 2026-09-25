"""
Email Service Module.
Provides modular email sending functionality with Gmail SMTP for development.
Designed with a base interface so production email providers (e.g., SendGrid, Resend, AWS SES)
can be swapped in seamlessly without changing auth or business logic.
"""
import html
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
        request_base_url: Optional[str] = None,
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

    def get_verification_url(
        self,
        raw_token: str,
        request_base_url: Optional[str] = None,
    ) -> str:
        """
        Resolves the appropriate verification URL.
        Priority:
        1. Explicit FRONTEND_URL if set and not localhost (e.g. custom web app domain)
        2. Active request_base_url if from a live host (e.g. Vercel deployment host)
        3. Vercel deployment variables (VERCEL_PROJECT_PRODUCTION_URL or VERCEL_URL)
        4. Fallback to FRONTEND_URL, request_base_url, or http://localhost:8000
        """
        frontend = (os.getenv("FRONTEND_URL") or getattr(config, "FRONTEND_URL", "")).rstrip("/")
        if frontend and "localhost" not in frontend and "127.0.0.1" not in frontend:
            return f"{frontend}/verify-email?token={raw_token}"

        if request_base_url:
            clean_base = request_base_url.rstrip("/")
            if "localhost" not in clean_base and "127.0.0.1" not in clean_base:
                return f"{clean_base}/verify-email?token={raw_token}"

        vercel_prod = os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
        if vercel_prod:
            return f"https://{vercel_prod.rstrip('/')}/verify-email?token={raw_token}"

        vercel_url = os.getenv("VERCEL_URL")
        if vercel_url:
            return f"https://{vercel_url.rstrip('/')}/verify-email?token={raw_token}"

        base = frontend or request_base_url or "http://localhost:8000"
        return f"{base.rstrip('/')}/verify-email?token={raw_token}"

    def _render_verification_email(
        self,
        full_name: str,
        verification_url: str,
    ) -> tuple[str, str]:
        """
        Renders plain text and HTML versions of the verification email.
        """
        safe_name = html.escape(full_name)
        safe_url = html.escape(verification_url)

        text_content = f"""Verify Your Email - FoodShare

Hello {full_name},

Thank you for registering with FoodShare.

Please click the link below to verify your email address:
{verification_url}

Please note: This verification link expires in 5 minutes.

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
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #fafafa; margin: 0; padding: 40px 16px; color: #111827;">
  <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 460px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
    <tr>
      <td style="padding: 32px 28px;">
        <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #9ca3af; margin-bottom: 20px;">FoodShare</div>
        <h1 style="margin: 0 0 12px 0; color: #111827; font-size: 20px; font-weight: 600; letter-spacing: -0.02em;">Verify your email</h1>
        <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 1.6; color: #4b5563;">
          Hello <strong>{safe_name}</strong>,
        </p>
        <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #4b5563;">
          Please confirm your email address to continue setting up your account. <strong>This link expires in 5 minutes.</strong>
        </p>
        <!-- CTA Button -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 24px 0;">
          <tr>
            <td>
              <a href="{safe_url}" target="_blank" style="background-color: #111827; color: #ffffff; display: block; text-align: center; padding: 12px 20px; font-size: 14px; font-weight: 500; text-decoration: none; border-radius: 8px;">
                Verify Email Address
              </a>
            </td>
          </tr>
        </table>
        <p style="margin: 0 0 20px 0; font-size: 13px; line-height: 1.5; color: #6b7280;">
          After verification, your account will be reviewed by an administrator.
        </p>
        <div style="border-top: 1px solid #f3f4f6; padding-top: 16px; margin-top: 24px;">
          <p style="margin: 0 0 6px 0; font-size: 12px; color: #9ca3af;">
            Button not working? Paste this link into your browser:
          </p>
          <p style="margin: 0; font-size: 12px; line-height: 1.4; word-break: break-all;">
            <a href="{safe_url}" style="color: #2563eb; text-decoration: none;">{safe_url}</a>
          </p>
        </div>
      </td>
    </tr>
    <tr>
      <td style="background-color: #f9fafb; padding: 16px 28px; text-align: center; border-top: 1px solid #f3f4f6;">
        <p style="margin: 0; font-size: 12px; color: #9ca3af;">
          If you didn't create a FoodShare account, please ignore this email.
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
        request_base_url: Optional[str] = None,
    ) -> bool:
        """
        Sends account verification email via SMTP.
        Does NOT log the raw token or credentials.
        """
        verification_url = self.get_verification_url(
            raw_token=raw_token,
            request_base_url=request_base_url,
        )

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
            print(f"[FoodShare Email] Verification link: {verification_url}")
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
            err_msg = f"[FoodShare Email] Failed to send verification email to {to_email}: {type(exc).__name__} - {exc}"
            print(err_msg)
            logger.error(err_msg)
            return False


def render_verification_success_html(message: str, status: str) -> str:
    """Renders a minimal, modern verification success landing page."""
    safe_msg = html.escape(message)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Email Verified - FoodShare</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #FAFAFA;
      color: #111827;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
      -webkit-font-smoothing: antialiased;
    }}
    .card {{
      background: #FFFFFF;
      width: 100%;
      max-width: 380px;
      border: 1px solid #E5E7EB;
      border-radius: 16px;
      padding: 36px 28px;
      text-align: center;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 6px 16px rgba(0, 0, 0, 0.02);
    }}
    .brand {{
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #9CA3AF;
      margin-bottom: 24px;
    }}
    .icon-wrap {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background-color: #ECFDF5;
      border: 1px solid #D1FAE5;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px auto;
    }}
    .icon {{
      width: 22px;
      height: 22px;
      color: #059669;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: #111827;
      margin-bottom: 8px;
    }}
    .badge {{
      display: inline-block;
      font-size: 12px;
      font-weight: 500;
      color: #4B5563;
      background: #F3F4F6;
      border: 1px solid #E5E7EB;
      padding: 3px 10px;
      border-radius: 9999px;
      margin-bottom: 16px;
    }}
    .desc {{
      font-size: 14px;
      line-height: 1.55;
      color: #6B7280;
      margin-bottom: 28px;
    }}
    .btn {{
      display: block;
      width: 100%;
      background-color: #111827;
      color: #FFFFFF;
      font-size: 14px;
      font-weight: 500;
      text-decoration: none;
      padding: 12px 18px;
      border-radius: 8px;
      transition: background-color 0.15s ease;
    }}
    .btn:hover {{
      background-color: #1F2937;
    }}
    .hint {{
      font-size: 12px;
      color: #9CA3AF;
      margin-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">FoodShare</div>
    <div class="icon-wrap">
      <svg class="icon" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    </div>
    <h1>Email Verified!</h1>
    <div class="badge">Next Step: Administrator Review</div>
    <p class="desc">
      Your email address is verified. Your account is now queued for administrator review. You can return to the mobile app now.
    </p>
    <a href="foodsharemobile://" class="btn">Open FoodShare App</a>
    <p class="hint">You can safely close this browser window</p>
  </div>
</body>
</html>"""


def render_verification_error_html(error_message: str) -> str:
    """Renders a minimal, modern error page when verification token is invalid or expired."""
    safe_err = html.escape(error_message)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Error - FoodShare</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #FAFAFA;
      color: #111827;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
      -webkit-font-smoothing: antialiased;
    }}
    .card {{
      background: #FFFFFF;
      width: 100%;
      max-width: 380px;
      border: 1px solid #E5E7EB;
      border-radius: 16px;
      padding: 36px 28px;
      text-align: center;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 6px 16px rgba(0, 0, 0, 0.02);
    }}
    .brand {{
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #9CA3AF;
      margin-bottom: 24px;
    }}
    .icon-wrap {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background-color: #FEF2F2;
      border: 1px solid #FEE2E2;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px auto;
    }}
    .icon {{
      width: 22px;
      height: 22px;
      color: #DC2626;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: #111827;
      margin-bottom: 12px;
    }}
    .error-box {{
      background-color: #FEF2F2;
      border: 1px solid #FEE2E2;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 13px;
      color: #991B1B;
      line-height: 1.45;
      margin-bottom: 16px;
      text-align: left;
    }}
    .desc {{
      font-size: 14px;
      line-height: 1.55;
      color: #6B7280;
      margin-bottom: 28px;
    }}
    .btn {{
      display: block;
      width: 100%;
      background-color: #111827;
      color: #FFFFFF;
      font-size: 14px;
      font-weight: 500;
      text-decoration: none;
      padding: 12px 18px;
      border-radius: 8px;
      transition: background-color 0.15s ease;
    }}
    .btn:hover {{
      background-color: #1F2937;
    }}
    .hint {{
      font-size: 12px;
      color: #9CA3AF;
      margin-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">FoodShare</div>
    <div class="icon-wrap">
      <svg class="icon" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    </div>
    <h1>Link Expired or Already Used</h1>
    <div class="error-box">
      {safe_err}
    </div>
    <p class="desc">
      Verification links expire after 5 minutes for security. Please open the FoodShare app to request a new link, or sign in if you are already approved.
    </p>
    <a href="foodsharemobile://" class="btn">Open FoodShare App</a>
    <p class="hint">You can safely close this browser window</p>
  </div>
</body>
</html>"""


# Default service instance for injection / direct usage
email_service: BaseEmailService = SMTPEmailService()
