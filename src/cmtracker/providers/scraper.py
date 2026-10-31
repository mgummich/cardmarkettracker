"""Fallback: Auslesen der öffentlichen Produktseite auf cardmarket.com.

Hinweise:
* Cardmarket schützt die Seite teilweise per Cloudflare. Bei HTTP 403 hilft oft nur die
  offizielle API (oder ein gültiges ``cf_clearance``-Cookie in ``scraper.cookies``).
* Das HTML kann sich jederzeit ändern – die Selektoren sind bewusst tolerant gehalten.
* Prüfe die Nutzungsbedingungen von Cardmarket; halte ``request_delay_seconds`` großzügig.
"""

from __future__ import annotations

import contextlib
import logging
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag

from ..config import CardConfig, OfferFilter, ScraperConfig
from ..constants import (
    CONDITIONS,
    LANGUAGE_IDS,
    normalize_condition,
    normalize_country,
    normalize_language,
)
from ..models import MarketData, Offer, PriceGuide
from .base import PriceProvider, ProviderError

log = logging.getLogger(__name__)

_SELLER_TYPE_IDS = {"private": 0, "professional": 1, "powerseller": 2}
_LOCATION_RE = re.compile(r"(?:item location|artikelstandort)\s*:\s*(.+)", re.I)
_FLAG_LABELS = {
    "foil": {"foil"},
    "signed": {"signed", "signiert"},
    "altered": {"altered", "verändert", "alteriert"},
    "first_edition": {"first edition", "1st edition", "erstauflage", "1. auflage"},
}
_PROFESSIONAL_LABELS = {"professional", "gewerblich", "gewerblicher verkäufer", "commercial"}
_POWERSELLER_LABELS = {"powerseller", "power seller"}


def parse_price(text: str | None) -> float | None:
    """Parst Preise wie ``1.234,56 €``, ``12,50 €`` oder ``€1,234.56``."""
    if not text:
        return None
    match = re.search(r"\d[\d.,\s  ]*", text)
    if not match:
        return None
    s = re.sub(r"[\s  ]", "", match.group(0)).rstrip(".,")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # "12,50" -> Dezimalkomma, "1,234" -> Tausendertrenner
        tail = s.rsplit(",", 1)[1]
        s = s.replace(",", "") if len(tail) == 3 else s.replace(",", ".")
    elif "." in s and len(s.rsplit(".", 1)[1]) == 3:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _labels(el: Tag | None) -> list[str]:
    """Alle Tooltip-/ARIA-Texte unterhalb eines Elements."""
    if el is None:
        return []
    out: list[str] = []
    for node in [el, *el.find_all(True)]:
        for attr in ("aria-label", "data-bs-original-title", "data-original-title", "title"):
            value = node.get(attr)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
    return out


def _parse_row(row: Tag) -> Offer | None:
    seller_box = row.select_one(".col-seller") or row.select_one(".seller-name")
    seller_link = row.select_one(".seller-name a") or (seller_box.find("a") if seller_box else None)
    seller = seller_link.get_text(strip=True) if seller_link else "?"

    price_el = row.select_one(".price-container") or row.select_one(".col-offer")
    price = parse_price(price_el.get_text(" ", strip=True) if price_el else None)
    if price is None:
        return None

    seller_country = None
    seller_type = "private" if seller_box else None
    for label in _labels(seller_box):
        m = _LOCATION_RE.search(label)
        if m:
            with contextlib.suppress(ValueError):
                seller_country = normalize_country(m.group(1))
        low = label.lower()
        if low in _POWERSELLER_LABELS:
            seller_type = "powerseller"
        elif low in _PROFESSIONAL_LABELS and seller_type != "powerseller":
            seller_type = "professional"

    attrs_box = row.select_one(".product-attributes") or row.select_one(".col-product") or row
    condition = None
    cond_el = attrs_box.select_one(".article-condition")
    if cond_el:
        try:
            condition = normalize_condition(cond_el.get_text(strip=True))
        except ValueError:
            condition = None

    language = None
    flags = dict.fromkeys(_FLAG_LABELS, False)
    for label in _labels(attrs_box):
        low = label.lower()
        for flag, names in _FLAG_LABELS.items():
            if low in names:
                flags[flag] = True
        if language is None:
            with contextlib.suppress(ValueError):
                language = normalize_language(label)

    qty_el = row.select_one(".item-count") or row.select_one(".amount-container span")
    quantity = 1
    if qty_el:
        digits = re.sub(r"\D", "", qty_el.get_text())
        quantity = int(digits) if digits else 1

    comment_el = row.select_one(".product-comments")
    comment = comment_el.get_text(" ", strip=True) if comment_el else None

    row_id = str(row.get("id") or "")
    article_id = row_id.removeprefix("articleRow") or None

    return Offer(
        article_id=article_id,
        price=price,
        seller=seller,
        seller_country=seller_country,
        seller_type=seller_type,
        language=language,
        condition=condition,
        quantity=quantity,
        comment=comment or None,
        **flags,
    )


def parse_product_page(html: str) -> MarketData:
    soup = BeautifulSoup(html, "html.parser")

    name = None
    h1 = soup.select_one(".page-title-container h1") or soup.find("h1")
    if h1:
        first_text = next((s for s in h1.strings if s.strip()), None)
        name = first_text.strip() if first_text else h1.get_text(strip=True)

    guide = PriceGuide()
    total = None
    for dt in soup.select("dl dt"):
        label = dt.get_text(" ", strip=True).lower()
        dd = dt.find_next_sibling("dd")
        if dd is None:
            continue
        text = dd.get_text(" ", strip=True)
        if "trend" in label:
            guide.trend = guide.trend or parse_price(text)
        elif "30" in label:
            guide.avg30 = parse_price(text)
        elif "7" in label:
            guide.avg7 = parse_price(text)
        elif label.startswith("1") or "1-day" in label or "1-tag" in label:
            guide.avg1 = parse_price(text)
        elif label in ("from", "ab"):
            guide.low = parse_price(text)
        elif "available" in label or "verfügbar" in label:
            digits = re.sub(r"\D", "", text)
            total = int(digits) if digits else None

    offers: list[Offer] = []
    for row in soup.select("div.article-row"):
        try:
            offer = _parse_row(row)
        except Exception as exc:  # noqa: BLE001 - einzelne kaputte Zeilen ignorieren
            log.debug("Zeile nicht lesbar: %s", exc)
            continue
        if offer:
            offers.append(offer)

    if not offers and not any((guide.trend, guide.low)) and "cloudflare" in html.lower():
        raise ProviderError("Cloudflare-Schutzseite erhalten – Scraping derzeit blockiert")

    return MarketData(offers=offers, price_guide=guide, product_name=name, total_available=total)


def build_product_url(url: str, filters: OfferFilter, locale: str) -> str:
    parts = urlsplit(url)
    segments = parts.path.split("/")
    if len(segments) > 1 and re.fullmatch(r"[a-z]{2}", segments[1]):
        segments[1] = locale
    query = dict(parse_qsl(parts.query))
    if filters.languages:
        query.setdefault("language", ",".join(str(LANGUAGE_IDS[x]) for x in filters.languages))
    if filters.min_condition:
        query.setdefault("minCondition", str(CONDITIONS.index(filters.min_condition) + 1))
    for attr, name in (
        ("foil", "isFoil"),
        ("signed", "isSigned"),
        ("altered", "isAltered"),
        ("first_edition", "isFirstEd"),
    ):
        value = getattr(filters, attr)
        if value is not None:
            query.setdefault(name, "Y" if value else "N")
    if filters.seller_types:
        query.setdefault(
            "sellerType", ",".join(str(_SELLER_TYPE_IDS[t]) for t in filters.seller_types)
        )
    return urlunsplit(
        (parts.scheme, parts.netloc, "/".join(segments), urlencode(query, safe=","), "")
    )


class ScraperProvider(PriceProvider):
    name = "scraper"

    def __init__(self, cfg: ScraperConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self._last_request = 0.0
        self._http = httpx.Client(
            timeout=cfg.timeout,
            follow_redirects=True,
            transport=transport,
            cookies=cfg.cookies,
            headers={
                "User-Agent": cfg.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": f"{cfg.locale},en;q=0.8",
                **cfg.extra_headers,
            },
        )

    def _throttle(self) -> None:
        wait = self.cfg.request_delay_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def fetch(self, card: CardConfig, filters: OfferFilter) -> MarketData:
        if not card.url:
            raise ProviderError(f"Karte '{card.name}' hat keine url")
        url = build_product_url(card.url, filters, self.cfg.locale)
        self._throttle()
        try:
            resp = self._http.get(url)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Netzwerkfehler: {exc}") from exc
        if resp.status_code in (403, 429, 503):
            raise ProviderError(
                f"cardmarket.com antwortet mit HTTP {resp.status_code} (Bot-Schutz/Rate-Limit). "
                "Intervall erhöhen oder die offizielle API nutzen."
            )
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code} für {url}")
        market = parse_product_page(resp.text)
        market.product_url = str(resp.url)
        return market

    def close(self) -> None:
        self._http.close()
