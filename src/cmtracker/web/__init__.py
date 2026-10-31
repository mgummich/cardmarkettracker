"""Weboberfläche: Dashboard und Konfiguration im Browser."""

from __future__ import annotations

import contextlib
import logging
import signal
from collections.abc import Iterator
from pathlib import Path

from ..runtime import Runner

log = logging.getLogger(__name__)


def serve(config_path: str | Path, runner: Runner | None, host: str, port: int) -> None:
    """Startet den Webserver (blockiert bis Strg+C / SIGTERM)."""
    import uvicorn

    from .app import create_app

    class Server(uvicorn.Server):
        # uvicorn löst SIGINT/SIGTERM nach dem Herunterfahren erneut aus und beendet den
        # Prozess damit sofort. Wir wollen danach noch den Hintergrunddienst sauber stoppen.
        @contextlib.contextmanager
        def capture_signals(self) -> Iterator[None]:
            previous = {
                sig: signal.signal(sig, self.handle_exit) for sig in (signal.SIGINT, signal.SIGTERM)
            }
            try:
                yield
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)

    app = create_app(config_path, runner)
    shown = "localhost" if host in ("0.0.0.0", "::") else host
    log.info("Weboberfläche: http://%s:%d", shown, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", proxy_headers=True)
    Server(config).run()
