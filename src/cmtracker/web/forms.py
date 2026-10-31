"""Umwandlung zwischen Formularfeldern und den Roh-Daten der config.yaml.

Konventionen:
* Fehlt ein Feld im Formular (z.B. weil es aus einer Umgebungsvariable kommt und daher
  deaktiviert angezeigt wird), bleibt der Wert in der YAML **unverändert**.
* ``POP`` entfernt einen Schlüssel – bei Karten heißt das „Standardwert übernehmen“.
* ``None`` wird als ``null`` geschrieben – bei Filtern heißt das „egal“.
* Checkboxen werden mit einem vorangestellten Hidden-Input (Wert ``0``) gesendet.
"""

from __future__ import annotations

import re
from collections.abc import Callable, MutableMapping
from typing import Any

from ruamel.yaml.comments import CommentedMap
from starlette.datastructures import FormData

from ..constants import (
    normalize_condition,
    normalize_country,
    normalize_language,
    normalize_seller_type,
)
from ..i18n import _

POP = object()

FILTER_LIST_FIELDS: dict[str, Callable[[str], str]] = {
    "languages": normalize_language,
    "seller_countries": normalize_country,
    "exclude_seller_countries": normalize_country,
    "seller_types": normalize_seller_type,
    "exclude_sellers": str,
}
FILTER_BOOL_FIELDS = ["foil", "signed", "altered", "first_edition"]
ALERT_NUMBER_FIELDS = ["max_price", "drop_percent", "below_reference_percent", "cooldown_hours"]


class FormError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


def is_env(value: Any) -> bool:
    return isinstance(value, str) and "${" in value


# ---------------------------------------------------------------------- Grundbausteine


def _get(form: FormData, name: str) -> str | None:
    """Letzter Wert (Checkbox nach Hidden-Input) oder None, wenn das Feld fehlt."""
    values = form.getlist(name)
    return str(values[-1]).strip() if values else None


def parse_number(text: str | None, field: str, *, allow_off: bool, integer: bool = False) -> Any:
    if text is None:
        raise KeyError(field)
    if text == "":
        return POP
    if text.lower() in ("aus", "off", "-", "keine", "none"):
        if allow_off:
            return None
        raise FormError(field, _("“off” is not allowed here"))
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        raise FormError(field, _("“{text}” is not a number").format(text=text)) from None
    if integer:
        if value != int(value):
            raise FormError(field, _("whole number expected"))
        return int(value)
    return int(value) if value.is_integer() else value


def split_list(text: str) -> list[str]:
    return [x for x in (p.strip() for p in re.split(r"[,;\n]+", text)) if x]


def apply(target: MutableMapping[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if value is POP:
            target.pop(key, None)
        else:
            target[key] = value


def apply_section(parent: MutableMapping[str, Any], name: str, updates: dict[str, Any]) -> None:
    """Wie ``apply`` für eine Unter-Map; leere Unter-Maps werden entfernt."""
    section = parent.get(name)
    if not isinstance(section, MutableMapping):
        section = CommentedMap()
    apply(section, updates)
    if section:
        parent[name] = section
    else:
        parent.pop(name, None)


# ---------------------------------------------------------------------- Filter


def parse_filters(form: FormData, prefix: str, allow_inherit: bool) -> dict[str, Any]:
    """Ergebnis: Schlüssel -> Wert | POP. Nicht gesendete Felder fehlen im Ergebnis."""
    out: dict[str, Any] = {}

    def mode_value(mode: str, value: Any) -> Any:
        if mode == "inherit":
            return POP
        if mode == "any":
            return None if allow_inherit else POP
        return value

    for field, normalize in FILTER_LIST_FIELDS.items():
        mode = _get(form, f"{prefix}{field}_mode")
        if mode is None:
            continue
        if field in ("languages", "seller_types"):
            raw_items = [str(v) for v in form.getlist(f"{prefix}{field}")]
        else:
            raw_items = split_list(_get(form, f"{prefix}{field}") or "")
        items: list[str] = []
        if mode == "custom":
            for item in raw_items:
                try:
                    value = normalize(item)
                except ValueError as exc:
                    raise FormError(field, str(exc)) from None
                if value not in items:
                    items.append(value)
            if not items:
                raise FormError(field, _("“Selection” chosen but nothing selected"))
        out[field] = mode_value(mode, items)

    cond = _get(form, f"{prefix}min_condition")
    if cond is not None:
        if cond in ("inherit", "any"):
            out["min_condition"] = mode_value(cond, None)
        else:
            try:
                out["min_condition"] = normalize_condition(cond)
            except ValueError as exc:
                raise FormError("min_condition", str(exc)) from None

    for field in FILTER_BOOL_FIELDS:
        value = _get(form, f"{prefix}{field}")
        if value is None:
            continue
        if value in ("inherit", "any"):
            out[field] = mode_value(value, None)
        else:
            out[field] = value == "yes"

    text = _get(form, f"{prefix}min_price")
    if text is not None:
        out["min_price"] = parse_number(text, "min_price", allow_off=allow_inherit)
    return out


def filters_view(raw: Any, allow_inherit: bool) -> dict[str, Any]:
    """Aufbereitung der Roh-Filter für das Formular."""
    raw = raw if isinstance(raw, dict) else {}
    view: dict[str, Any] = {"_env": {k for k, v in raw.items() if is_env(v)}}
    absent = "inherit" if allow_inherit else "any"

    for field, normalize in FILTER_LIST_FIELDS.items():
        if field not in raw:
            view[field] = {"mode": absent, "values": [], "text": ""}
            continue
        value = raw[field]
        if value is None:
            view[field] = {"mode": "any", "values": [], "text": ""}
            continue
        items = value if isinstance(value, list) else [value]
        normalized = []
        for item in items:
            try:
                normalized.append(normalize(item))
            except ValueError:
                normalized.append(str(item))
        view[field] = {"mode": "custom", "values": normalized, "text": ", ".join(normalized)}

    cond = raw.get("min_condition", POP)
    if cond is POP:
        view["min_condition"] = absent
    elif cond is None:
        view["min_condition"] = "any"
    else:
        try:
            view["min_condition"] = normalize_condition(cond)
        except ValueError:
            view["min_condition"] = str(cond)

    for field in FILTER_BOOL_FIELDS:
        value = raw.get(field, POP)
        if value is POP:
            view[field] = absent
        elif value is None:
            view[field] = "any"
        else:
            view[field] = "yes" if value else "no"

    mp = raw.get("min_price", POP)
    view["min_price"] = "" if mp is POP else ("aus" if mp is None else _fmt_num(mp))
    return view


# ---------------------------------------------------------------------- Alerts


def parse_alerts(form: FormData, prefix: str, allow_inherit: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in ALERT_NUMBER_FIELDS:
        text = _get(form, f"{prefix}{field}")
        if text is None:
            continue
        value = parse_number(text, field, allow_off=field != "cooldown_hours")
        if value is None and not allow_inherit:
            value = POP
        out[field] = value
    for field in ("enabled", "all_time_low"):
        value = _get(form, f"{prefix}{field}")
        if value is None:
            continue
        out[field] = POP if value == "inherit" else value in ("yes", "1")
    ref = _get(form, f"{prefix}reference")
    if ref is not None:
        if ref == "inherit":
            out["reference"] = POP
        elif ref in ("trend", "avg1", "avg7", "avg30", "low"):
            out["reference"] = ref
        else:
            raise FormError("reference", _("unknown reference price"))
    return out


def alerts_view(raw: Any, allow_inherit: bool) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    view: dict[str, Any] = {"_env": {k for k, v in raw.items() if is_env(v)}}
    for field in ALERT_NUMBER_FIELDS:
        value = raw.get(field, POP)
        view[field] = "" if value is POP else ("aus" if value is None else _fmt_num(value))
    for field in ("enabled", "all_time_low"):
        value = raw.get(field, POP)
        if value is POP:
            view[field] = "inherit" if allow_inherit else ("yes" if field == "enabled" else "no")
        else:
            view[field] = "yes" if value else "no"
    view["reference"] = raw.get("reference", "inherit" if allow_inherit else "trend")
    return view


# ---------------------------------------------------------------------- Karten


def parse_card(form: FormData, is_new: bool) -> dict[str, Any]:
    """Liefert Updates für die Karte inkl. Unterabschnitte (``filters``, ``alerts``, ``buy``)."""
    name = _get(form, "name") or ""
    if not name:
        raise FormError("name", _("Name is required"))
    out: dict[str, Any] = {"name": name}
    if is_new:
        key = _get(form, "key") or ""
        if key:
            if not re.fullmatch(r"[a-z0-9][a-z0-9\-_]*", key):
                raise FormError("key", _("only lowercase letters, digits, - and _"))
            out["key"] = key
    for field in ("game", "url", "notes"):
        value = _get(form, field)
        if value is not None:
            out[field] = value or POP
    pid = _get(form, "product_id")
    if pid is not None:
        out["product_id"] = parse_number(pid, "product_id", allow_off=False, integer=True)
    enabled = _get(form, "enabled")
    if enabled is not None:
        out["enabled"] = POP if enabled == "1" else False

    out["filters"] = parse_filters(form, "f_", allow_inherit=True)
    out["alerts"] = parse_alerts(form, "a_", allow_inherit=True)

    buy: dict[str, Any] = {}
    enabled = _get(form, "b_enabled")
    if enabled is not None:
        buy["enabled"] = enabled == "1"
    text = _get(form, "b_max_price")
    if text is not None:
        buy["max_price"] = parse_number(text, "buy.max_price", allow_off=False)
    text = _get(form, "b_quantity")
    if text is not None:
        qty = parse_number(text, "buy.quantity", allow_off=False, integer=True)
        buy["quantity"] = POP if qty in (POP, 1) else qty
    buy_filters = parse_filters(form, "bf_", allow_inherit=True)
    out["buy"] = buy
    out["buy_filters"] = buy_filters
    if buy.get("enabled") is False:
        buy["enabled"] = POP
    return out


def apply_card(card: MutableMapping[str, Any], updates: dict[str, Any]) -> None:
    updates = dict(updates)
    filters = updates.pop("filters", {})
    alerts = updates.pop("alerts", {})
    buy = updates.pop("buy", {})
    buy_filters = updates.pop("buy_filters", {})
    apply(card, updates)
    apply_section(card, "filters", filters)
    apply_section(card, "alerts", alerts)
    buy_section = card.get("buy")
    if not isinstance(buy_section, MutableMapping):
        buy_section = CommentedMap()
    apply(buy_section, buy)
    apply_section(buy_section, "filters", buy_filters)
    if buy_section:
        card["buy"] = buy_section
    else:
        card.pop("buy", None)


def card_view(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    buy = raw.get("buy") if isinstance(raw.get("buy"), dict) else {}
    return {
        "name": raw.get("name", ""),
        "key": raw.get("key", ""),
        "game": raw.get("game", "Magic"),
        "product_id": raw.get("product_id", ""),
        "url": raw.get("url", ""),
        "notes": raw.get("notes", ""),
        "enabled": raw.get("enabled", True) is not False,
        "_env": {k for k, v in raw.items() if is_env(v)},
        "filters": filters_view(raw.get("filters"), allow_inherit=True),
        "alerts": alerts_view(raw.get("alerts"), allow_inherit=True),
        "buy": {
            "enabled": bool(buy.get("enabled", False)),
            "max_price": _fmt_num(buy["max_price"]) if buy.get("max_price") is not None else "",
            "quantity": buy.get("quantity", 1),
            "filters": filters_view(buy.get("filters"), allow_inherit=True),
        },
    }


# ---------------------------------------------------------------------- Einfache Abschnitte


def parse_fields(form: FormData, spec: dict[str, str]) -> dict[str, Any]:
    """spec: Feldname -> Typ (float, int, str, optstr, bool, choice)."""
    out: dict[str, Any] = {}
    for field, kind in spec.items():
        text = _get(form, field)
        if text is None:
            continue
        if kind == "bool":
            out[field] = text == "1"
        elif kind in ("float", "int"):
            value = parse_number(text, field, allow_off=False, integer=kind == "int")
            out[field] = value
        elif kind == "optstr":
            out[field] = text or None
        else:
            out[field] = text if text else POP
    return out


def _fmt_num(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
