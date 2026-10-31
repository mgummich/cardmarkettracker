import httpx

from cmtracker.config import CardConfig, MkmApiConfig, OfferFilter
from cmtracker.providers.mkm_api import MkmApiProvider, article_query_params

CFG = MkmApiConfig(
    app_token="a", app_secret="b", access_token="c", access_token_secret="d", max_articles=150
)


def make_article(i, price):
    return {
        "idArticle": i,
        "price": price,
        "count": 2,
        "condition": "NM",
        "language": {"idLanguage": 3, "languageName": "German"},
        "isFoil": False,
        "isSigned": False,
        "isAltered": False,
        "isFirstEd": False,
        "comments": "top",
        "seller": {"username": f"u{i}", "isCommercial": 1, "address": {"country": "D"}},
    }


def test_fetch_product_and_paginated_articles():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"].startswith("OAuth realm=")
        if request.url.path.endswith("/products/42"):
            return httpx.Response(
                200,
                json={
                    "product": {
                        "enName": "Black Lotus",
                        "website": "/en/Magic/Products/Singles/LEA/Black-Lotus",
                        "priceGuide": {
                            "TREND": 100.5,
                            "AVG30": 99,
                            "AVG7": 98,
                            "AVG1": 97,
                            "LOW": 80,
                            "TRENDFOIL": 300,
                        },
                    }
                },
            )
        start = int(request.url.params["start"])
        assert request.url.params["idLanguage"] == "3"
        assert request.url.params["minCondition"] == "EX"
        if start == 0:
            return httpx.Response(
                206, json={"article": [make_article(i, 100 + i) for i in range(100)]}
            )
        return httpx.Response(200, json={"article": [make_article(1000, 90.0)]})

    provider = MkmApiProvider(CFG, transport=httpx.MockTransport(handler))
    data = provider.fetch(
        CardConfig(name="Black Lotus", product_id=42),
        OfferFilter(languages=["German"], min_condition="EX"),
    )
    assert len(data.offers) == 101
    assert data.price_guide.trend == 100.5 and data.price_guide.avg30 == 99
    assert (
        data.product_url == "https://www.cardmarket.com/en/Magic/Products/Singles/LEA/Black-Lotus"
    )
    o = data.offers[-1]
    assert (o.price, o.seller_country, o.seller_type, o.language) == (
        90.0,
        "DE",
        "professional",
        "German",
    )
    assert o.article_id == "1000" and o.quantity == 2


def test_foil_price_guide_and_params():
    params = article_query_params(OfferFilter(languages=["de", "en"], foil=True, signed=False))
    assert params == {"isFoil": "true", "isSigned": "false"}


def test_auth_error_is_provider_error():
    import pytest

    from cmtracker.providers import ProviderError

    provider = MkmApiProvider(CFG, transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(ProviderError, match="authentication failed"):
        provider.fetch(CardConfig(name="X", product_id=1), OfferFilter())


def test_add_to_cart_sends_xml():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"shoppingCart": []})

    provider = MkmApiProvider(CFG, transport=httpx.MockTransport(handler))
    provider.client.add_to_cart("123", 2)
    assert seen["method"] == "PUT"
    assert "<idArticle>123</idArticle><amount>2</amount>" in seen["body"]
