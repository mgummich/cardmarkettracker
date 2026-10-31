"""Formatierung für Nachrichten und Berichte (deutsches Zahlenformat)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .constants import CONDITION_NAMES_DE, LANGUAGE_NAMES_DE, country_name_de
from .models import Offer


def eur(value: float | None) -> str:
    if value is None:
        return "–"
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def pct(value: float | None, signed: bool = True) -> str:
    if value is None:
        return "–"
    text = f"{value:+.1f}" if signed else f"{value:.1f}"
    return text.replace(".", ",") + " %"


def change_pct(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100


def local_time(dt: datetime, tz: str, fmt: str = "%d.%m.%Y %H:%M") -> str:
    return dt.astimezone(ZoneInfo(tz)).strftime(fmt)


def describe_offer(offer: Offer) -> str:
    parts = [eur(offer.price)]
    details = []
    if offer.condition:
        details.append(offer.condition)
    if offer.language:
        details.append(LANGUAGE_NAMES_DE.get(offer.language, offer.language))
    for flag, label in (
        ("foil", "Foil"),
        ("signed", "signiert"),
        ("altered", "altered"),
        ("first_edition", "1. Ed."),
    ):
        if getattr(offer, flag):
            details.append(label)
    if details:
        parts.append(f"({', '.join(details)})")
    seller = offer.seller
    if offer.seller_country:
        seller += f", {country_name_de(offer.seller_country)}"
    parts.append(f"– {seller}")
    if offer.quantity > 1:
        parts.append(f"[{offer.quantity}x verfügbar]")
    return " ".join(parts)


def condition_name(code: str | None) -> str:
    return CONDITION_NAMES_DE.get(code or "", code or "–")
