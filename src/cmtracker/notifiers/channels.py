"""Konkrete Benachrichtigungskanäle."""

from __future__ import annotations

import html
import json
import logging
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from ..config import (
    ConsoleConfig,
    DiscordConfig,
    EmailConfig,
    NtfyConfig,
    TelegramConfig,
    WebhookConfig,
)
from ..i18n import _
from .base import Notification, Notifier

log = logging.getLogger(__name__)
TIMEOUT = 20


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _HttpNotifier(Notifier):
    def __init__(self, name: str, events: list[str], transport: httpx.BaseTransport | None = None):
        super().__init__(name, events)
        self.http = httpx.Client(timeout=TIMEOUT, transport=transport)

    def close(self) -> None:
        self.http.close()


class TelegramNotifier(_HttpNotifier):
    def __init__(self, cfg: TelegramConfig, transport: httpx.BaseTransport | None = None):
        super().__init__(cfg.name or "telegram", cfg.events, transport)
        self.cfg = cfg
        self.api = f"https://api.telegram.org/bot{cfg.bot_token}"

    def send(self, n: Notification) -> None:
        text = f"<b>{html.escape(n.title)}</b>\n\n{html.escape(n.body)}"
        if n.url:
            link = html.escape(n.url, quote=True)
            text += f'\n\n<a href="{link}">{html.escape(_("Open on Cardmarket"))}</a>'
        resp = self.http.post(
            f"{self.api}/sendMessage",
            json={
                "chat_id": self.cfg.chat_id,
                "text": _truncate(text, 4096),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        resp.raise_for_status()
        for path in n.attachments:
            with path.open("rb") as fh:
                r = self.http.post(
                    f"{self.api}/sendDocument",
                    data={"chat_id": self.cfg.chat_id},
                    files={"document": (path.name, fh, "text/html")},
                )
            r.raise_for_status()


class DiscordNotifier(_HttpNotifier):
    def __init__(self, cfg: DiscordConfig, transport: httpx.BaseTransport | None = None):
        super().__init__(cfg.name or "discord", cfg.events, transport)
        self.cfg = cfg

    def send(self, n: Notification) -> None:
        color = {"alert": 0xE67E22, "purchase": 0x2ECC71, "error": 0xE74C3C}.get(n.event, 0x3498DB)
        embed = {
            "title": _truncate(n.title, 256),
            "description": _truncate(n.body, 4000),
            "color": color,
        }
        if n.url:
            embed["url"] = n.url
        payload = {"username": self.cfg.username, "embeds": [embed]}
        if n.attachments:
            files = {}
            handles = []
            try:
                for i, path in enumerate(n.attachments):
                    fh = path.open("rb")
                    handles.append(fh)
                    files[f"files[{i}]"] = (path.name, fh, "text/html")
                resp = self.http.post(
                    self.cfg.webhook_url,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                )
            finally:
                for fh in handles:
                    fh.close()
        else:
            resp = self.http.post(self.cfg.webhook_url, json=payload)
        resp.raise_for_status()


class NtfyNotifier(_HttpNotifier):
    def __init__(self, cfg: NtfyConfig, transport: httpx.BaseTransport | None = None):
        super().__init__(cfg.name or "ntfy", cfg.events, transport)
        self.cfg = cfg

    def send(self, n: Notification) -> None:
        payload: dict[str, object] = {
            "topic": self.cfg.topic,
            "title": n.title,
            "message": _truncate(n.body, 4000),
            "tags": [
                {"alert": "moneybag", "purchase": "shopping_cart", "error": "warning"}.get(
                    n.event, "bar_chart"
                )
            ],
        }
        if n.url:
            payload["click"] = n.url
        if self.cfg.priority:
            payload["priority"] = self.cfg.priority
        headers = {"Authorization": f"Bearer {self.cfg.token}"} if self.cfg.token else {}
        resp = self.http.post(self.cfg.server.rstrip("/"), json=payload, headers=headers)
        resp.raise_for_status()


class WebhookNotifier(_HttpNotifier):
    def __init__(self, cfg: WebhookConfig, transport: httpx.BaseTransport | None = None):
        super().__init__(cfg.name or "webhook", cfg.events, transport)
        self.cfg = cfg

    def send(self, n: Notification) -> None:
        resp = self.http.post(
            self.cfg.url,
            json={"event": n.event, "title": n.title, "message": n.body, "url": n.url},
            headers=self.cfg.headers,
        )
        resp.raise_for_status()


class EmailNotifier(Notifier):
    def __init__(self, cfg: EmailConfig):
        super().__init__(cfg.name or "email", cfg.events)
        self.cfg = cfg

    def send(self, n: Notification) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"[Cardmarket Tracker] {n.title}"
        msg["From"] = self.cfg.sender
        msg["To"] = ", ".join(self.cfg.recipients)
        body = n.body + (f"\n\n{n.url}" if n.url else "")
        msg.set_content(body)
        for path in n.attachments:
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            msg.add_attachment(
                path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
            )

        context = ssl.create_default_context()
        if self.cfg.security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                self.cfg.host, self.cfg.port, context=context, timeout=TIMEOUT
            )
        else:
            smtp = smtplib.SMTP(self.cfg.host, self.cfg.port, timeout=TIMEOUT)
        with smtp:
            if self.cfg.security == "starttls":
                smtp.starttls(context=context)
            if self.cfg.username:
                smtp.login(self.cfg.username, self.cfg.password or "")
            smtp.send_message(msg)


class ConsoleNotifier(Notifier):
    def __init__(self, cfg: ConsoleConfig):
        super().__init__(cfg.name or "console", cfg.events)

    def send(self, n: Notification) -> None:
        extra = f"\n{n.url}" if n.url else ""
        files = "".join(f"\n[Anhang] {p}" for p in n.attachments)
        log.info("[%s] %s\n%s%s%s", n.event.upper(), n.title, n.body, extra, files)
