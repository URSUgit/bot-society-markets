from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from urllib.request import Request, urlopen

from .config import Settings


class NotificationDispatcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def dispatch(self, channel: dict, payload: dict) -> tuple[bool, str | None]:
        channel_type = channel["channel_type"]
        if channel_type == "webhook":
            return self._dispatch_webhook(channel, payload)
        if channel_type == "email":
            return self._dispatch_email(channel, payload)
        return False, f"Unsupported channel type: {channel_type}"

    def _dispatch_webhook(self, channel: dict, payload: dict) -> tuple[bool, str | None]:
        headers = {"content-type": "application/json", "user-agent": "BotSocietyMarkets/0.5"}
        secret = channel.get("secret")
        if secret:
            headers["x-bsm-signature"] = secret
        request = Request(
            channel["target"],
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.outbound_timeout_seconds) as response:
                status = getattr(response, "status", 200)
            return 200 <= int(status) < 300, None if 200 <= int(status) < 300 else f"Webhook returned status {status}"
        except Exception as exc:  # pragma: no cover - network failure path
            return False, str(exc)

    def _dispatch_email(self, channel: dict, payload: dict) -> tuple[bool, str | None]:
        if not self.settings.smtp_host or not self.settings.smtp_from_email:
            return False, "SMTP is not configured"

        message = EmailMessage()
        message["Subject"] = payload["title"]
        message["From"] = self.settings.smtp_from_email
        message["To"] = channel["target"]
        message.set_content(payload["message"])

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.outbound_timeout_seconds) as client:
                if self.settings.smtp_use_tls:
                    client.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    client.login(self.settings.smtp_username, self.settings.smtp_password)
                client.send_message(message)
            return True, None
        except Exception as exc:  # pragma: no cover - network failure path
            return False, str(exc)
