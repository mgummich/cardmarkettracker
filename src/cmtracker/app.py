"""Verdrahtung aller Komponenten + Dauerbetrieb (Scheduler)."""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import AppConfig
from .notifiers import Notification, NotificationHub, create_hub
from .providers import PriceProvider, create_provider
from .purchasing import CartPurchaser, DryRunPurchaser, Purchaser
from .reports import build_report, render_text, write_report
from .storage import Storage
from .tracker import CheckResult, Tracker

log = logging.getLogger(__name__)


def create_purchaser(cfg: AppConfig, provider: PriceProvider) -> Purchaser | None:
    if not cfg.purchasing.enabled:
        return None
    if cfg.purchasing.mode == "cart":
        from .providers.mkm_api import MkmApiProvider

        if not isinstance(provider, MkmApiProvider):
            raise RuntimeError("purchasing.mode = cart benötigt provider.type = mkm_api")
        return CartPurchaser(provider.client)
    return DryRunPurchaser()


class App:
    def __init__(
        self,
        cfg: AppConfig,
        storage: Storage | None = None,
        provider: PriceProvider | None = None,
        hub: NotificationHub | None = None,
    ):
        self.cfg = cfg
        self.storage = storage or Storage(cfg.general.database)
        self.provider = provider or create_provider(cfg.provider)
        self.hub = hub or create_hub(cfg.notifications)
        self.tracker = Tracker(
            cfg, self.storage, self.provider, self.hub, create_purchaser(cfg, self.provider)
        )

    def close(self) -> None:
        self.provider.close()
        self.hub.close()
        self.storage.close()

    def run_check(self, only: list[str] | None = None) -> list[CheckResult]:
        log.info("Starte Prüfung (%s)…", self.provider.name)
        results = self.tracker.check_all(only)
        errors = sum(1 for r in results if r.error)
        alerts = sum(len(r.alerts_sent) for r in results)
        log.info("Prüfung fertig: %d Karten, %d Alerts, %d Fehler", len(results), alerts, errors)
        return results

    def run_report(self, send: bool = True) -> Path:
        rc = self.cfg.reports
        report = build_report(self.cfg, self.storage)
        path = write_report(report, rc.output_dir, rc.top_offers)
        log.info("Bericht geschrieben: %s", path)
        if send and rc.send_summary:
            self.hub.send(
                Notification(
                    title="Cardmarket-Bericht",
                    body=render_text(report, rc.public_url),
                    event="report",
                    url=f"{rc.public_url.rstrip('/')}/latest.html" if rc.public_url else None,
                    attachments=[path] if rc.attach_html else [],
                )
            )
        return path

    # ------------------------------------------------------------------ Dauerbetrieb

    def _report_due(self, now_local: datetime) -> bool:
        daily = self.cfg.reports.daily_time
        if not daily:
            return False
        hh, mm = (int(x) for x in daily.split(":"))
        if (now_local.hour, now_local.minute) < (hh, mm):
            return False
        return self.storage.get_meta("last_report_date") != now_local.date().isoformat()

    def run_forever(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        tz = ZoneInfo(self.cfg.general.timezone)
        interval = self.cfg.general.interval_minutes * 60
        next_check = time.monotonic()
        log.info(
            "Tracker läuft: %d Karten, Intervall %.0f min, Bericht täglich um %s",
            len(self.cfg.cards),
            self.cfg.general.interval_minutes,
            self.cfg.reports.daily_time or "–",
        )
        while not stop.is_set():
            if time.monotonic() >= next_check:
                try:
                    self.run_check()
                except Exception:  # noqa: BLE001
                    log.exception("Unerwarteter Fehler bei der Prüfung")
                jitter = random.uniform(0, self.cfg.general.jitter_seconds)
                next_check = time.monotonic() + interval + jitter

            now_local = datetime.now(tz)
            if self._report_due(now_local):
                try:
                    self.run_report()
                except Exception:  # noqa: BLE001
                    log.exception("Bericht konnte nicht erstellt werden")
                self.storage.set_meta("last_report_date", now_local.date().isoformat())

            stop.wait(max(1.0, min(30.0, next_check - time.monotonic())))
        log.info("Tracker beendet.")
