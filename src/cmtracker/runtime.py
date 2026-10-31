"""Runtime: background thread for checks, reports and configuration reload.

The ``Runner`` owns the ``App`` exclusively (SQLite connection, HTTP clients) and runs
everything in *one* thread. The web UI only talks to it via
``request_check``/``request_report``/``notify_config_changed`` and reads ``status``.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .app import App
from .config import AppConfig, ConfigError, load_config
from .i18n import _, set_language
from .models import utcnow

log = logging.getLogger(__name__)

STARTER_CONFIG = """\
# Cardmarket Tracker – created automatically. Edit it in the web interface or here
# (see config.example.yaml and https://mgummich.github.io/cardmarkettracker/ for all options).
general:
  language: en              # en | de – notifications, reports, CLI and logs
  interval_minutes: 60
  database: data/tracker.db
  timezone: Europe/Berlin

provider:
  type: demo

defaults:
  filters:
    min_condition: EX
  alerts:
    drop_percent: 10
    cooldown_hours: 12

cards: []

notifications:
  - type: console

reports:
  output_dir: data/reports
  daily_time: "08:00"

purchasing:
  enabled: false
  mode: dry_run

web:
  username: admin
  password: ${WEB_PASSWORD:-}
"""


def ensure_config(path: str | Path) -> bool:
    """Create a starter configuration if none exists. Returns True if it was created."""
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STARTER_CONFIG, encoding="utf-8")
    log.warning(_("No configuration found – created a starter configuration at %s"), path)
    return True


@dataclass
class RunnerStatus:
    scheduling: bool = True
    started_at: datetime | None = None
    running: bool = False
    current_task: str | None = None  # check | report
    last_check_at: datetime | None = None
    last_check_seconds: float | None = None
    last_check_errors: int = 0
    last_check_alerts: int = 0
    next_check_at: datetime | None = None
    last_report_at: datetime | None = None
    last_reload_at: datetime | None = None
    reloads: int = 0
    config_error: str | None = None
    pending: list[str] = field(default_factory=list)  # check | report


class Runner:
    def __init__(self, config_path: str | Path, schedule: bool = True):
        self.config_path = Path(config_path)
        self.schedule = schedule
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._check_requests: list[list[str] | None] = []
        self._report_requested: bool | None = None  # None = kein Auftrag, sonst 'senden?'
        self._force_reload = False
        self._thread: threading.Thread | None = None
        self._status = RunnerStatus(scheduling=schedule)

    # ------------------------------------------------------------------ API für die Weboberfläche

    @property
    def status(self) -> RunnerStatus:
        with self._lock:
            return replace(self._status, pending=list(self._status.pending))

    def request_check(self, card_keys: list[str] | None = None) -> None:
        with self._lock:
            self._check_requests.append(card_keys)
            self._status.pending.append("check")
        self._wake.set()

    def request_report(self, send: bool = False) -> None:
        with self._lock:
            self._report_requested = send
            self._status.pending.append("report")
        self._wake.set()

    def notify_config_changed(self) -> None:
        with self._lock:
            self._force_reload = True
        self._wake.set()

    # ------------------------------------------------------------------ Lebenszyklus

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="cmtracker-runner", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 60) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def run_blocking(self) -> None:
        self._loop()

    def wait_idle(self, timeout: float = 30) -> bool:
        """Für Tests: wartet, bis keine Aufträge mehr offen sind."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            s = self.status
            if not s.running and not s.pending and not self._check_requests:
                return True
            time.sleep(0.05)
        return False

    # ------------------------------------------------------------------ Intern

    def _set(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self._status, k, v)

    def _load(self) -> AppConfig | None:
        try:
            cfg = load_config(self.config_path)
        except ConfigError as exc:
            log.error(_("Configuration invalid – keeping the previous one:\n%s"), exc)
            self._set(config_error=str(exc))
            return None
        self._set(config_error=None)
        set_language(cfg.general.language)  # language of this thread (messages, logs)
        return cfg

    def _mtime(self) -> float | None:
        try:
            return self.config_path.stat().st_mtime
        except OSError:
            return None

    def _loop(self) -> None:
        self._set(started_at=utcnow())
        app: App | None = None
        seen_mtime: float | None = None
        last_check_mono: float | None = None
        next_check = time.monotonic()

        while not self._stop.is_set():
            # 1) Konfiguration (neu) laden
            mtime = self._mtime()
            with self._lock:
                force, self._force_reload = self._force_reload, False
            if app is None or force or mtime != seen_mtime:
                seen_mtime = mtime
                cfg = self._load()
                if cfg is not None:
                    try:
                        new_app = App(cfg)
                    except Exception as exc:  # noqa: BLE001
                        log.exception(_("Could not create components"))
                        self._set(config_error=str(exc))
                    else:
                        if app is not None:
                            app.close()
                            log.info(_("Configuration reloaded (%d cards)"), len(cfg.cards))
                        app = new_app
                        self._set(last_reload_at=utcnow(), reloads=self._status.reloads + 1)
                        if last_check_mono is not None:
                            next_check = last_check_mono + self._interval(cfg)
            if app is None:
                self._wake.wait(10)
                self._wake.clear()
                continue

            # 2) Manuelle Aufträge
            with self._lock:
                requests, self._check_requests = self._check_requests, []
                report_req, self._report_requested = self._report_requested, None
            for keys in requests:
                self._do_check(app, keys)

            # 3) Geplante Prüfung
            if self.schedule and time.monotonic() >= next_check:
                self._do_check(app, None)
                last_check_mono = time.monotonic()
                next_check = last_check_mono + self._interval(app.cfg)

            # 4) Bericht
            now_local = datetime.now(ZoneInfo(app.cfg.general.timezone))
            if report_req is not None:
                self._do_report(app, send=report_req)
            if self.schedule and app.cfg.cards and app._report_due(now_local):
                self._do_report(app, send=True)
                app.storage.set_meta("last_report_date", now_local.date().isoformat())

            with self._lock:
                self._status.pending.clear()
            self._set(
                next_check_at=(
                    utcnow() + timedelta(seconds=max(0, next_check - time.monotonic()))
                    if self.schedule
                    else None
                )
            )
            self._wake.wait(max(1.0, min(30.0, next_check - time.monotonic())))
            self._wake.clear()

        if app is not None:
            app.close()
        log.info(_("Tracker stopped."))

    @staticmethod
    def _interval(cfg: AppConfig) -> float:
        g = cfg.general
        return g.interval_minutes * 60 + random.uniform(0, g.jitter_seconds)

    def _do_check(self, app: App, keys: list[str] | None) -> None:
        self._set(running=True, current_task="check")
        start = time.monotonic()
        try:
            results = app.run_check(keys)
            self._set(
                last_check_errors=sum(1 for r in results if r.error),
                last_check_alerts=sum(len(r.alerts_sent) for r in results),
            )
        except Exception:  # noqa: BLE001
            log.exception(_("Unexpected error during check"))
        finally:
            self._set(
                running=False,
                current_task=None,
                last_check_at=utcnow(),
                last_check_seconds=round(time.monotonic() - start, 1),
            )

    def _do_report(self, app: App, send: bool) -> None:
        self._set(running=True, current_task="report")
        try:
            app.run_report(send=send)
            self._set(last_report_at=utcnow())
        except Exception:  # noqa: BLE001
            log.exception(_("Could not create report"))
        finally:
            self._set(running=False, current_task=None)
