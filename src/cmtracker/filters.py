"""Anwenden der Angebotsfilter.

Grundsatz: Ist ein Filter gesetzt und ein Attribut des Angebots unbekannt, passt das
Angebot *nicht*. Lieber ein Alarm zu wenig als ein Fehlkauf.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime

from .config import OfferFilter
from .constants import condition_rank
from .models import MarketData, Offer, Snapshot


def offer_matches(offer: Offer, f: OfferFilter) -> bool:
    if f.languages is not None and offer.language not in f.languages:
        return False
    if f.min_condition is not None:
        if offer.condition is None:
            return False
        if condition_rank(offer.condition) > condition_rank(f.min_condition):
            return False
    for attr in ("foil", "signed", "altered", "first_edition"):
        wanted = getattr(f, attr)
        if wanted is not None and getattr(offer, attr) != wanted:
            return False
    if f.seller_countries is not None and offer.seller_country not in f.seller_countries:
        return False
    if f.exclude_seller_countries and offer.seller_country in f.exclude_seller_countries:
        return False
    if f.seller_types is not None and offer.seller_type not in f.seller_types:
        return False
    if f.exclude_sellers:
        blocked = {s.lower() for s in f.exclude_sellers}
        if offer.seller.lower() in blocked:
            return False
    return not (f.min_price is not None and offer.price < f.min_price)


def filter_offers(offers: Iterable[Offer], f: OfferFilter) -> list[Offer]:
    """Passende Angebote, aufsteigend nach Preis sortiert."""
    return sorted((o for o in offers if offer_matches(o, f)), key=lambda o: o.price)


def build_snapshot(
    card_key: str,
    market: MarketData,
    matching: list[Offer],
    taken_at: datetime,
    keep_offers: int,
) -> Snapshot:
    prices = [o.price for o in matching]
    return Snapshot(
        card_key=card_key,
        taken_at=taken_at,
        offer_count=len(matching),
        total_offer_count=len(market.offers),
        min_price=prices[0] if prices else None,
        avg5_price=round(statistics.fmean(prices[:5]), 2) if prices else None,
        median_price=round(statistics.median(prices), 2) if prices else None,
        price_guide=market.price_guide,
        offers=matching[:keep_offers],
        product_url=market.product_url,
    )
