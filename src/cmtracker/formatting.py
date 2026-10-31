"""Locale-aware formatting for messages, reports and the web UI."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .constants import condition_name, country_name, language_name
from .i18n import _, get_language
from .models import Offer

__all__ = [
    "change_pct",
    "condition_name",
    "describe_offer",
    "eur",
    "local_time",
    "pct",
]

# Named date formats per language
_DATE_FORMATS: dict[str, dict[str, str]] = {
    "en": {
        "long": "%Y-%m-%d %H:%M",
        "short": "%m-%d %H:%M",
        "date": "%Y-%m-%d",
        "day": "%m-%d",
        "time": "%H:%M",
        "stamp": "%Y-%m-%d_%H%M",
    },
    "de": {
        "long": "%d.%m.%Y %H:%M",
        "short": "%d.%m. %H:%M",
        "date": "%d.%m.%Y",
        "day": "%d.%m.",
        "time": "%H:%M",
        "stamp": "%Y-%m-%d_%H%M",
    },
}


def eur(value: float | None) -> str:
    """``€1,234.56`` (English) or ``1.234,56 €`` (German)."""
    if value is None:
        return "–"
    if get_language() == "de":
        text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{text} €"
    if value < 0:
        return f"-€{abs(value):,.2f}"
    return f"€{value:,.2f}"


def pct(value: float | None, signed: bool = True) -> str:
    """``+1.5%`` (English) or ``+1,5 %`` (German)."""
    if value is None:
        return "–"
    text = f"{value:+.1f}" if signed else f"{value:.1f}"
    if get_language() == "de":
        return text.replace(".", ",") + " %"
    return text + "%"


def change_pct(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100


def local_time(dt: datetime, tz: str, fmt: str = "long") -> str:
    """Format ``dt`` in time zone ``tz``. ``fmt`` is a named format or a strftime pattern."""
    pattern = _DATE_FORMATS.get(get_language(), _DATE_FORMATS["en"]).get(fmt, fmt)
    return dt.astimezone(ZoneInfo(tz)).strftime(pattern)


def describe_offer(offer: Offer) -> str:
    parts = [eur(offer.price)]
    details = []
    if offer.condition:
        details.append(offer.condition)
    if offer.language:
        details.append(language_name(offer.language))
    for flag, label in (
        ("foil", _("Foil")),
        ("signed", _("signed")),
        ("altered", _("altered")),
        ("first_edition", _("1st ed.")),
    ):
        if getattr(offer, flag):
            details.append(label)
    if details:
        parts.append(f"({', '.join(details)})")
    seller = offer.seller
    if offer.seller_country:
        seller += f", {country_name(offer.seller_country)}"
    parts.append(f"– {seller}")
    if offer.quantity > 1:
        parts.append(_("[{n}x available]").format(n=offer.quantity))
    return " ".join(parts)
