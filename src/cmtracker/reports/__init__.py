"""Detailed report on all tracked cards (HTML + text summary)."""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from ..alerts import reference_name
from ..config import AppConfig, CardConfig
from ..constants import condition_name, country_name, language_name
from ..formatting import change_pct, eur, local_time, pct
from ..i18n import _, get_language
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


def summarize_filters(cfg: AppConfig, card: CardConfig) -> str:
    f = cfg.card_filters(card)
    parts = []
    if f.languages:
        parts.append(
            _("Language: {languages}").format(
                languages=", ".join(language_name(x) for x in f.languages)
            )
        )
    if f.min_condition:
        parts.append(_("min. {condition}").format(condition=f.min_condition))
    for attr, yes, no in (
        ("foil", _("Foil"), _("non-foil")),
        ("signed", _("signed"), _("not signed")),
        ("altered", _("altered"), _("not altered")),
        ("first_edition", _("1st edition"), _("no 1st edition")),
    ):
        value = getattr(f, attr)
        if value is not None:
            parts.append(yes if value else no)
    if f.seller_countries:
        parts.append(_("Countries: {list}").format(list=", ".join(f.seller_countries)))
    if f.exclude_seller_countries:
        parts.append(_("excluding: {list}").format(list=", ".join(f.exclude_seller_countries)))
    if f.seller_types:
        parts.append(_("Sellers: {list}").format(list=", ".join(f.seller_types)))
    if f.min_price:
        parts.append(_("from {price}").format(price=eur(f.min_price)))
    return " · ".join(parts) or _("no filters")


def summarize_alerts(cfg: AppConfig, card: CardConfig) -> str:
    r = cfg.card_alerts(card)
    if not r.enabled:
        return _("Alerts disabled")
    parts = []
    if r.max_price:
        parts.append(f"≤ {eur(r.max_price)}")
    if r.drop_percent:
        parts.append(_("drop ≥ {pct}").format(pct=pct(r.drop_percent, signed=False)))
    if r.below_reference_percent:
        parts.append(
            _("≥ {pct} below {reference}").format(
                pct=pct(r.below_reference_percent, signed=False),
                reference=reference_name(r.reference),
            )
        )
    if r.all_time_low:
        parts.append(_("all-time low"))
    return " · ".join(parts) or _("no rules")


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
                filter_summary=summarize_filters(cfg, card),
                alert_summary=summarize_alerts(cfg, card),
                chart_svg=line_chart(
                    {
                        "low": [(s.taken_at, s.min_price) for s in history],
                        "trend": [(s.taken_at, s.price_guide.trend) for s in history],
                        "avg30": [(s.taken_at, s.price_guide.avg30) for s in history],
                    },
                    tz=cfg.general.timezone,
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
    env.filters["country"] = country_name
    env.filters["lang"] = language_name
    env.globals["_"] = _
    return env


def render_html(report: Report, top_offers: int = 5) -> str:
    def fmt_time(dt: datetime, fmt: str = "long") -> str:
        return local_time(dt, report.timezone, fmt)

    return (
        _env()
        .get_template("report.html.j2")
        .render(report=report, top_offers=top_offers, fmt_time=fmt_time, lang=get_language())
    )


def render_text(report: Report, public_url: str | None = None) -> str:
    lines = [
        _("{cards} cards · period {days} days").format(
            cards=len(report.cards), days=report.window_days
        ),
        "",
    ]
    for cr in report.cards:
        if not cr.latest:
            lines.append("• " + _("{name}: no data yet").format(name=cr.card.name))
            continue
        lines.append(
            "• "
            + _(
                "{name}: from {price} (24h {d1}, 7d {d7}) · trend {trend} · {offers} offers"
            ).format(
                name=cr.card.name,
                price=eur(cr.latest.min_price),
                d1=pct(cr.change_24h),
                d7=pct(cr.change_7d),
                trend=eur(cr.latest.price_guide.trend),
                offers=cr.latest.offer_count,
            )
        )
    lines.append("")
    lines.append(_("Alerts in period: {n}").format(n=report.alerts_total))
    if public_url:
        lines.append(_("Full report: {url}").format(url=f"{public_url.rstrip('/')}/latest.html"))
    return "\n".join(lines)


def write_report(report: Report, output_dir: str | Path, top_offers: int = 5) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = render_html(report, top_offers)
    stamp = local_time(report.generated_at, report.timezone, "stamp")
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
                "taken_at",
                "offers_matching",
                "offers_total",
                "min_price",
                "avg5",
                "median",
                "trend",
                "avg1",
                "avg7",
                "avg30",
                "low",
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
