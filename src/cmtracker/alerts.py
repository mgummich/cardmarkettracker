"""Auswertung der Alert-Regeln und Entprellung (Cooldown)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import AlertRules, CardConfig
from .formatting import describe_offer, eur, pct
from .models import Snapshot
from .storage import AlertRecord

REFERENCE_NAMES = {
    "trend": "Preistrend",
    "avg1": "1-Tages-Durchschnitt",
    "avg7": "7-Tages-Durchschnitt",
    "avg30": "30-Tages-Durchschnitt",
    "low": "ab-Preis",
}


@dataclass(slots=True)
class TriggeredRule:
    rule: str  # max_price | drop_percent | below_reference | all_time_low
    price: float
    reason: str


def evaluate_rules(
    rules: AlertRules,
    snap: Snapshot,
    previous: Snapshot | None,
    all_time_low: float | None,
) -> list[TriggeredRule]:
    """Prüft alle Regeln gegen den aktuellen Snapshot (vor dem Speichern berechnen!)."""
    if not rules.enabled or snap.min_price is None:
        return []
    price = snap.min_price
    hits: list[TriggeredRule] = []

    if rules.max_price is not None and price <= rules.max_price:
        hits.append(TriggeredRule("max_price", price, f"Preis ≤ Zielpreis {eur(rules.max_price)}"))

    if (
        rules.drop_percent is not None
        and previous is not None
        and previous.min_price
        and price <= previous.min_price * (1 - rules.drop_percent / 100)
    ):
        change = (price - previous.min_price) / previous.min_price * 100
        hits.append(
            TriggeredRule(
                "drop_percent",
                price,
                f"{pct(change)} seit letzter Prüfung (vorher {eur(previous.min_price)})",
            )
        )

    ref_value = snap.price_guide.get(rules.reference)
    if (
        rules.below_reference_percent is not None
        and ref_value
        and price <= ref_value * (1 - rules.below_reference_percent / 100)
    ):
        below = (ref_value - price) / ref_value * 100
        name = REFERENCE_NAMES[rules.reference]
        hits.append(
            TriggeredRule(
                "below_reference",
                price,
                f"{pct(below, signed=False)} unter {name} ({eur(ref_value)})",
            )
        )

    if rules.all_time_low and all_time_low is not None and price < all_time_low:
        hits.append(
            TriggeredRule("all_time_low", price, f"Neues Allzeit-Tief (bisher {eur(all_time_low)})")
        )
    return hits


def should_send(
    hit: TriggeredRule, last: AlertRecord | None, cooldown_hours: float, now: datetime
) -> bool:
    """Gleicher Alarm höchstens alle ``cooldown_hours`` – außer der Preis fiel weiter."""
    if last is None:
        return True
    if now - last.sent_at >= timedelta(hours=cooldown_hours):
        return True
    return last.price is not None and hit.price < last.price


def format_alert(card: CardConfig, snap: Snapshot, hits: list[TriggeredRule]) -> tuple[str, str]:
    title = f"Preisalarm: {card.name}"
    lines = []
    if snap.cheapest:
        lines.append(f"Günstigstes passendes Angebot: {describe_offer(snap.cheapest)}")
    lines.append(f"Passende Angebote: {snap.offer_count} (von {snap.total_offer_count})")
    if snap.price_guide.trend:
        lines.append(f"Preistrend: {eur(snap.price_guide.trend)}")
    lines.append("")
    lines.append("Ausgelöst durch:")
    lines.extend(f"• {h.reason}" for h in hits)
    return title, "\n".join(lines)
