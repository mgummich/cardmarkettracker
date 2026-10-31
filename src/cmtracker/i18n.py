"""Internationalisation.

Source strings are English and wrapped in ``_()``. Translations live in
``cmtracker/locales/<lang>.py`` as a plain ``dict`` (English source -> translation).

The active language is stored in a ``ContextVar``:

* the web UI sets it per request (cookie / ``Accept-Language`` / config),
* the background runner and the CLI set it from ``general.language``.

Strings with placeholders use ``str.format``: ``_("{n} cards").format(n=3)``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from .locales import de as _de

LANGUAGES: dict[str, str] = {"en": "English", "de": "Deutsch"}
DEFAULT_LANGUAGE = "en"

_CATALOGS: dict[str, dict[str, str]] = {"de": _de.MESSAGES}
_current: ContextVar[str] = ContextVar("cmtracker_language", default=DEFAULT_LANGUAGE)


def normalize(lang: str | None) -> str | None:
    if not lang:
        return None
    code = lang.strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGES else None


def set_language(lang: str | None) -> None:
    _current.set(normalize(lang) or DEFAULT_LANGUAGE)


def get_language() -> str:
    return _current.get()


@contextmanager
def language(lang: str | None) -> Iterator[None]:
    token = _current.set(normalize(lang) or DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        _current.reset(token)


def _(text: str) -> str:
    """Translate ``text`` into the active language."""
    catalog = _CATALOGS.get(_current.get())
    if catalog is None:
        return text
    return catalog.get(text, text)


def negotiate(accept_language: str | None) -> str | None:
    """Pick the best supported language from an ``Accept-Language`` header."""
    if not accept_language:
        return None
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _sep, params = piece.partition(";")
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 0.0
        code = normalize(tag)
        if code and quality > 0:
            candidates.append((-quality, index, code))
    return min(candidates)[2] if candidates else None
