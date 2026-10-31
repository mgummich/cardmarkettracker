from conftest import offer

from cmtracker.config import OfferFilter
from cmtracker.filters import filter_offers, offer_matches


def test_condition_language_and_flags():
    f = OfferFilter(languages=["de"], min_condition="EX", foil=False)
    assert offer_matches(offer(1, condition="NM"), f)
    assert offer_matches(offer(1, condition="EX"), f)
    assert not offer_matches(offer(1, condition="GD"), f)
    assert not offer_matches(offer(1, language="English"), f)
    assert not offer_matches(offer(1, foil=True), f)
    assert not offer_matches(offer(1, condition=None), f)


def test_seller_filters():
    f = OfferFilter(
        seller_countries=["DE", "AT"],
        seller_types=["professional", "powerseller"],
        exclude_sellers=["BadGuy"],
    )
    assert offer_matches(offer(1, seller_type="professional"), f)
    assert not offer_matches(offer(1, seller_type="private"), f)
    assert not offer_matches(offer(1, seller_type="powerseller", seller_country="FR"), f)
    assert not offer_matches(offer(1, seller_type="powerseller", seller="badguy"), f)
    assert not offer_matches(offer(1, seller_type="powerseller", seller_country=None), f)


def test_exclusions_and_min_price():
    f = OfferFilter(exclude_seller_countries=["GB"], min_price=0.5)
    assert offer_matches(offer(1), f)
    assert not offer_matches(offer(1, seller_country="GB"), f)
    assert not offer_matches(offer(0.2), f)


def test_empty_filter_matches_everything_and_sorts():
    result = filter_offers([offer(3), offer(1), offer(2)], OfferFilter())
    assert [o.price for o in result] == [1, 2, 3]
