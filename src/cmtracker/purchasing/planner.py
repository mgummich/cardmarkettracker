"""Entscheidet, welche Angebote gekauft würden."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import BuyRules
from ..models import Offer


@dataclass(slots=True)
class PurchaseDecision:
    card_key: str
    offer: Offer
    quantity: int

    @property
    def total(self) -> float:
        return round(self.offer.price * self.quantity, 2)


def plan_purchases(
    card_key: str,
    rules: BuyRules,
    offers: list[Offer],
    already_bought: int,
    handled_article_ids: set[str],
    budget_left: float,
) -> list[PurchaseDecision]:
    """``offers`` müssen bereits gefiltert sein. Versandkosten werden nicht berücksichtigt."""
    if not rules.enabled or rules.max_price is None:
        return []
    remaining = rules.quantity - already_bought
    decisions: list[PurchaseDecision] = []
    for offer in sorted(offers, key=lambda o: o.price):
        if remaining <= 0 or offer.price > rules.max_price:
            break
        if offer.article_id is None or offer.article_id in handled_article_ids:
            continue
        affordable = int(budget_left // offer.price) if offer.price > 0 else 0
        qty = min(remaining, offer.quantity, affordable)
        if qty <= 0:
            break
        decisions.append(PurchaseDecision(card_key, offer, qty))
        remaining -= qty
        budget_left -= offer.price * qty
    return decisions
