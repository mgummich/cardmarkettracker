"""Command line: ``cmtracker <command>``."""

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
from .i18n import _, set_language
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


# ---------------------------------------------------------------------- Commands


def cmd_validate(cfg: AppConfig, args: argparse.Namespace) -> int:
    print(
        "✔ "
        + _("Configuration valid – provider: {provider}, {n} cards").format(
            provider=cfg.provider.type, n=len(cfg.cards)
        )
    )
    for card in cfg.cards:
        f = cfg.card_filters(card)
        a = cfg.card_alerts(card)
        state = "" if card.enabled else " " + _("(disabled)")
        print(f"  • {card.key}{state}: {card.name}")
        print(f"      {_('Filters')}: {f.model_dump(exclude_none=True) or '-'}")
        print(f"      {_('Alerts')}: {a.model_dump(exclude_none=True)}")
        if card.buy.enabled:
            print(
                "      "
                + _("Buy: up to {price}, {qty} pcs.").format(
                    price=eur(card.buy.max_price), qty=card.buy.quantity
                )
            )
    channels = [n.type for n in cfg.notifications] or ["console"]
    print("  " + _("Notifications: {channels}").format(channels=", ".join(channels)))
    p = cfg.purchasing
    print(
        "  "
        + _("Auto-buy: {state} (mode {mode}, max {run}/check, {month}/month)").format(
            state=_("ON") if p.enabled else _("off"),
            mode=p.mode,
            run=eur(p.max_per_run),
            month=eur(p.max_per_month),
        )
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
            f"✔ {r.card_key}: "
            + _("{matching}/{total} offers, from {price}, trend {trend}").format(
                matching=s.offer_count,
                total=s.total_offer_count,
                price=eur(s.min_price),
                trend=eur(s.price_guide.trend),
            )
        )
        if s.cheapest:
            print("    " + _("cheapest: {offer}").format(offer=describe_offer(s.cheapest)))
        for a in r.alerts_sent:
            print(f"    🔔 {a.reason}")
        for decision, result in r.purchases:
            print(f"    🛒 {decision.quantity}x {eur(decision.offer.price)} → {result.status}")
    return 1 if results and all(r.error for r in results) else 0


def _serve(cfg: AppConfig, args: argparse.Namespace, schedule: bool) -> int:
    from .runtime import Runner

    runner = Runner(args.config, schedule=schedule)
    web_enabled = cfg.web.enabled and not getattr(args, "no_web", False)
    host = args.host or cfg.web.host
    port = args.port or cfg.web.port
    if web_enabled and host not in ("127.0.0.1", "localhost", "::1") and not cfg.web.password:
        log.warning(_("Web UI reachable on %s without a password – set web.password!"), host)
    if not web_enabled:
        if not schedule:
            print("✘ " + _("The web UI is disabled (web.enabled: false)."), file=sys.stderr)
            return 2
        stop = threading.Event()

        def handle(signum, frame):  # noqa: ARG001
            log.info(_("Received signal %s – shutting down…"), signum)
            stop.set()

        signal.signal(signal.SIGTERM, handle)
        signal.signal(signal.SIGINT, handle)
        runner.start()
        stop.wait()
        runner.stop()
        return 0

    from .web import serve

    runner.start()
    try:
        serve(args.config, runner, host, port)  # returns on SIGINT/SIGTERM
    finally:
        log.info(_("Stopping background service…"))
        runner.stop()
    return 0


def cmd_run(cfg: AppConfig, args: argparse.Namespace) -> int:
    return _serve(cfg, args, schedule=True)


def cmd_web(cfg: AppConfig, args: argparse.Namespace) -> int:
    return _serve(cfg, args, schedule=False)


def cmd_report(cfg: AppConfig, args: argparse.Namespace) -> int:
    app = _app(cfg)
    try:
        path = app.run_report(send=args.send)
    finally:
        app.close()
    print(_("Report: {path}").format(path=path))
    return 0


def cmd_test_notify(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .notifiers import Notification, create_hub

    hub = create_hub(cfg.notifications)
    ok = 0
    for event in ("alert", "report", "purchase", "error"):
        ok += hub.send(
            Notification(
                _("Test ({event})").format(event=event),
                _("Test message from Cardmarket Tracker – the connection works. ✔"),
                event=event,
                url="https://www.cardmarket.com",
            )
        )
    hub.close()
    print(_("{n} test messages delivered (see log for details).").format(n=ok))
    return 0 if ok else 1


def cmd_history(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .storage import Storage

    storage = Storage(cfg.general.database)
    rows = storage.history(args.card, utcnow() - timedelta(days=args.days))
    if not rows:
        print(_("No data."))
        return 1
    print(f"{_('Time'):<17} {_('Low'):>11} {'Ø5':>11} {_('Trend'):>11} {'Δ':>9} {_('Offers'):>7}")
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
    print(_("Exported {n} data points to {path}.").format(n=n, path=args.output))
    return 0


def cmd_purchases(cfg: AppConfig, args: argparse.Namespace) -> int:
    from .storage import Storage

    storage = Storage(cfg.general.database)
    rows = storage.purchases(args.limit)
    if not rows:
        print(_("No purchases (or simulated purchases) yet."))
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
    print(
        _("Reports at {url} (Ctrl+C to stop)").format(
            url=f"http://{args.host}:{args.port}/latest.html"
        )
    )
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


# ---------------------------------------------------------------------- Parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cmtracker", description="Cardmarket price tracker")
    p.add_argument(
        "-c",
        "--config",
        default=os.environ.get("CMTRACKER_CONFIG", "config.yaml"),
        help="path to config.yaml (default: $CMTRACKER_CONFIG or ./config.yaml)",
    )
    p.add_argument("--log-level", help="DEBUG, INFO, WARNING, ...")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("run", help="continuous operation: schedule + web UI")
    s.add_argument("--no-web", action="store_true", help="without web UI")
    s.add_argument("--host", help="web UI address (default: web.host)")
    s.add_argument("--port", type=int, help="web UI port (default: web.port)")
    s = sub.add_parser("web", help="web UI only (checks only on demand)")
    s.add_argument("--host", help="address (default: web.host)")
    s.add_argument("--port", type=int, help="port (default: web.port)")
    s = sub.add_parser("check", help="check once")
    s.add_argument("--card", action="append", help="only this card key (repeatable)")
    s = sub.add_parser("report", help="generate report")
    s.add_argument("--send", action="store_true", help="also send the summary")
    sub.add_parser("validate", help="validate and show configuration")
    sub.add_parser("test-notify", help="send a test message to all channels")
    s = sub.add_parser("history", help="show price history of a card")
    s.add_argument("card", help="card key")
    s.add_argument("--days", type=int, default=30)
    s = sub.add_parser("export", help="export price history as CSV")
    s.add_argument("card", help="card key")
    s.add_argument("-o", "--output", default="history.csv")
    s = sub.add_parser("purchases", help="show (simulated) purchases")
    s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("serve", help="serve the report directory via HTTP")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    return p


COMMANDS = {
    "run": cmd_run,
    "web": cmd_web,
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
    set_language(os.environ.get("CMTRACKER_LANGUAGE"))
    if args.command in ("run", "web"):
        from .runtime import ensure_config

        ensure_config(args.config)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"✘ {exc}", file=sys.stderr)
        return 2
    set_language(cfg.general.language)
    _setup_logging(args.log_level or cfg.general.log_level)
    return COMMANDS[args.command](cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
