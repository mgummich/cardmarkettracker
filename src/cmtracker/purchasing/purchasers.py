"""Ausführung von Kaufentscheidungen."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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
        return PurchaseResult("simulated", "Probelauf – es wurde nichts gekauft")


class CartPurchaser(Purchaser):
    """Legt Artikel über die Cardmarket-API in den Warenkorb."""

    mode = "cart"

    def __init__(self, client):  # MkmApiClient
        self.client = client

    def execute(self, decision: PurchaseDecision) -> PurchaseResult:
        try:
            self.client.add_to_cart(str(decision.offer.article_id), decision.quantity)
        except Exception as exc:  # noqa: BLE001
            return PurchaseResult("failed", str(exc))
        return PurchaseResult(
            "in_cart", "In den Warenkorb gelegt – Bezahlung auf cardmarket.com abschließen"
        )
