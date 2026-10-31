from __future__ import annotations

from ..config import (
    ConsoleConfig,
    DiscordConfig,
    EmailConfig,
    NtfyConfig,
    TelegramConfig,
    WebhookConfig,
)
from .base import Notification, NotificationHub, Notifier
from .channels import (
    ConsoleNotifier,
    DiscordNotifier,
    EmailNotifier,
    NtfyNotifier,
    TelegramNotifier,
    WebhookNotifier,
)

_FACTORIES = {
    TelegramConfig: TelegramNotifier,
    DiscordConfig: DiscordNotifier,
    NtfyConfig: NtfyNotifier,
    EmailConfig: EmailNotifier,
    WebhookConfig: WebhookNotifier,
    ConsoleConfig: ConsoleNotifier,
}


def create_hub(configs: list) -> NotificationHub:
    notifiers: list[Notifier] = [_FACTORIES[type(c)](c) for c in configs]
    if not notifiers:
        notifiers.append(ConsoleNotifier(ConsoleConfig(type="console")))
    return NotificationHub(notifiers)


__all__ = ["Notification", "NotificationHub", "Notifier", "create_hub"]
