"""Demo-Datenquelle: erzeugt plausible, reproduzierbare Fake-Angebote.

Ideal zum Ausprobieren von Alerts, Berichten und Kauf-Logik ohne Cardmarket-Zugang.
"""

from __future__ import annotations

import hashlib
import math
import random

from ..config import CardConfig, DemoConfig, OfferFilter
from ..constants import CONDITIONS
from ..models import MarketData, Offer, PriceGuide, utcnow
from .base import PriceProvider

_LANGS = ["English", "German", "French", "Italian", "Spanish", "Japanese"]
_COUNTRIES = ["DE", "DE", "DE", "AT", "FR", "IT", "ES", "NL", "BE", "GB"]
_SELLER_TYPES = ["private", "private", "professional", "powerseller"]


class DemoProvider(PriceProvider):
    name = "demo"

    def __init__(self, cfg: DemoConfig | None = None):
        self.cfg = cfg or DemoConfig()

    def _base_price(self, key: str) -> float:
        h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        return round(2 + (h % 20000) / 100, 2)

    def fetch(self, card: CardConfig, filters: OfferFilter) -> MarketData:
        now = utcnow()
        hours = int(now.timestamp() // 3600)
        base = self._base_price(card.key or card.name)
        # Wochenzyklus + leichtes Rauschen pro Stunde
        wave = 1 + 0.12 * math.sin(hours / 24 * 2 * math.pi / 7)
        rng = random.Random(f"{self.cfg.seed}-{card.key}-{hours}")
        trend = round(base * wave, 2)

        offers = []
        for i in range(rng.randint(12, 30)):
            price = round(trend * rng.uniform(0.82, 1.6), 2)
            offers.append(
                Offer(
                    article_id=f"demo-{card.key}-{hours}-{i}",
                    price=price,
                    seller=f"seller_{rng.randint(1, 400)}",
                    seller_country=rng.choice(_COUNTRIES),
                    seller_type=rng.choice(_SELLER_TYPES),
                    language=rng.choice(_LANGS),
                    condition=rng.choice(CONDITIONS[:5]),
                    foil=rng.random() < 0.15,
                    quantity=rng.randint(1, 4),
                )
            )
        return MarketData(
            offers=offers,
            price_guide=PriceGuide(
                trend=trend,
                avg1=round(trend * rng.uniform(0.95, 1.05), 2),
                avg7=round(base * 1.01, 2),
                avg30=round(base, 2),
                low=min(o.price for o in offers),
            ),
            product_name=card.name,
            product_url=card.url or "https://www.cardmarket.com",
            total_available=len(offers),
        )
