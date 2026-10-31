"""Wiring of all components."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .i18n import _
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
            raise RuntimeError(_("purchasing.mode cart only works with provider.type mkm_api"))
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
        log.info(_("Starting check (%s)…"), self.provider.name)
        results = self.tracker.check_all(only)
        errors = sum(1 for r in results if r.error)
        alerts = sum(len(r.alerts_sent) for r in results)
        log.info(_("Check finished: %d cards, %d alerts, %d errors"), len(results), alerts, errors)
        return results

    def run_report(self, send: bool = True) -> Path:
        rc = self.cfg.reports
        report = build_report(self.cfg, self.storage)
        path = write_report(report, rc.output_dir, rc.top_offers)
        log.info(_("Report written: %s"), path)
        if send and rc.send_summary:
            self.hub.send(
                Notification(
                    title=_("Cardmarket report"),
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
