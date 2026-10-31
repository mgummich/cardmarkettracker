"""Benachrichtigungen: Basisklasse und Verteiler."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import _

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Notification:
    title: str
    body: str
    event: str = "alert"  # alert | report | purchase | error
    url: str | None = None
    attachments: list[Path] = field(default_factory=list)


class Notifier(ABC):
    def __init__(self, name: str, events: list[str]):
        self.name = name
        self.events = set(events)

    def wants(self, event: str) -> bool:
        return event in self.events

    @abstractmethod
    def send(self, n: Notification) -> None:
        """Wirft eine Exception bei Fehlern."""


class NotificationHub:
    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    def send(self, n: Notification) -> int:
        """Sendet an alle passenden Kanäle. Gibt die Anzahl erfolgreicher Zustellungen zurück."""
        ok = 0
        for notifier in self.notifiers:
            if not notifier.wants(n.event):
                continue
            try:
                notifier.send(n)
                ok += 1
            except Exception as exc:  # noqa: BLE001 - ein kaputter Kanal darf nichts blockieren
                log.error(_("Notification via %s failed: %s"), notifier.name, exc)
        return ok

    def close(self) -> None:
        for notifier in self.notifiers:
            close = getattr(notifier, "close", None)
            if close:
                close()
