"""Kommandozeile: ``cmtracker <befehl>``."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import logging
import os
import signal
import sys
import threading
from datetime import timedelta

from . import __version__
from .config import AppConfig, ConfigError, load_config
from .formatting import describe_offer, eur, local_time, pct
from .models import utcnow

log = logging.getLogger("cmtracker")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _app(cfg: AppConfig):
    from .app import App

    return App(cfg)


# ---------------------------------------------------------------------- Befehle


def cmd_validate(cfg: AppConfig, args: argparse.Namespace) -> int:
    print(f"✔ Konfiguration gültig – Provider: {cfg.provider.type}, {len(cfg.cards)} Karten")
    for card in cfg.cards:
        f = cfg.card_filters(card)
        a = cfg.card_alerts(card)
        state = "" if card.enabled else " (deaktiviert)"
        print(f"  • {card.key}{state}: {card.name}")
        print(f"      Filter: {f.model_dump(exclude_none=True) or '-'}")
        print(f"      Alerts: {a.model_dump(exclude_none=True)}")
        if card.buy.enabled:
            print(f"      Kauf:   bis {eur(card.buy.max_price)}, {card.buy.quantity} Stück")
    print(f"  Benachrichtigungen: {[n.type for n in cfg.notifications] or ['console']}")
    p = cfg.purchasing
    print(
        f"  Auto-Kauf: {'AN' if p.enabled else 'aus'} (Modus {p.mode}, "
        f"max {eur(p.max_per_run)}/Lauf, {eur(p.max_per_month)}/Monat)"
    )
    return 0


def cmd_check(cfg: AppConfig, args: argparse.Namespace) -> int:
    app = _app(cfg)
    try:
        results = app.run_check(args.card or None)
    finally:
        app.close()
    for r in results:
        if r.error:
            print(f"✘ {r.card_key}: {r.error}")
            continue
        s = r.snapshot
        assert s is not None
        print(
            f"✔ {r.card_key}: {s.offer_count}/{s.total_offer_count} Angebote, "
            f"ab {eur(s.min_price)}, Trend {eur(s.price_guide.trend)}"
        )
        if s.cheapest:
            print(f"    günstigstes: {describe_offer(s.cheapest)}")
        for a in r.alerts_sent:
            print(f"    🔔 {a.reason}")
        for decision, result in r.purchases:
            print(f"    🛒 {decision.quantity}x {eur(decision.offer.price)} → {result.status}")
    return 1 if results and all(r.error for r in results) else 0


def cmd_run(cfg: AppConfig, args: argparse.Namespace) -> int:
    app = _app(cfg)
    stop = threading.Event()

    def handle(signum, frame):  # noqa: ARG001
        log.info("Signal %s empfangen – beende…", signum)
        stop.set()

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)
    try:
        app.run_forever(stop)
    finally:
        app.close()
    return 0


def cmd_report(cfg: AppConfig, args: argparse.Namespace) -> int:
    app = _app(cfg)
    try:
        path = app.run_report(send=args.send)
    finally:
        app.close()
    print(f"Bericht: {path}")
    return 0


def cmd_test_notify(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .notifiers import Notification, create_hub

    hub = create_hub(cfg.notifications)
    ok = 0
    for event in ("alert", "report", "purchase", "error"):
        ok += hub.send(
            Notification(
                f"Test ({event})",
                "Testnachricht vom Cardmarket Tracker – die Verbindung funktioniert. ✔",
                event=event,
                url="https://www.cardmarket.com",
            )
        )
    hub.close()
    print(f"{ok} Testnachrichten zugestellt (Details siehe Log).")
    return 0 if ok else 1


def cmd_history(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .storage import Storage

    storage = Storage(cfg.general.database)
    rows = storage.history(args.card, utcnow() - timedelta(days=args.days))
    if not rows:
        print("Keine Daten.")
        return 1
    print(f"{'Zeitpunkt':<17} {'Tiefst':>11} {'Ø5':>11} {'Trend':>11} {'Δ':>9} {'Angeb.':>7}")
    prev = None
    for s in rows:
        delta = None
        if prev and prev.min_price and s.min_price:
            delta = (s.min_price - prev.min_price) / prev.min_price * 100
        print(
            f"{local_time(s.taken_at, cfg.general.timezone):<17} {eur(s.min_price):>11} "
            f"{eur(s.avg5_price):>11} {eur(s.price_guide.trend):>11} {pct(delta):>9} "
            f"{s.offer_count:>7}"
        )
        prev = s
    storage.close()
    return 0


def cmd_export(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .reports import export_csv
    from .storage import Storage

    storage = Storage(cfg.general.database)
    n = export_csv(storage, args.card, args.output)
    storage.close()
    print(f"{n} Datenpunkte nach {args.output} exportiert.")
    return 0


def cmd_purchases(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .storage import Storage

    storage = Storage(cfg.general.database)
    rows = storage.purchases(args.limit)
    if not rows:
        print("Noch keine Käufe (oder simulierten Käufe).")
    for p in rows:
        print(
            f"{local_time(p.created_at, cfg.general.timezone)}  {p.status:<10} {p.mode:<8} "
            f"{p.card_key:<25} {p.quantity}x {eur(p.price):>10}  {p.seller or ''}"
        )
    storage.close()
    return 0


def cmd_serve(cfg: AppConfig, args: argparse.Namespace) -> int:
    directory = cfg.reports.output_dir
    os.makedirs(directory, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Berichte unter http://{args.host}:{args.port}/latest.html (Strg+C zum Beenden)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


# ---------------------------------------------------------------------- Parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cmtracker", description="Cardmarket Preis-Tracker")
    p.add_argument(
        "-c",
        "--config",
        default=os.environ.get("CMTRACKER_CONFIG", "config.yaml"),
        help="Pfad zur config.yaml (Standard: $CMTRACKER_CONFIG oder ./config.yaml)",
    )
    p.add_argument("--log-level", help="DEBUG, INFO, WARNING, ...")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Dauerbetrieb: regelmäßig prüfen + täglicher Bericht")
    s = sub.add_parser("check", help="Einmalige Prüfung")
    s.add_argument("--card", action="append", help="Nur diese Karte(n) (Key), mehrfach möglich")
    s = sub.add_parser("report", help="Bericht erzeugen")
    s.add_argument("--send", action="store_true", help="Zusammenfassung auch verschicken")
    sub.add_parser("validate", help="Konfiguration prüfen und anzeigen")
    sub.add_parser("test-notify", help="Testnachricht an alle Kanäle senden")
    s = sub.add_parser("history", help="Preisverlauf einer Karte anzeigen")
    s.add_argument("card", help="Karten-Key")
    s.add_argument("--days", type=int, default=30)
    s = sub.add_parser("export", help="Preisverlauf als CSV exportieren")
    s.add_argument("card", help="Karten-Key")
    s.add_argument("-o", "--output", default="history.csv")
    s = sub.add_parser("purchases", help="(Simulierte) Käufe anzeigen")
    s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("serve", help="Berichte per HTTP ausliefern")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    return p


COMMANDS = {
    "run": cmd_run,
    "check": cmd_check,
    "report": cmd_report,
    "validate": cmd_validate,
    "test-notify": cmd_test_notify,
    "history": cmd_history,
    "export": cmd_export,
    "purchases": cmd_purchases,
    "serve": cmd_serve,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"✘ {exc}", file=sys.stderr)
        return 2
    _setup_logging(args.log_level or cfg.general.log_level)
    return COMMANDS[args.command](cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
