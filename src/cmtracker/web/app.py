"""FastAPI application: dashboard, card management, settings, JSON API."""

from __future__ import annotations

import base64
import binascii
import logging
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from ruamel.yaml.comments import CommentedMap

from .. import __version__
from ..config import AppConfig, ConfigError, slugify
from ..constants import (
    CONDITIONS,
    COUNTRIES,
    LANGUAGES,
    SELLER_TYPES,
    condition_name,
    country_name,
    language_name,
)
from ..formatting import eur, local_time, pct
from ..i18n import LANGUAGES as UI_LANGUAGES
from ..i18n import _, get_language, negotiate, normalize, set_language
from ..models import utcnow
from ..notifiers import Notification, create_hub
from ..runtime import Runner
from ..storage import Storage
from . import forms
from .config_store import ConfigStore, card_key_of
from .views import build_dashboard, build_detail

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
RANGES = {"7": 7, "30": 30, "90": 90, "365": 365, "all": None}
LANG_COOKIE = "cmtracker_lang"
SELLER_TYPE_NAMES = {
    "private": "Private",
    "professional": "Professional",
    "powerseller": "Powerseller",
}
TASK_NAMES = {"check": "Check running", "report": "Creating report"}


def seller_type_name(value: str | None) -> str:
    return _(SELLER_TYPE_NAMES.get(value or "", value or "–"))


def task_name(value: str | None) -> str:
    return _(TASK_NAMES.get(value or "", "Job queued…"))


SETTINGS_SPECS: dict[str, dict[str, str]] = {
    "general": {
        "language": "str",
        "interval_minutes": "float",
        "jitter_seconds": "float",
        "timezone": "str",
        "keep_offers": "int",
        "notify_errors": "bool",
        "log_level": "str",
    },
    "reports": {
        "daily_time": "optstr",
        "history_days": "int",
        "top_offers": "int",
        "send_summary": "bool",
        "attach_html": "bool",
        "public_url": "optstr",
    },
    "purchasing": {
        "enabled": "bool",
        "mode": "str",
        "max_per_run": "float",
        "max_per_month": "float",
    },
}


def _mask(value: Any, keep: int = 4) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return "•" * len(text)
    return "•" * min(8, len(text) - keep) + text[-keep:]


def describe_target(n: Any) -> str:
    kind = n.type
    if kind == "telegram":
        return _("Chat {id}").format(id=_mask(n.chat_id))
    if kind == "discord":
        return f"Webhook {_mask(n.webhook_url, 6)}"
    if kind == "ntfy":
        return f"{n.server.rstrip('/')}/{_mask(n.topic)}"
    if kind == "email":
        return f"{n.host}:{n.port} → {', '.join(n.recipients)}"
    if kind == "webhook":
        return urlsplit(n.url).netloc or _mask(n.url)
    return _("Log output")


def create_app(config_path: str | Path, runner: Runner | None = None) -> FastAPI:
    store = ConfigStore(config_path)
    app = FastAPI(title="Cardmarket Tracker", version=__version__, docs_url="/api/docs")
    app.state.store = store
    app.state.runner = runner

    templates = Jinja2Templates(directory=str(HERE / "templates"))
    env = templates.env
    env.filters.update(
        eur=eur,
        pct=pct,
        condition=condition_name,
        country=country_name,
        lang=language_name,
        seller_type=seller_type_name,
        task=task_name,
    )
    env.globals.update(
        _=_,
        version=__version__,
        CONDITIONS=CONDITIONS,
        LANGUAGES=list(LANGUAGES.values()),
        COUNTRIES=COUNTRIES,
        SELLER_TYPES=SELLER_TYPES,
        UI_LANGUAGES=UI_LANGUAGES,
        describe_target=describe_target,
    )
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    # ------------------------------------------------------------------ Middleware

    @app.middleware("http")
    async def security(request: Request, call_next):
        try:
            cfg, _cfg_error = store.current()
        except ConfigError:
            cfg = None
        set_language(
            normalize(request.cookies.get(LANG_COOKIE))
            or negotiate(request.headers.get("accept-language"))
            or (cfg.general.language if cfg else None)
        )
        web = cfg.web if cfg else None
        if web and web.password and not _authorized(request, web.username or "admin", web.password):
            return HTMLResponse(
                _("Login required"),
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Cardmarket Tracker", charset="UTF-8"'},
            )
        if request.method not in ("GET", "HEAD", "OPTIONS") and not _same_origin(request):
            return HTMLResponse(_("Invalid request origin (CSRF protection)"), status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    # ------------------------------------------------------------------ Helpers

    def config() -> tuple[AppConfig, str | None]:
        try:
            return store.current()
        except ConfigError as exc:
            raise HTTPException(500, str(exc)) from None

    @contextmanager
    def open_storage(cfg: AppConfig) -> Iterator[Storage]:
        storage = Storage(cfg.general.database)
        try:
            yield storage
        finally:
            storage.close()

    def render(request: Request, template: str, cfg: AppConfig, **ctx: Any) -> HTMLResponse:
        _cfg, cfg_error = store.current()
        status = runner.status if runner else None

        def fmt_time(dt, fmt="long"):
            return local_time(dt, cfg.general.timezone, fmt) if dt else "–"

        return templates.TemplateResponse(
            request,
            template,
            {
                "cfg": cfg,
                "cfg_error": cfg_error or (status.config_error if status else None),
                "runner": status,
                "fmt_time": fmt_time,
                "msg": request.query_params.get("msg"),
                "err": request.query_params.get("err"),
                "nav": template.split(".")[0],
                "lang": get_language(),
                "current_path": request.url.path
                + (f"?{request.url.query}" if request.url.query else ""),
                **ctx,
            },
        )

    def back(url: str, msg: str | None = None, err: str | None = None) -> RedirectResponse:
        url, _sep, fragment = url.partition("#")
        sep = "&" if "?" in url else "?"
        if msg:
            url += f"{sep}msg={quote(msg)}"
        elif err:
            url += f"{sep}err={quote(err)}"
        if fragment:
            url += f"#{fragment}"
        return RedirectResponse(url, status_code=303)

    def save(raw: CommentedMap) -> str | None:
        """Save; returns an error message or None."""
        try:
            store.save(raw)
        except ConfigError as exc:
            return str(exc)
        if runner:
            runner.notify_config_changed()
        return None

    def get_card(cfg: AppConfig, key: str):
        try:
            return cfg.get_card(key)
        except KeyError:
            raise HTTPException(404, _("Card '{key}' not found").format(key=key)) from None

    # ------------------------------------------------------------------ Language

    @app.get("/lang/{code}")
    def switch_language(request: Request, code: str, next: str = "/"):  # noqa: A002
        target = next if next.startswith("/") and not next.startswith("//") else "/"
        response = RedirectResponse(target, status_code=303)
        lang = normalize(code)
        if lang:
            response.set_cookie(
                LANG_COOKIE, lang, max_age=365 * 24 * 3600, samesite="lax", httponly=True
            )
        return response

    # ------------------------------------------------------------------ Dashboard

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        cfg, _cfg_error = config()
        with open_storage(cfg) as storage:
            data = build_dashboard(cfg, storage)
        return render(request, "dashboard.html", cfg, data=data)

    @app.get("/cards/{key}", response_class=HTMLResponse)
    def card_detail(request: Request, key: str, range: str = "30"):  # noqa: A002
        cfg, _cfg_error = config()
        card = get_card(cfg, key)
        days = RANGES.get(range, 30)
        with open_storage(cfg) as storage:
            detail = build_detail(cfg, storage, card, days)
        return render(
            request, "card_detail.html", cfg, d=detail, card=card, range=range, ranges=RANGES
        )

    @app.get("/activity", response_class=HTMLResponse)
    def activity(request: Request):
        cfg, _cfg_error = config()
        with open_storage(cfg) as storage:
            alerts = storage.alerts_since(utcnow().replace(year=2000))[:200]
            purchases = storage.purchases(limit=200)
        names = {c.key: c.name for c in cfg.cards}
        return render(
            request, "activity.html", cfg, alerts=alerts, purchases=purchases, names=names
        )

    # ------------------------------------------------------------------ Aktionen

    @app.post("/check")
    def check_all(request: Request):
        if not runner:
            return back("/", err=_("No background service running"))
        runner.request_check(None)
        return back(_local_referer(request), msg=_("Check of all cards started"))

    @app.post("/cards/{key}/check")
    def check_card(key: str):
        cfg, _cfg_error = config()
        get_card(cfg, key)
        if not runner:
            return back(f"/cards/{key}", err=_("No background service running"))
        runner.request_check([key])
        return back(f"/cards/{key}", msg=_("Check started"))

    @app.post("/report")
    async def make_report(request: Request):
        form = await request.form()
        if not runner:
            return back("/system", err=_("No background service running"))
        runner.request_report(send=form.get("send") == "1")
        return back("/system", msg=_("Creating report"))

    @app.post("/system/test-notify")
    def test_notify():
        cfg, _cfg_error = config()
        hub = create_hub(cfg.notifications)
        try:
            ok = hub.send(
                Notification(
                    _("Test from the web interface"),
                    _("Test message from Cardmarket Tracker – the connection works. ✔"),
                    event="alert",
                )
            )
        finally:
            hub.close()
        if ok:
            return back("/system", msg=_("{n} channel(s) succeeded").format(n=ok))
        return back("/system", err=_("No delivery succeeded – see the log for details"))

    # ------------------------------------------------------------------ Karten bearbeiten

    def card_form(request, cfg, view, is_new, key=None, error=None, error_field=None):
        return render(
            request,
            "card_form.html",
            cfg,
            v=view,
            is_new=is_new,
            key=key,
            error=error,
            error_field=error_field,
            defaults_filters=cfg.defaults.filters,
            defaults_alerts=cfg.defaults.alerts,
        )

    @app.get("/cards-new", response_class=HTMLResponse)
    def new_card_form(request: Request):
        cfg, _cfg_error = config()
        return card_form(request, cfg, forms.card_view({}), is_new=True)

    @app.post("/cards-new", response_class=HTMLResponse)
    async def new_card(request: Request):
        cfg, _cfg_error = config()
        form = await request.form()
        card = CommentedMap()
        try:
            updates = forms.parse_card(form, is_new=True)
            forms.apply_card(card, updates)
        except forms.FormError as exc:
            forms.apply_card(card, {"name": str(form.get("name") or "")})
            return card_form(request, cfg, forms.card_view(card), True, None, str(exc), exc.field)
        raw = store.load_raw()
        key = card_key_of(card)
        if store.find_card(raw, key):
            return card_form(
                request,
                cfg,
                forms.card_view(card),
                True,
                error=_(
                    "A card with the key '{key}' already exists – please choose a different key."
                ).format(key=key),
                error_field="key",
            )
        store.append_card(raw, card)
        if error := save(raw):
            return card_form(request, cfg, forms.card_view(card), True, error=error)
        if runner:
            runner.request_check([key])
        return back(f"/cards/{key}", msg=_("Card created – first check running"))

    @app.get("/cards/{key}/edit", response_class=HTMLResponse)
    def edit_card_form(request: Request, key: str):
        cfg, _cfg_error = config()
        found = store.find_card(store.load_raw(), key)
        if not found:
            raise HTTPException(404, "Karte nicht gefunden")
        return card_form(request, cfg, forms.card_view(found[1]), is_new=False, key=key)

    @app.post("/cards/{key}/edit", response_class=HTMLResponse)
    async def edit_card(request: Request, key: str):
        cfg, _cfg_error = config()
        form = await request.form()
        raw = store.load_raw()
        found = store.find_card(raw, key)
        if not found:
            raise HTTPException(404, "Karte nicht gefunden")
        idx, card = found
        original_view = forms.card_view(card)

        def mutate(edited: CommentedMap) -> None:
            forms.apply_card(edited, forms.parse_card(form, is_new=False))
            if "key" not in edited and slugify(str(edited["name"])) != key:
                edited["key"] = key  # Key stabil halten, damit der Verlauf erhalten bleibt

        try:
            edited = store.update_card(raw, idx, mutate)
        except forms.FormError as exc:
            return card_form(request, cfg, original_view, False, key, str(exc), exc.field)
        if error := save(raw):
            return card_form(request, cfg, forms.card_view(edited), False, key, error)
        return back(f"/cards/{key}", msg=_("Saved"))

    @app.post("/cards/{key}/toggle")
    def toggle_card(key: str):
        raw = store.load_raw()
        found = store.find_card(raw, key)
        if not found:
            raise HTTPException(404, "Karte nicht gefunden")
        idx, card = found
        enabled = card.get("enabled", True) is not False
        store.update_card(
            raw, idx, lambda c: forms.apply(c, {"enabled": False if enabled else forms.POP})
        )
        if error := save(raw):
            return back(f"/cards/{key}", err=error)
        return back(f"/cards/{key}", msg=_("Paused") if enabled else _("Active again"))

    @app.post("/cards/{key}/delete")
    async def delete_card(request: Request, key: str):
        cfg, _cfg_error = config()
        form = await request.form()
        raw = store.load_raw()
        found = store.find_card(raw, key)
        if not found:
            raise HTTPException(404, "Karte nicht gefunden")
        store.delete_card(raw, found[0])
        if error := save(raw):
            return back(f"/cards/{key}", err=error)
        if form.get("purge") == "1":
            with open_storage(cfg) as storage:
                storage.delete_card_data(key)
        return back("/", msg=_("Card deleted"))

    # ------------------------------------------------------------------ Einstellungen

    def settings_page(request, cfg, error=None):
        raw = store.load_raw()

        def section(name: str) -> dict:
            value = raw.get(name)
            return value if isinstance(value, dict) else {}

        defaults = section("defaults")
        provider = section("provider")
        scraper = provider.get("scraper") if isinstance(provider.get("scraper"), dict) else {}
        return render(
            request,
            "settings.html",
            cfg,
            error=error,
            raw={k: section(k) for k in ("general", "reports", "purchasing")},
            env_fields={
                **{
                    name: {k for k, v in section(name).items() if forms.is_env(v)}
                    for name in ("general", "reports", "purchasing", "provider")
                },
                "scraper": {k for k, v in scraper.items() if forms.is_env(v)},
            },
            df=forms.filters_view(defaults.get("filters"), allow_inherit=False),
            da=forms.alerts_view(defaults.get("alerts"), allow_inherit=False),
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request):
        cfg, _cfg_error = config()
        return settings_page(request, cfg)

    @app.post("/settings/{section}", response_class=HTMLResponse)
    async def save_settings(request: Request, section: str):
        cfg, _cfg_error = config()
        form = await request.form()
        raw = store.load_raw()
        try:
            if section in SETTINGS_SPECS:
                forms.apply_section(raw, section, forms.parse_fields(form, SETTINGS_SPECS[section]))
            elif section == "defaults":
                defaults = raw.get("defaults")
                if not isinstance(defaults, dict):
                    defaults = CommentedMap()
                forms.apply_section(defaults, "filters", forms.parse_filters(form, "df_", False))
                forms.apply_section(defaults, "alerts", forms.parse_alerts(form, "da_", False))
                if defaults:
                    raw["defaults"] = defaults
            elif section == "provider":
                provider = raw.get("provider")
                if not isinstance(provider, dict):
                    provider = CommentedMap()
                forms.apply(provider, forms.parse_fields(form, {"type": "str"}))
                forms.apply_section(
                    provider,
                    "scraper",
                    forms.parse_fields(form, {"locale": "str", "request_delay_seconds": "float"}),
                )
                raw["provider"] = provider
            else:
                raise HTTPException(404)
        except forms.FormError as exc:
            return settings_page(request, cfg, error=str(exc))
        if error := save(raw):
            return settings_page(request, cfg, error=error)
        return back(f"/settings#{section}", msg=_("Settings saved"))

    @app.get("/system", response_class=HTMLResponse)
    def system(request: Request):
        cfg, _cfg_error = config()
        out = Path(cfg.reports.output_dir)
        reports = sorted(out.glob("report_*.html"), reverse=True)[:10] if out.exists() else []
        return render(
            request,
            "system.html",
            cfg,
            config_path=store.path.resolve(),
            reports=[p.name for p in reports],
        )

    # ------------------------------------------------------------------ Berichte (Dateien)

    @app.get("/reports/{name}")
    def report_file(name: str):
        cfg, _cfg_error = config()
        if not re.fullmatch(r"[\w\-.]+\.html", name):
            raise HTTPException(404)
        path = Path(cfg.reports.output_dir) / name
        if not path.is_file():
            raise HTTPException(404, "Noch kein Bericht vorhanden")
        return FileResponse(path, media_type="text/html")

    # ------------------------------------------------------------------ JSON-API

    @app.get("/api/status")
    def api_status():
        cfg, cfg_error = config()
        s = runner.status if runner else None
        return {
            "version": __version__,
            "cards": len(cfg.cards),
            "provider": cfg.provider.type,
            "config_error": cfg_error or (s.config_error if s else None),
            "runner": None
            if s is None
            else {
                "scheduling": s.scheduling,
                "running": s.running,
                "busy": s.running or bool(s.pending),
                "current_task": s.current_task,
                "current_task_label": task_name(s.current_task) if s.current_task else None,
                "last_check_at": s.last_check_at,
                "next_check_at": s.next_check_at,
                "last_check_errors": s.last_check_errors,
            },
        }

    @app.get("/api/cards")
    def api_cards():
        cfg, _cfg_error = config()
        with open_storage(cfg) as storage:
            data = build_dashboard(cfg, storage)
        return [
            {
                "key": r.card.key,
                "name": r.card.name,
                "enabled": r.card.enabled,
                "state": r.state,
                "min_price": r.latest.min_price if r.latest else None,
                "trend": r.latest.price_guide.trend if r.latest else None,
                "offer_count": r.latest.offer_count if r.latest else None,
                "checked_at": r.latest.taken_at if r.latest else None,
                "change_24h": r.change_24h,
                "change_7d": r.change_7d,
                "target": r.target,
                "all_time_low": r.all_time_low,
                "error": (r.status or {}).get("error"),
            }
            for r in data.rows
        ]

    @app.get("/api/cards/{key}/history")
    def api_history(key: str, days: int | None = 30):
        cfg, _cfg_error = config()
        get_card(cfg, key)
        with open_storage(cfg) as storage:
            rows = storage.history(key, utcnow() - timedelta(days=days) if days else None)
        return JSONResponse(
            [
                {
                    "taken_at": s.taken_at.isoformat(),
                    "min_price": s.min_price,
                    "avg5_price": s.avg5_price,
                    "median_price": s.median_price,
                    "offer_count": s.offer_count,
                    "trend": s.price_guide.trend,
                    "avg30": s.price_guide.avg30,
                }
                for s in rows
            ]
        )

    return app


# ---------------------------------------------------------------------- Sicherheit


def _authorized(request: Request, username: str, password: str) -> bool:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        user, _sep, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return secrets.compare_digest(user.encode(), username.encode()) and secrets.compare_digest(
        pw.encode(), password.encode()
    )


def _same_origin(request: Request) -> bool:
    """POSTs nur von der eigenen Seite (Schutz vor Cross-Site-Request-Forgery)."""
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source or source == "null":
        return source is None
    return urlsplit(source).netloc == request.headers.get("host", "")


def _local_referer(request: Request) -> str:
    """Path of the referring page if it is our own, else ``/``."""
    referer = urlsplit(request.headers.get("referer") or "")
    if referer.netloc and referer.netloc != request.headers.get("host", ""):
        return "/"
    path = referer.path or "/"
    return path + (f"?{referer.query}" if referer.query else "")
