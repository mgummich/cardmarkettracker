"""Datenmodelle, die zwischen Providern, Tracker, Speicher und Berichten ausgetauscht werden."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


@dataclass(slots=True)
class Offer:
    """Ein einzelnes Angebot (Artikel) eines Verkäufers."""

    price: float
    seller: str
    article_id: str | None = None
    seller_country: str | None = None  # ISO-2, z.B. "DE"
    seller_type: str | None = None  # private | professional | powerseller
    language: str | None = None  # kanonischer Name, z.B. "German"
    condition: str | None = None  # MT, NM, EX, GD, LP, PL, PO
    foil: bool = False
    signed: bool = False
    altered: bool = False
    first_edition: bool = False
    quantity: int = 1
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Offer:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass(slots=True)
class PriceGuide:
    """Cardmarket-Preisübersicht (Trend, Durchschnitte, ab-Preis)."""

    trend: float | None = None
    avg1: float | None = None
    avg7: float | None = None
    avg30: float | None = None
    low: float | None = None

    def get(self, reference: str) -> float | None:
        return getattr(self, reference, None)


@dataclass(slots=True)
class MarketData:
    """Rohdaten, die ein Provider für eine Karte liefert."""

    offers: list[Offer]
    price_guide: PriceGuide = field(default_factory=PriceGuide)
    product_name: str | None = None
    product_url: str | None = None
    total_available: int | None = None


@dataclass(slots=True)
class Snapshot:
    """Gespeicherter Stand einer Karte zu einem Zeitpunkt (nach Anwendung der Filter)."""

    card_key: str
    taken_at: datetime
    offer_count: int
    total_offer_count: int
    min_price: float | None
    avg5_price: float | None
    median_price: float | None
    price_guide: PriceGuide
    offers: list[Offer] = field(default_factory=list)
    product_url: str | None = None
    id: int | None = None

    @property
    def cheapest(self) -> Offer | None:
        return self.offers[0] if self.offers else None
