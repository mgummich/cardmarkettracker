from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cmtracker.config import parse_config
from cmtracker.models import MarketData, Offer, PriceGuide
from cmtracker.notifiers import Notification, NotificationHub, Notifier
from cmtracker.providers.base import PriceProvider
from cmtracker.storage import Storage


class RecordingNotifier(Notifier):
    def __init__(self):
        super().__init__("recorder", ["alert", "report", "purchase", "error"])
        self.sent: list[Notification] = []

    def send(self, n: Notification) -> None:
        self.sent.append(n)


class FakeProvider(PriceProvider):
    """Liefert pro Karte die jeweils nächste vorbereitete MarketData."""

    name = "fake"

    def __init__(self):
        self.queue: dict[str, list[MarketData]] = {}

    def push(self, key: str, market: MarketData) -> None:
        self.queue.setdefault(key, []).append(market)

    def fetch(self, card, filters):
        items = self.queue.get(card.key)
        if not items:
            raise RuntimeError("keine Daten")
        return items.pop(0) if len(items) > 1 else items[0]


def offer(price, **kw) -> Offer:
    defaults = dict(
        seller="s",
        article_id=f"a{price}",
        language="German",
        condition="NM",
        seller_country="DE",
        seller_type="private",
    )
    defaults.update(kw)
    return Offer(price=price, **defaults)


def market(prices, trend=None, **kw) -> MarketData:
    return MarketData(
        offers=[offer(p, **kw) for p in prices],
        price_guide=PriceGuide(trend=trend, avg30=trend),
        product_url="https://example.com/card",
    )


@pytest.fixture
def storage():
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def recorder():
    return RecordingNotifier()


@pytest.fixture
def hub(recorder):
    return NotificationHub([recorder])


@pytest.fixture
def make_config():
    def _make(**overrides):
        data = {
            "provider": {"type": "demo"},
            "cards": [{"name": "Test Card", "key": "test"}],
        }
        data.update(overrides)
        return parse_config(data)

    return _make


T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
