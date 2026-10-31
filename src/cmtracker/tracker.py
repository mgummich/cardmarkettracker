"""Kernlogik: Karte abrufen → filtern → speichern → Alerts → ggf. kaufen."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from .alerts import TriggeredRule, evaluate_rules, format_alert, should_send
from .config import AppConfig, CardConfig
from .filters import build_snapshot, filter_offers
from .formatting import describe_offer, eur
from .models import Snapshot, utcnow
from .notifiers import Notification, NotificationHub
from .providers import PriceProvider
from .purchasing import PurchaseDecision, Purchaser, PurchaseResult, plan_purchases
from .storage import REAL_PURCHASE_STATUSES, SIMULATED_STATUSES, Storage

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CheckResult:
    card_key: str
    snapshot: Snapshot | None = None
    alerts_sent: list[TriggeredRule] = field(default_factory=list)
    purchases: list[tuple[PurchaseDecision, PurchaseResult]] = field(default_factory=list)
    error: str | None = None


class Tracker:
    def __init__(
        self,
        cfg: AppConfig,
        storage: Storage,
        provider: PriceProvider,
        hub: NotificationHub,
        purchaser: Purchaser | None = None,
    ):
        self.cfg = cfg
        self.storage = storage
        self.provider = provider
        self.hub = hub
        self.purchaser = purchaser

    # ------------------------------------------------------------------ Öffentlich

    def check_all(self, only: list[str] | None = None) -> list[CheckResult]:
        cards = [c for c in self.cfg.cards if c.enabled and (not only or c.key in only)]
        budget = self._initial_budget()
        results = []
        for card in cards:
            result, spent = self._check_card_safe(card, budget)
            budget -= spent
            results.append(result)
        return results

    def check_card(self, card: CardConfig) -> CheckResult:
        result, _ = self._check_card_safe(card, self._initial_budget())
        return result

    # ------------------------------------------------------------------ Intern

    def _check_card_safe(self, card: CardConfig, budget: float) -> tuple[CheckResult, float]:
        try:
            outcome = self._check_card(card, budget)
            self.storage.set_card_status(card.key, None)
            return outcome
        except Exception as exc:  # noqa: BLE001 - eine Karte darf den Lauf nicht abbrechen
            log.error("Fehler bei '%s': %s", card.name, exc)
            self.storage.set_card_status(card.key, str(exc))
            if self.cfg.general.notify_errors:
                self.hub.send(
                    Notification(f"Fehler bei {card.name}", str(exc), event="error", url=card.url)
                )
            return CheckResult(card.key, error=str(exc)), 0.0

    def _check_card(self, card: CardConfig, budget: float) -> tuple[CheckResult, float]:
        now = utcnow()
        filters = self.cfg.card_filters(card)
        market = self.provider.fetch(card, filters)
        matching = filter_offers(market.offers, filters)

        previous = self.storage.latest_snapshot(card.key)
        atl = self.storage.all_time_low(card.key)
        snap = build_snapshot(card.key, market, matching, now, self.cfg.general.keep_offers)
        if snap.product_url is None:
            snap.product_url = card.url
        self.storage.save_snapshot(snap)
        log.info(
            "%s: %d/%d passende Angebote, ab %s (Trend %s)",
            card.name,
            snap.offer_count,
            snap.total_offer_count,
            eur(snap.min_price),
            eur(snap.price_guide.trend),
        )

        result = CheckResult(card.key, snapshot=snap)
        result.alerts_sent = self._handle_alerts(card, snap, previous, atl, now)

        spent = 0.0
        if self.cfg.purchasing.enabled and card.buy.enabled and self.purchaser:
            buy_offers = filter_offers(market.offers, self.cfg.card_buy_filters(card))
            result.purchases, spent = self._handle_purchases(card, buy_offers, budget)
        return result, spent

    def _handle_alerts(
        self,
        card: CardConfig,
        snap: Snapshot,
        previous: Snapshot | None,
        atl: float | None,
        now: datetime,
    ) -> list[TriggeredRule]:
        rules = self.cfg.card_alerts(card)
        hits = evaluate_rules(rules, snap, previous, atl)
        to_send = [
            h
            for h in hits
            if should_send(h, self.storage.last_alert(card.key, h.rule), rules.cooldown_hours, now)
        ]
        if not to_send:
            return []
        title, body = format_alert(card, snap, to_send)
        self.hub.send(Notification(title, body, event="alert", url=snap.product_url))
        for hit in to_send:
            self.storage.record_alert(card.key, hit.rule, hit.price, hit.reason)
        return to_send

    # ------------------------------------------------------------------ Kauf

    def _statuses(self) -> tuple[str, ...]:
        return (
            SIMULATED_STATUSES
            if self.cfg.purchasing.mode == "dry_run"
            else (REAL_PURCHASE_STATUSES)
        )

    def _initial_budget(self) -> float:
        p = self.cfg.purchasing
        if not p.enabled:
            return 0.0
        month_start = utcnow().replace(day=1, hour=0, minute=0, second=0)
        spent_month = self.storage.spent_since(month_start, self._statuses())
        return max(0.0, min(p.max_per_run, p.max_per_month - spent_month))

    def _handle_purchases(
        self, card: CardConfig, offers: list, budget: float
    ) -> tuple[list[tuple[PurchaseDecision, PurchaseResult]], float]:
        assert self.purchaser is not None
        decisions = plan_purchases(
            card.key,
            card.buy,
            offers,
            already_bought=self.storage.bought_quantity(card.key, self._statuses()),
            handled_article_ids=self.storage.handled_article_ids(card.key),
            budget_left=budget,
        )
        done = []
        spent = 0.0
        for decision in decisions:
            result = self.purchaser.execute(decision)
            offer = decision.offer
            self.storage.record_purchase(
                card.key,
                offer.article_id,
                offer.seller,
                offer.price,
                decision.quantity,
                self.purchaser.mode,
                result.status,
                result.detail,
            )
            if result.status != "failed":
                spent += decision.total
            label = {
                "simulated": "Kauf simuliert",
                "in_cart": "In den Warenkorb gelegt",
                "ordered": "Gekauft",
                "failed": "Kauf fehlgeschlagen",
            }.get(result.status, result.status)
            body = (
                f"{decision.quantity}x {describe_offer(offer)}\n"
                f"Summe: {eur(decision.total)} (zzgl. Versand)\n{result.detail}"
            )
            event = "error" if result.status == "failed" else "purchase"
            self.hub.send(Notification(f"{label}: {card.name}", body, event=event, url=card.url))
            done.append((decision, result))
        return done, spent
