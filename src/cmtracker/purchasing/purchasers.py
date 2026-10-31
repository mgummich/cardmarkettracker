"""Executing purchase decisions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..i18n import _
from .planner import PurchaseDecision


@dataclass(slots=True)
class PurchaseResult:
    status: str  # simulated | in_cart | ordered | failed
    detail: str = ""


class Purchaser(ABC):
    mode: str = "base"

    @abstractmethod
    def execute(self, decision: PurchaseDecision) -> PurchaseResult: ...


class DryRunPurchaser(Purchaser):
    mode = "dry_run"

    def execute(self, decision: PurchaseDecision) -> PurchaseResult:
        return PurchaseResult("simulated", _("Dry run – nothing was bought"))


class CartPurchaser(Purchaser):
    """Adds articles to the Cardmarket shopping cart via the API."""

    mode = "cart"

    def __init__(self, client):  # MkmApiClient
        self.client = client

    def execute(self, decision: PurchaseDecision) -> PurchaseResult:
        try:
            self.client.add_to_cart(str(decision.offer.article_id), decision.quantity)
        except Exception as exc:  # noqa: BLE001
            return PurchaseResult("failed", str(exc))
        return PurchaseResult(
            "in_cart", _("Added to cart – complete the payment on cardmarket.com")
        )
