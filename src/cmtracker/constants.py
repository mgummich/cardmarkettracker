"""Cardmarket master data: conditions, languages, countries, seller types.

All ``normalize_*`` functions accept common spellings (English/German, abbreviations)
and return a canonical value or raise ``ValueError``.
"""

from __future__ import annotations

import re

from .i18n import _, get_language

# Reihenfolge = Qualität absteigend. Index+1 entspricht dem ``minCondition``-Parameter
# auf cardmarket.com.
CONDITIONS: list[str] = ["MT", "NM", "EX", "GD", "LP", "PL", "PO"]

CONDITION_NAMES_DE: dict[str, str] = {
    "MT": "Mint",
    "NM": "Near Mint",
    "EX": "Excellent",
    "GD": "Good",
    "LP": "Light Played",
    "PL": "Played",
    "PO": "Poor",
}

_CONDITION_ALIASES: dict[str, str] = {
    "M": "MT",
    "MINT": "MT",
    "NEARMINT": "NM",
    "EXCELLENT": "EX",
    "GOOD": "GD",
    "LIGHTPLAYED": "LP",
    "LIGHTLYPLAYED": "LP",
    "PLAYED": "PL",
    "POOR": "PO",
}

# Cardmarket-Sprach-IDs (API: idLanguage, Website: language=...)
LANGUAGES: dict[int, str] = {
    1: "English",
    2: "French",
    3: "German",
    4: "Spanish",
    5: "Italian",
    6: "S-Chinese",
    7: "Japanese",
    8: "Portuguese",
    9: "Russian",
    10: "Korean",
    11: "T-Chinese",
}
LANGUAGE_IDS: dict[str, int] = {name: idx for idx, name in LANGUAGES.items()}

LANGUAGE_NAMES_DE: dict[str, str] = {
    "English": "Englisch",
    "French": "Französisch",
    "German": "Deutsch",
    "Spanish": "Spanisch",
    "Italian": "Italienisch",
    "S-Chinese": "Chinesisch (vereinfacht)",
    "Japanese": "Japanisch",
    "Portuguese": "Portugiesisch",
    "Russian": "Russisch",
    "Korean": "Koreanisch",
    "T-Chinese": "Chinesisch (traditionell)",
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "en": "English",
    "english": "English",
    "englisch": "English",
    "fr": "French",
    "french": "French",
    "französisch": "French",
    "francais": "French",
    "français": "French",
    "de": "German",
    "german": "German",
    "deutsch": "German",
    "es": "Spanish",
    "spanish": "Spanish",
    "spanisch": "Spanish",
    "español": "Spanish",
    "espanol": "Spanish",
    "it": "Italian",
    "italian": "Italian",
    "italienisch": "Italian",
    "italiano": "Italian",
    "zh": "S-Chinese",
    "zh-cn": "S-Chinese",
    "s-chinese": "S-Chinese",
    "simplified chinese": "S-Chinese",
    "chinese (simplified)": "S-Chinese",
    "s-chinesisch": "S-Chinese",
    "chinesisch (vereinfacht)": "S-Chinese",
    "ja": "Japanese",
    "jp": "Japanese",
    "japanese": "Japanese",
    "japanisch": "Japanese",
    "pt": "Portuguese",
    "portuguese": "Portuguese",
    "portugiesisch": "Portuguese",
    "ru": "Russian",
    "russian": "Russian",
    "russisch": "Russian",
    "ko": "Korean",
    "kr": "Korean",
    "korean": "Korean",
    "koreanisch": "Korean",
    "zh-tw": "T-Chinese",
    "t-chinese": "T-Chinese",
    "traditional chinese": "T-Chinese",
    "chinese (traditional)": "T-Chinese",
    "t-chinesisch": "T-Chinese",
    "chinesisch (traditionell)": "T-Chinese",
}

# ISO-3166-Alpha-2 -> (englischer Name, deutscher Name)
COUNTRIES: dict[str, tuple[str, str]] = {
    "AT": ("Austria", "Österreich"),
    "BE": ("Belgium", "Belgien"),
    "BG": ("Bulgaria", "Bulgarien"),
    "CA": ("Canada", "Kanada"),
    "CH": ("Switzerland", "Schweiz"),
    "CY": ("Cyprus", "Zypern"),
    "CZ": ("Czech Republic", "Tschechien"),
    "DE": ("Germany", "Deutschland"),
    "DK": ("Denmark", "Dänemark"),
    "EE": ("Estonia", "Estland"),
    "ES": ("Spain", "Spanien"),
    "FI": ("Finland", "Finnland"),
    "FR": ("France", "Frankreich"),
    "GB": ("United Kingdom", "Vereinigtes Königreich"),
    "GR": ("Greece", "Griechenland"),
    "HR": ("Croatia", "Kroatien"),
    "HU": ("Hungary", "Ungarn"),
    "IE": ("Ireland", "Irland"),
    "IS": ("Iceland", "Island"),
    "IT": ("Italy", "Italien"),
    "JP": ("Japan", "Japan"),
    "LI": ("Liechtenstein", "Liechtenstein"),
    "LT": ("Lithuania", "Litauen"),
    "LU": ("Luxembourg", "Luxemburg"),
    "LV": ("Latvia", "Lettland"),
    "MT": ("Malta", "Malta"),
    "NL": ("Netherlands", "Niederlande"),
    "NO": ("Norway", "Norwegen"),
    "PL": ("Poland", "Polen"),
    "PT": ("Portugal", "Portugal"),
    "RO": ("Romania", "Rumänien"),
    "SE": ("Sweden", "Schweden"),
    "SG": ("Singapore", "Singapur"),
    "SI": ("Slovenia", "Slowenien"),
    "SK": ("Slovakia", "Slowakei"),
    "US": ("United States", "Vereinigte Staaten"),
}
# Cardmarket verwendet in der API vereinzelt eigene Kürzel.
_COUNTRY_CODE_ALIASES: dict[str, str] = {"D": "DE", "UK": "GB"}
_COUNTRY_NAME_ALIASES: dict[str, str] = {
    "czechia": "CZ",
    "tschechische republik": "CZ",
    "usa": "US",
    "united states of america": "US",
    "great britain": "GB",
    "großbritannien": "GB",
}

SELLER_TYPES: list[str] = ["private", "professional", "powerseller"]
_SELLER_TYPE_ALIASES: dict[str, str] = {
    "private": "private",
    "privat": "private",
    "0": "private",
    "professional": "professional",
    "commercial": "professional",
    "gewerblich": "professional",
    "gewerblicher verkäufer": "professional",
    "1": "professional",
    "powerseller": "powerseller",
    "power seller": "powerseller",
    "2": "powerseller",
}


def normalize_condition(value: str) -> str:
    key = re.sub(r"[\s\-_]", "", str(value)).upper()
    if key in CONDITIONS:
        return key
    if key in _CONDITION_ALIASES:
        return _CONDITION_ALIASES[key]
    raise ValueError(
        _("Unknown condition: {value} (allowed: {allowed})").format(
            value=repr(value), allowed=", ".join(CONDITIONS)
        )
    )


def condition_rank(condition: str) -> int:
    """0 = Mint (bester Zustand), 6 = Poor."""
    return CONDITIONS.index(normalize_condition(condition))


def normalize_language(value: str | int) -> str:
    if isinstance(value, int) or str(value).isdigit():
        idx = int(value)
        if idx in LANGUAGES:
            return LANGUAGES[idx]
        raise ValueError(_("Unknown language ID: {value}").format(value=repr(value)))
    text = str(value).strip()
    if text in LANGUAGE_IDS:
        return text
    key = text.lower()
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]
    raise ValueError(_("Unknown language: {value}").format(value=repr(value)))


def normalize_country(value: str) -> str:
    text = str(value).strip()
    code = text.upper()
    code = _COUNTRY_CODE_ALIASES.get(code, code)
    if code in COUNTRIES:
        return code
    lower = text.lower()
    if lower in _COUNTRY_NAME_ALIASES:
        return _COUNTRY_NAME_ALIASES[lower]
    for iso, names in COUNTRIES.items():
        if lower in (n.lower() for n in names):
            return iso
    raise ValueError(_("Unknown country: {value}").format(value=repr(value)))


def normalize_seller_type(value: str | int) -> str:
    key = str(value).strip().lower()
    if key in _SELLER_TYPE_ALIASES:
        return _SELLER_TYPE_ALIASES[key]
    raise ValueError(
        _("Unknown seller type: {value} (allowed: {allowed})").format(
            value=repr(value), allowed=", ".join(SELLER_TYPES)
        )
    )


CONDITION_NAMES_EN: dict[str, str] = {
    "MT": "Mint",
    "NM": "Near Mint",
    "EX": "Excellent",
    "GD": "Good",
    "LP": "Light Played",
    "PL": "Played",
    "PO": "Poor",
}

LANGUAGE_NAMES_EN: dict[str, str] = {
    "English": "English",
    "French": "French",
    "German": "German",
    "Spanish": "Spanish",
    "Italian": "Italian",
    "S-Chinese": "Chinese (simplified)",
    "Japanese": "Japanese",
    "Portuguese": "Portuguese",
    "Russian": "Russian",
    "Korean": "Korean",
    "T-Chinese": "Chinese (traditional)",
}


def condition_name(code: str | None) -> str:
    """Human-readable condition name (Mint, Near Mint, …)."""
    return CONDITION_NAMES_EN.get(code or "", code or "–")


def language_name(lang: str | None) -> str:
    """Name of a card language in the active UI language."""
    if not lang:
        return "–"
    names = LANGUAGE_NAMES_DE if get_language() == "de" else LANGUAGE_NAMES_EN
    return names.get(lang, lang)


def country_name(code: str | None) -> str:
    """Name of a country (ISO-2) in the active UI language."""
    if not code:
        return "?"
    names = COUNTRIES.get(code)
    if not names:
        return code
    return names[1] if get_language() == "de" else names[0]
