"""Datenaufbereitung für Dashboard und Detailseiten."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..config import AppConfig, CardConfig
from ..formatting import change_pct
from ..i18n import _
from ..models import Snapshot, utcnow
from ..reports import summarize_alerts, summarize_filters
from ..reports.charts import line_chart, sparkline
from ..storage import AlertRecord, PurchaseRecord, Storage

MAX_CHART_POINTS = 400


@dataclass
class CardRow:
    card: CardConfig
    latest: Snapshot | None
    status: dict | None
    change_24h: float | None
    change_7d: float | None
    vs_trend: float | None
    target: float | None
    to_target: float | None  # % bis Zielpreis (negativ = darunter)
    all_time_low: float | None
    alerts_7d: int
    spark: str

    @property
    def state(self) -> str:
        if not self.card.enabled:
            return "paused"
        if self.status and self.status.get("error"):
            return "error"
        if self.latest is None:
            return "new"
        if self.to_target is not None and self.to_target <= 0:
            return "hit"
        return "ok"


@dataclass
class DashboardData:
    rows: list[CardRow]
    alerts: list[AlertRecord]
    purchases: list[PurchaseRecord]
    alerts_24h: int
    hits: int
    errors: int


@dataclass
class CardDetail:
    row: CardRow
    history: list[Snapshot]
    chart: str
    days: int | None
    window_min: float | None
    window_max: float | None
    window_avg: float | None
    alerts: list[AlertRecord] = field(default_factory=list)
    purchases: list[PurchaseRecord] = field(default_factory=list)
    filter_summary: str = ""
    alert_summary: str = ""


def _change(storage: Storage, key: str, current: float | None, ago: datetime) -> float | None:
    old = storage.snapshot_at_or_before(key, ago)
    return change_pct(current, old.min_price if old else None)


def build_row(cfg: AppConfig, storage: Storage, card: CardConfig, now: datetime) -> CardRow:
    latest = storage.latest_snapshot(card.key)
    current = latest.min_price if latest else None
    target = cfg.card_alerts(card).max_price
    week = storage.history(card.key, now - timedelta(days=7))
    return CardRow(
        card=card,
        latest=latest,
        status=storage.card_status(card.key),
        change_24h=_change(storage, card.key, current, now - timedelta(hours=24)),
        change_7d=_change(storage, card.key, current, now - timedelta(days=7)),
        vs_trend=change_pct(current, latest.price_guide.trend) if latest else None,
        target=target,
        to_target=change_pct(current, target) if target else None,
        all_time_low=storage.all_time_low(card.key),
        alerts_7d=len(storage.alerts_since(now - timedelta(days=7), card.key)),
        spark=sparkline([s.min_price for s in _downsample(week, 60)]),
    )


def build_dashboard(cfg: AppConfig, storage: Storage) -> DashboardData:
    now = utcnow()
    rows = [build_row(cfg, storage, card, now) for card in cfg.cards]
    return DashboardData(
        rows=rows,
        alerts=storage.alerts_since(now - timedelta(days=7))[:10],
        purchases=storage.purchases(limit=5),
        alerts_24h=len(storage.alerts_since(now - timedelta(hours=24))),
        hits=sum(1 for r in rows if r.state == "hit"),
        errors=sum(1 for r in rows if r.state == "error"),
    )


def build_detail(
    cfg: AppConfig, storage: Storage, card: CardConfig, days: int | None
) -> CardDetail:
    now = utcnow()
    row = build_row(cfg, storage, card, now)
    since = now - timedelta(days=days) if days else None
    history = storage.history(card.key, since)
    prices = [s.min_price for s in history if s.min_price is not None]
    shown = _downsample(history, MAX_CHART_POINTS)
    target = cfg.card_alerts(card).max_price
    chart = line_chart(
        {
            "low": [(s.taken_at, s.min_price) for s in shown],
            "trend": [(s.taken_at, s.price_guide.trend) for s in shown],
            "avg30": [(s.taken_at, s.price_guide.avg30) for s in shown],
        },
        width=960,
        height=320,
        hover_series="low",
        tz=cfg.general.timezone,
        reference_line=(_("Target"), target) if target else None,
    )
    return CardDetail(
        row=row,
        history=history,
        chart=chart,
        days=days,
        window_min=min(prices) if prices else None,
        window_max=max(prices) if prices else None,
        window_avg=round(statistics.fmean(prices), 2) if prices else None,
        alerts=storage.alerts_since(since or datetime.min.replace(tzinfo=now.tzinfo), card.key)[
            :50
        ],
        purchases=storage.purchases_for(card.key),
        filter_summary=summarize_filters(cfg, card),
        alert_summary=summarize_alerts(cfg, card),
    )


def _downsample(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    step = len(items) / limit
    picked = [items[int(i * step)] for i in range(limit)]
    picked[-1] = items[-1]
    return picked
