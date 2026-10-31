"""Gemeinsame Schnittstelle aller Datenquellen."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import CardConfig, OfferFilter
from ..models import MarketData


class ProviderError(Exception):
    """Fehler beim Abrufen von Daten (Netzwerk, Auth, Parsing, ...)."""


class PriceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, card: CardConfig, filters: OfferFilter) -> MarketData:
        """Liefert Angebote + Preisübersicht für eine Karte.

        ``filters`` darf zur serverseitigen Vorfilterung genutzt werden; der Tracker
        filtert das Ergebnis anschließend ohnehin noch einmal lokal.
        """

    def close(self) -> None:  # noqa: B027 - optional zu überschreiben
        """Ressourcen freigeben (optional)."""
