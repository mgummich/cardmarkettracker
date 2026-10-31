"""Ausführlicher Bericht über alle getrackten Karten (HTML + Text-Zusammenfassung)."""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from ..alerts import REFERENCE_NAMES
from ..config import AppConfig, CardConfig
from ..constants import LANGUAGE_NAMES_DE, country_name_de
from ..formatting import change_pct, condition_name, eur, local_time, pct
from ..models import Snapshot, utcnow
from ..storage import AlertRecord, Storage
from .charts import line_chart


@dataclass
class CardReport:
    card: CardConfig
    latest: Snapshot | None
    history: list[Snapshot]
    all_time_low: float | None
    change_24h: float | None
    change_7d: float | None
    change_30d: float | None
    window_min: float | None
    window_max: float | None
    window_avg: float | None
    alerts: list[AlertRecord] = field(default_factory=list)
    filter_summary: str = ""
    alert_summary: str = ""
    chart_svg: str = ""

    @property
    def vs_trend(self) -> float | None:
        if not self.latest:
            return None
        return change_pct(self.latest.min_price, self.latest.price_guide.trend)


@dataclass
class Report:
    generated_at: datetime
    window_days: int
    timezone: str
    cards: list[CardReport]
    alerts_total: int


def _summarize_filters(cfg: AppConfig, card: CardConfig) -> str:
    f = cfg.card_filters(card)
    parts = []
    if f.languages:
        parts.append("Sprache: " + ", ".join(LANGUAGE_NAMES_DE.get(x, x) for x in f.languages))
    if f.min_condition:
        parts.append(f"min. {f.min_condition}")
    for attr, yes, no in (
        ("foil", "Foil", "Non-Foil"),
        ("signed", "signiert", "nicht signiert"),
        ("altered", "altered", "nicht altered"),
        ("first_edition", "1. Edition", "keine 1. Edition"),
    ):
        value = getattr(f, attr)
        if value is not None:
            parts.append(yes if value else no)
    if f.seller_countries:
        parts.append("Länder: " + ", ".join(f.seller_countries))
    if f.exclude_seller_countries:
        parts.append("ohne: " + ", ".join(f.exclude_seller_countries))
    if f.seller_types:
        parts.append("Verkäufer: " + ", ".join(f.seller_types))
    if f.min_price:
        parts.append(f"ab {eur(f.min_price)}")
    return " · ".join(parts) or "keine Filter"


def _summarize_alerts(cfg: AppConfig, card: CardConfig) -> str:
    r = cfg.card_alerts(card)
    if not r.enabled:
        return "Alerts deaktiviert"
    parts = []
    if r.max_price:
        parts.append(f"≤ {eur(r.max_price)}")
    if r.drop_percent:
        parts.append(f"Fall ≥ {pct(r.drop_percent, signed=False)}")
    if r.below_reference_percent:
        parts.append(
            f"≥ {pct(r.below_reference_percent, signed=False)} unter {REFERENCE_NAMES[r.reference]}"
        )
    if r.all_time_low:
        parts.append("Allzeit-Tief")
    return " · ".join(parts) or "keine Regeln"


def build_report(cfg: AppConfig, storage: Storage, now: datetime | None = None) -> Report:
    now = now or utcnow()
    days = cfg.reports.history_days
    since = now - timedelta(days=days)
    cards = []
    alerts_total = 0
    for card in cfg.cards:
        history = storage.history(card.key, since)
        latest = storage.latest_snapshot(card.key)
        prices = [s.min_price for s in history if s.min_price is not None]
        current = latest.min_price if latest else None

        def change(
            delta: timedelta, current: float | None = current, key: str = card.key
        ) -> float | None:
            old = storage.snapshot_at_or_before(key, now - delta)
            return change_pct(current, old.min_price if old else None)

        alerts = storage.alerts_since(since, card.key)
        alerts_total += len(alerts)
        cards.append(
            CardReport(
                card=card,
                latest=latest,
                history=history,
                all_time_low=storage.all_time_low(card.key),
                change_24h=change(timedelta(hours=24)),
                change_7d=change(timedelta(days=7)),
                change_30d=change(timedelta(days=30)),
                window_min=min(prices) if prices else None,
                window_max=max(prices) if prices else None,
                window_avg=round(statistics.fmean(prices), 2) if prices else None,
                alerts=alerts,
                filter_summary=_summarize_filters(cfg, card),
                alert_summary=_summarize_alerts(cfg, card),
                chart_svg=line_chart(
                    {
                        "Tiefstpreis (gefiltert)": [(s.taken_at, s.min_price) for s in history],
                        "Preistrend": [(s.taken_at, s.price_guide.trend) for s in history],
                        "30-Tage-Ø": [(s.taken_at, s.price_guide.avg30) for s in history],
                    }
                ),
            )
        )
    return Report(now, days, cfg.general.timezone, cards, alerts_total)


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("cmtracker.reports", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["eur"] = eur
    env.filters["pct"] = pct
    env.filters["condition"] = condition_name
    env.filters["country"] = country_name_de
    env.filters["lang"] = lambda v: LANGUAGE_NAMES_DE.get(v or "", v or "–")
    return env


def render_html(report: Report, top_offers: int = 5) -> str:
    def fmt_time(dt: datetime, fmt: str = "%d.%m.%Y %H:%M") -> str:
        return local_time(dt, report.timezone, fmt)

    return (
        _env()
        .get_template("report.html.j2")
        .render(report=report, top_offers=top_offers, fmt_time=fmt_time)
    )


def render_text(report: Report, public_url: str | None = None) -> str:
    lines = [f"{len(report.cards)} Karten · Zeitraum {report.window_days} Tage", ""]
    for cr in report.cards:
        if not cr.latest:
            lines.append(f"• {cr.card.name}: noch keine Daten")
            continue
        lines.append(
            f"• {cr.card.name}: ab {eur(cr.latest.min_price)} "
            f"(24h {pct(cr.change_24h)}, 7T {pct(cr.change_7d)}) · "
            f"Trend {eur(cr.latest.price_guide.trend)} · {cr.latest.offer_count} Angebote"
        )
    lines.append("")
    lines.append(f"Alerts im Zeitraum: {report.alerts_total}")
    if public_url:
        lines.append(f"Vollständiger Bericht: {public_url.rstrip('/')}/latest.html")
    return "\n".join(lines)


def write_report(report: Report, output_dir: str | Path, top_offers: int = 5) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = render_html(report, top_offers)
    stamp = local_time(report.generated_at, report.timezone, "%Y-%m-%d_%H%M")
    path = out / f"report_{stamp}.html"
    path.write_text(html, encoding="utf-8")
    (out / "latest.html").write_text(html, encoding="utf-8")
    return path


def export_csv(storage: Storage, card_key: str, path: str | Path) -> int:
    rows = storage.history(card_key)
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "zeitpunkt",
                "angebote_passend",
                "angebote_gesamt",
                "tiefstpreis",
                "avg5",
                "median",
                "trend",
                "avg1",
                "avg7",
                "avg30",
                "ab_preis",
            ]
        )
        for s in rows:
            g = s.price_guide
            writer.writerow(
                [
                    s.taken_at.isoformat(),
                    s.offer_count,
                    s.total_offer_count,
                    s.min_price,
                    s.avg5_price,
                    s.median_price,
                    g.trend,
                    g.avg1,
                    g.avg7,
                    g.avg30,
                    g.low,
                ]
            )
    return len(rows)
