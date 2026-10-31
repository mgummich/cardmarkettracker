from pathlib import Path

import httpx
import pytest

from cmtracker.config import CardConfig, OfferFilter, ScraperConfig
from cmtracker.providers import ProviderError
from cmtracker.providers.scraper import (
    ScraperProvider,
    build_product_url,
    parse_price,
    parse_product_page,
)

HTML = (Path(__file__).parent / "fixtures" / "product_page.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("12,50 €", 12.5),
        ("1.234,56 €", 1234.56),
        ("€1,234.56", 1234.56),
        ("0,02 €", 0.02),
        ("12.50", 12.5),
        ("1.234 €", 1234.0),
        ("ab 3 €", 3.0),
        ("", None),
        ("N/A", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parse_product_page():
    data = parse_product_page(HTML)
    assert data.product_name == "Black Lotus"
    assert data.total_available == 1234
    g = data.price_guide
    assert (g.trend, g.avg30, g.avg7, g.avg1, g.low) == (12345.67, 11500, 11800, 12000.5, 8999)
    assert len(data.offers) == 2
    a, b = data.offers
    assert a.article_id == "111" and a.seller == "CardShopX" and a.price == 9250
    assert (a.seller_country, a.seller_type, a.language, a.condition) == (
        "DE",
        "professional",
        "German",
        "NM",
    )
    assert a.signed and not a.foil and a.quantity == 2 and a.comment == "Top Zustand!"
    assert (b.seller_country, b.seller_type, b.language, b.condition, b.foil) == (
        "FR",
        "private",
        "English",
        "LP",
        True,
    )


def test_build_product_url():
    url = build_product_url(
        "https://www.cardmarket.com/en/Magic/Products/Singles/Alpha/Black-Lotus?sellerCountry=7",
        OfferFilter(
            languages=["de", "en"], min_condition="NM", foil=False, seller_types=["professional"]
        ),
        "de",
    )
    assert url.startswith("https://www.cardmarket.com/de/Magic/Products/Singles/Alpha/Black-Lotus?")
    for part in ("sellerCountry=7", "language=3,1", "minCondition=2", "isFoil=N", "sellerType=1"):
        assert part in url


def test_blocked_request_raises():
    cfg = ScraperConfig(request_delay_seconds=0)
    provider = ScraperProvider(cfg, transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(ProviderError, match="403"):
        provider.fetch(CardConfig(name="X", url="https://www.cardmarket.com/en/X"), OfferFilter())


def test_fetch_parses_response():
    cfg = ScraperConfig(request_delay_seconds=0)
    provider = ScraperProvider(
        cfg, transport=httpx.MockTransport(lambda r: httpx.Response(200, text=HTML))
    )
    data = provider.fetch(
        CardConfig(name="X", url="https://www.cardmarket.com/en/X"), OfferFilter()
    )
    assert len(data.offers) == 2
    assert data.product_url.startswith("https://www.cardmarket.com/en/X")
