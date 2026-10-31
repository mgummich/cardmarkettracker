"""Official Cardmarket API (MKM API v2.0, OAuth 1.0a)."""

from __future__ import annotations

import logging
from typing import Any
from xml.sax.saxutils import escape

import httpx

from ..config import CardConfig, MkmApiConfig, OfferFilter
from ..constants import LANGUAGE_IDS, normalize_country, normalize_language
from ..i18n import _
from ..models import MarketData, Offer, PriceGuide
from .base import PriceProvider, ProviderError
from .oauth import build_auth_header

log = logging.getLogger(__name__)

PAGE_SIZE = 100
WEBSITE_BASE = "https://www.cardmarket.com"
_SELLER_TYPES = {0: "private", 1: "professional", 2: "powerseller"}


def _first(guide: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = guide.get(key)
        if value not in (None, "", 0):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def parse_price_guide(guide: dict[str, Any] | None, foil: bool) -> PriceGuide:
    guide = guide or {}
    if foil:
        return PriceGuide(
            trend=_first(guide, "TRENDFOIL", "TREND-FOIL", "FOILTREND"),
            avg1=_first(guide, "FOILAVG1", "AVG1-FOIL", "AVG1FOIL"),
            avg7=_first(guide, "FOILAVG7", "AVG7-FOIL", "AVG7FOIL"),
            avg30=_first(guide, "FOILAVG30", "AVG30-FOIL", "AVG30FOIL"),
            low=_first(guide, "LOWFOIL", "LOW-FOIL", "FOILLOW"),
        )
    return PriceGuide(
        trend=_first(guide, "TREND"),
        avg1=_first(guide, "AVG1"),
        avg7=_first(guide, "AVG7"),
        avg30=_first(guide, "AVG30"),
        low=_first(guide, "LOW", "LOWEX"),
    )


def parse_article(a: dict[str, Any]) -> Offer:
    seller = a.get("seller") or {}
    country_raw = (seller.get("address") or {}).get("country") or seller.get("country")
    try:
        country = normalize_country(country_raw) if country_raw else None
    except ValueError:
        country = None
    lang_info = a.get("language") or {}
    try:
        language = normalize_language(
            lang_info.get("idLanguage") or lang_info.get("languageName") or ""
        )
    except ValueError:
        language = None
    return Offer(
        article_id=str(a["idArticle"]) if a.get("idArticle") is not None else None,
        price=float(a["price"]),
        seller=str(seller.get("username") or "?"),
        seller_country=country,
        seller_type=_SELLER_TYPES.get(seller.get("isCommercial")),
        language=language,
        condition=a.get("condition"),
        foil=bool(a.get("isFoil")),
        signed=bool(a.get("isSigned")),
        altered=bool(a.get("isAltered")),
        first_edition=bool(a.get("isFirstEd")),
        quantity=int(a.get("count") or 1),
        comment=a.get("comments") or None,
    )


class MkmApiClient:
    def __init__(self, cfg: MkmApiConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self.base_url = cfg.base_url.rstrip("/")
        self._http = httpx.Client(timeout=cfg.timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        content: str | None = None,
    ) -> tuple[Any, int]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        str_params = {k: str(v) for k, v in (params or {}).items()}
        auth = build_auth_header(
            method,
            url,
            self.cfg.app_token,
            self.cfg.app_secret,
            self.cfg.access_token,
            self.cfg.access_token_secret,
            params=str_params,
        )
        headers = {"Authorization": auth}
        if content is not None:
            headers["Content-Type"] = "application/xml"
        try:
            resp = self._http.request(
                method, url, params=str_params or None, content=content, headers=headers
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                _("Network error talking to the Cardmarket API: {error}").format(error=exc)
            ) from exc

        if resp.status_code == 204:
            return None, 204
        if resp.status_code in (401, 403):
            raise ProviderError(
                _("Cardmarket API: authentication failed ({status}). Check your tokens.").format(
                    status=resp.status_code
                )
            )
        if resp.status_code == 429:
            raise ProviderError(_("Cardmarket API: daily request limit reached (429)."))
        if resp.status_code >= 400:
            raise ProviderError(
                f"Cardmarket-API {method} {path}: HTTP {resp.status_code} {resp.text[:200]}"
            )
        try:
            return resp.json(), resp.status_code
        except ValueError as exc:
            raise ProviderError(_("Cardmarket API returned invalid JSON")) from exc

    def get_product(self, product_id: int) -> dict[str, Any]:
        data, _status = self.request("GET", f"products/{product_id}")
        if not data or "product" not in data:
            raise ProviderError(_("Product {id} not found").format(id=product_id))
        return data["product"]

    def get_articles(
        self, product_id: int, params: dict[str, Any], max_articles: int
    ) -> list[dict[str, Any]]:
        articles: list[dict[str, Any]] = []
        start = 0
        while len(articles) < max_articles:
            page_params = {**params, "start": start, "maxResults": PAGE_SIZE}
            data, status = self.request("GET", f"articles/{product_id}", page_params)
            if not data:
                break
            batch = data.get("article") or []
            articles.extend(batch)
            # 206 = Partial Content -> es gibt weitere Seiten
            if status != 206 or len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE
        return articles[:max_articles]

    def add_to_cart(self, article_id: str, amount: int) -> Any:
        body = (
            '<?xml version="1.0" encoding="UTF-8" ?>'
            "<request><action>add</action>"
            f"<article><idArticle>{escape(str(article_id))}</idArticle>"
            f"<amount>{int(amount)}</amount></article></request>"
        )
        data, _status = self.request("PUT", "shoppingcart", content=body)
        return data


def article_query_params(filters: OfferFilter) -> dict[str, Any]:
    """Serverseitige Vorfilterung (nur was die API sicher unterstützt)."""
    params: dict[str, Any] = {}
    if filters.languages and len(filters.languages) == 1:
        params["idLanguage"] = LANGUAGE_IDS[filters.languages[0]]
    if filters.min_condition:
        params["minCondition"] = filters.min_condition
    for attr, name in (("foil", "isFoil"), ("signed", "isSigned"), ("altered", "isAltered")):
        value = getattr(filters, attr)
        if value is not None:
            params[name] = "true" if value else "false"
    return params


class MkmApiProvider(PriceProvider):
    name = "mkm_api"

    def __init__(self, cfg: MkmApiConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self.client = MkmApiClient(cfg, transport=transport)

    def fetch(self, card: CardConfig, filters: OfferFilter) -> MarketData:
        if card.product_id is None:
            raise ProviderError(_("Card '{name}' has no product_id").format(name=card.name))
        product = self.client.get_product(card.product_id)
        raw = self.client.get_articles(
            card.product_id, article_query_params(filters), self.cfg.max_articles
        )
        offers = []
        for a in raw:
            try:
                offers.append(parse_article(a))
            except (KeyError, TypeError, ValueError) as exc:
                log.debug("Skipped article (%s): %s", exc, a)
        website = product.get("website")
        return MarketData(
            offers=offers,
            price_guide=parse_price_guide(product.get("priceGuide"), foil=filters.foil is True),
            product_name=product.get("enName") or product.get("locName"),
            product_url=(WEBSITE_BASE + website) if website else card.url,
            total_available=product.get("countArticles"),
        )

    def close(self) -> None:
        self.client.close()
