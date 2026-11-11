import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    async def send_verification(self, recipient: str, link: str) -> None:
        await self._send(recipient, "Verify your PyChat AI email", f"Verify your account: {link}")

    async def send_password_reset(self, recipient: str, link: str) -> None:
        await self._send(recipient, "Reset your PyChat AI password", f"Reset your password: {link}")

    async def _send(self, recipient: str, subject: str, body: str) -> None:
        settings = get_settings()
        if settings.email_provider == "local" and not settings.smtp_host:
            if settings.environment.lower() != "development":
                logger.warning("Local email delivery is disabled outside development")
                return
            logger.info(
                "LOCAL DEVELOPMENT EMAIL recipient=%s subject=%s body=%s",
                recipient,
                subject,
                body,
            )
            return
        if not settings.smtp_host or not settings.smtp_from_email:
            logger.warning("Email delivery is not configured; message not sent")
            return
        await asyncio.to_thread(self._send_sync, recipient, subject, body)

    @staticmethod
    def _send_sync(recipient: str, subject: str, body: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


email_service = EmailService()
