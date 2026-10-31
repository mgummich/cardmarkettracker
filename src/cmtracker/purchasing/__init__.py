"""Automatischer Kauf (experimentell).

Sicherheitsnetz – es wird nur gekauft, wenn ALLES zutrifft:
* ``purchasing.enabled: true`` global
* ``buy.enabled: true`` bei der Karte, mit ``buy.max_price``
* Angebot erfüllt Karten- + Kauf-Filter und kostet <= ``buy.max_price``
* gewünschte Stückzahl (``buy.quantity``) ist noch nicht erreicht
* Budget pro Lauf (``max_per_run``) und pro Kalendermonat (``max_per_month``) reicht

Modi:
* ``dry_run`` – nichts wird gekauft, nur protokolliert und gemeldet (Standard)
* ``cart``    – Artikel wird über die API in den Cardmarket-Warenkorb gelegt.
                Bezahlen musst du weiterhin selbst auf cardmarket.com.
"""

from __future__ import annotations

from .planner import PurchaseDecision, plan_purchases
from .purchasers import CartPurchaser, DryRunPurchaser, Purchaser, PurchaseResult

__all__ = [
    "CartPurchaser",
    "DryRunPurchaser",
    "PurchaseDecision",
    "PurchaseResult",
    "Purchaser",
    "plan_purchases",
]
