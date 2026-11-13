"""Outbound account email over SMTP. Tests replace the sender on app.state."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings


class MailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        assert settings.smtp_host
        self.host, self.port, self.security = settings.smtp_host, settings.smtp_port, settings.smtp_security
        self.username = settings.smtp_username
        self.password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
        self.sender = settings.mail_from

    def send(self, message: EmailMessage) -> None:
        message["From"] = self.sender
        context = ssl.create_default_context()
        if self.security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=10, context=context)
        else:
            client = smtplib.SMTP(self.host, self.port, timeout=10)
        with client:
            if self.security == "starttls":
                client.starttls(context=context)
            if self.username and self.password:
                client.login(self.username, self.password)
            client.send_message(message)


def sender_for(settings: Settings) -> MailSender | None:
    return SmtpSender(settings) if settings.smtp_host else None
