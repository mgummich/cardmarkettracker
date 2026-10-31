"""Konfiguration (YAML) inklusive Validierung und ``${ENV}``-Ersetzung."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .constants import (
    normalize_condition,
    normalize_country,
    normalize_language,
    normalize_seller_type,
)

Event = Literal["alert", "report", "purchase", "error"]
ALL_EVENTS: list[str] = ["alert", "report", "purchase", "error"]


class ConfigError(Exception):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- Filter / Regeln


class OfferFilter(_Model):
    """Welche Angebote berücksichtigt werden. ``None`` = egal."""

    languages: list[str] | None = None
    min_condition: str | None = None
    foil: bool | None = None
    signed: bool | None = None
    altered: bool | None = None
    first_edition: bool | None = None
    seller_countries: list[str] | None = None
    exclude_seller_countries: list[str] | None = None
    seller_types: list[str] | None = None
    exclude_sellers: list[str] | None = None
    min_price: float | None = Field(default=None, ge=0)

    @field_validator("languages", mode="before")
    @classmethod
    def _langs(cls, v: Any) -> Any:
        if v is None:
            return None
        items = [v] if isinstance(v, str | int) else v
        return [normalize_language(x) for x in items] or None

    @field_validator("min_condition", mode="before")
    @classmethod
    def _cond(cls, v: Any) -> Any:
        return None if v is None else normalize_condition(v)

    @field_validator("seller_countries", "exclude_seller_countries", mode="before")
    @classmethod
    def _countries(cls, v: Any) -> Any:
        if v is None:
            return None
        items = [v] if isinstance(v, str) else v
        return [normalize_country(x) for x in items] or None

    @field_validator("seller_types", mode="before")
    @classmethod
    def _seller_types(cls, v: Any) -> Any:
        if v is None:
            return None
        items = [v] if isinstance(v, str) else v
        return [normalize_seller_type(x) for x in items] or None

    def merged_with(self, override: OfferFilter | None) -> OfferFilter:
        """Felder aus ``override``, die explizit gesetzt wurden, überschreiben ``self``."""
        if override is None:
            return self.model_copy()
        return self.model_copy(update=override.model_dump(exclude_unset=True))


Reference = Literal["trend", "avg1", "avg7", "avg30", "low"]


class AlertRules(_Model):
    enabled: bool = True
    max_price: float | None = Field(default=None, gt=0)
    """Alarm, wenn das günstigste passende Angebot <= diesem Preis ist."""
    drop_percent: float | None = Field(default=None, gt=0, lt=100)
    """Alarm, wenn der Tiefstpreis seit der letzten Prüfung um mind. X % gefallen ist."""
    below_reference_percent: float | None = Field(default=None, gt=0, lt=100)
    """Alarm, wenn der Tiefstpreis mind. X % unter dem Referenzpreis liegt."""
    reference: Reference = "trend"
    all_time_low: bool = False
    """Alarm bei neuem Allzeit-Tief (bezogen auf die eigene Historie)."""
    cooldown_hours: float = Field(default=12, ge=0)
    """Gleiche Regel feuert erst nach Ablauf erneut – außer der Preis ist weiter gefallen."""

    def merged_with(self, override: AlertRules | None) -> AlertRules:
        if override is None:
            return self.model_copy()
        return self.model_copy(update=override.model_dump(exclude_unset=True))


class BuyRules(_Model):
    enabled: bool = False
    max_price: float | None = Field(default=None, gt=0)
    quantity: int = Field(default=1, ge=1)
    filters: OfferFilter | None = None
    """Zusätzliche (meist strengere) Filter nur für den Kauf."""

    @model_validator(mode="after")
    def _check(self) -> BuyRules:
        if self.enabled and self.max_price is None:
            raise ValueError("buy.max_price ist Pflicht, wenn buy.enabled = true")
        return self


class CardConfig(_Model):
    name: str
    key: str | None = None
    game: str = "Magic"
    product_id: int | None = None
    url: str | None = None
    enabled: bool = True
    notes: str | None = None
    filters: OfferFilter = Field(default_factory=OfferFilter)
    alerts: AlertRules = Field(default_factory=AlertRules)
    buy: BuyRules = Field(default_factory=BuyRules)

    @model_validator(mode="after")
    def _key(self) -> CardConfig:
        if not self.key:
            self.key = slugify(self.name)
        return self


# --------------------------------------------------------------------------- Provider


class MkmApiConfig(_Model):
    app_token: str
    app_secret: str
    access_token: str
    access_token_secret: str
    base_url: str = "https://api.cardmarket.com/ws/v2.0/output.json"
    max_articles: int = Field(default=300, ge=1, le=1000)
    timeout: float = 30


class ScraperConfig(_Model):
    base_url: str = "https://www.cardmarket.com"
    locale: str = "en"
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
    request_delay_seconds: float = Field(default=5, ge=0)
    timeout: float = 30
    extra_headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)


class DemoConfig(_Model):
    seed: int = 42


class ProviderConfig(_Model):
    type: Literal["mkm_api", "scraper", "demo"] = "demo"
    mkm_api: MkmApiConfig | None = None
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    demo: DemoConfig = Field(default_factory=DemoConfig)

    @model_validator(mode="after")
    def _check(self) -> ProviderConfig:
        if self.type == "mkm_api" and self.mkm_api is None:
            raise ValueError("provider.mkm_api muss gesetzt sein, wenn provider.type = mkm_api")
        return self


# --------------------------------------------------------------------------- Benachrichtigungen


class _NotifierBase(_Model):
    name: str | None = None
    events: list[Event] = Field(default_factory=lambda: list(ALL_EVENTS))


class TelegramConfig(_NotifierBase):
    type: Literal["telegram"]
    bot_token: str
    chat_id: str


class DiscordConfig(_NotifierBase):
    type: Literal["discord"]
    webhook_url: str
    username: str = "Cardmarket Tracker"


class NtfyConfig(_NotifierBase):
    type: Literal["ntfy"]
    topic: str
    server: str = "https://ntfy.sh"
    token: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class EmailConfig(_NotifierBase):
    type: Literal["email"]
    host: str
    port: int = 587
    security: Literal["starttls", "ssl", "none"] = "starttls"
    username: str | None = None
    password: str | None = None
    sender: str
    recipients: list[str]


class WebhookConfig(_NotifierBase):
    type: Literal["webhook"]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class ConsoleConfig(_NotifierBase):
    type: Literal["console"]


NotifierConfig = Annotated[
    TelegramConfig | DiscordConfig | NtfyConfig | EmailConfig | WebhookConfig | ConsoleConfig,
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- Rest


class GeneralConfig(_Model):
    interval_minutes: float = Field(default=60, ge=1)
    jitter_seconds: float = Field(default=60, ge=0)
    database: str = "data/tracker.db"
    timezone: str = "Europe/Berlin"
    log_level: str = "INFO"
    keep_offers: int = Field(default=20, ge=1, le=200)
    """Wie viele der günstigsten passenden Angebote pro Prüfung gespeichert werden."""
    notify_errors: bool = False


class DefaultsConfig(_Model):
    filters: OfferFilter = Field(default_factory=OfferFilter)
    alerts: AlertRules = Field(default_factory=AlertRules)


class ReportConfig(_Model):
    output_dir: str = "data/reports"
    daily_time: str | None = "08:00"
    history_days: int = Field(default=30, ge=1)
    top_offers: int = Field(default=5, ge=1, le=50)
    send_summary: bool = True
    attach_html: bool = True
    public_url: str | None = None
    """Optional: URL, unter der ``output_dir`` erreichbar ist (wird in Nachrichten verlinkt)."""

    @field_validator("daily_time")
    @classmethod
    def _time(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("daily_time muss im Format HH:MM sein")
        return v


class PurchasingConfig(_Model):
    enabled: bool = False
    mode: Literal["dry_run", "cart"] = "dry_run"
    max_per_run: float = Field(default=50, gt=0)
    max_per_month: float = Field(default=200, gt=0)


class AppConfig(_Model):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    cards: list[CardConfig] = Field(default_factory=list)
    notifications: list[NotifierConfig] = Field(default_factory=list)
    reports: ReportConfig = Field(default_factory=ReportConfig)
    purchasing: PurchasingConfig = Field(default_factory=PurchasingConfig)

    @model_validator(mode="after")
    def _check(self) -> AppConfig:
        seen: set[str] = set()
        for card in self.cards:
            if card.key in seen:
                raise ValueError(
                    f"Karten-Key '{card.key}' ist doppelt – setze bei einer der Karten 'key' "
                    "explizit (z.B. bei gleicher Karte mit anderen Filtern)."
                )
            seen.add(card.key)
            if self.provider.type == "mkm_api" and card.product_id is None:
                raise ValueError(f"Karte '{card.name}': product_id ist für mkm_api Pflicht")
            if self.provider.type == "scraper" and not card.url:
                raise ValueError(f"Karte '{card.name}': url ist für den Scraper Pflicht")
        if (
            self.purchasing.enabled
            and self.purchasing.mode == "cart"
            and self.provider.type != "mkm_api"
        ):
            raise ValueError("purchasing.mode = cart funktioniert nur mit provider.type = mkm_api")
        return self

    # Effektive Einstellungen pro Karte (Defaults + Overrides) --------------------------

    def card_filters(self, card: CardConfig) -> OfferFilter:
        return self.defaults.filters.merged_with(card.filters)

    def card_alerts(self, card: CardConfig) -> AlertRules:
        return self.defaults.alerts.merged_with(card.alerts)

    def card_buy_filters(self, card: CardConfig) -> OfferFilter:
        return self.card_filters(card).merged_with(card.buy.filters)

    def get_card(self, key: str) -> CardConfig:
        for card in self.cards:
            if card.key == key:
                return card
        raise KeyError(key)


# --------------------------------------------------------------------------- Laden


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "card"


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand_env(value: Any) -> Any:
    """Ersetzt ``${VAR}`` und ``${VAR:-default}`` rekursiv in Strings."""
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            env = os.environ.get(name)
            if env:
                return env
            if default is not None:
                return default
            raise ConfigError(f"Umgebungsvariable {name} ist nicht gesetzt")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    return value


def parse_config(data: dict[str, Any]) -> AppConfig:
    try:
        return AppConfig.model_validate(expand_env(data or {}))
    except ValidationError as exc:
        lines = ["Konfiguration ungültig:"]
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  - {loc}: {err['msg']}")
        raise ConfigError("\n".join(lines)) from None


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"Konfigurationsdatei {path} nicht gefunden – kopiere config.example.yaml nach {path}"
        )
    with path.open(encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML-Fehler in {path}: {exc}") from None
    return parse_config(data)
