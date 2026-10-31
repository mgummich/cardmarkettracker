"""Lesen/Schreiben der config.yaml unter Erhalt von Kommentaren und ``${ENV}``-Platzhaltern."""

from __future__ import annotations

import copy
import io
import logging
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.tokens import CommentToken

from ..config import AppConfig, ConfigError, load_config, parse_config, slugify

log = logging.getLogger(__name__)


def card_key_of(raw_card: dict[str, Any]) -> str:
    return str(raw_card.get("key") or slugify(str(raw_card.get("name", ""))))


# ruamel hängt Kommentare, die *nach* einer Liste stehen (z.B. der Kopf des nächsten
# Abschnitts), an den letzten Wert des letzten Listeneintrags. Beim Anhängen/Löschen von
# Karten muss dieser "Schwanz" mitwandern, sonst verrutscht oder verschwindet er.


def _tail_owner(node: Any) -> tuple[Any, Any]:
    while True:
        if isinstance(node, CommentedMap) and node:
            key: Any = list(node.keys())[-1]
        elif isinstance(node, CommentedSeq) and node:
            key = len(node) - 1
        else:
            return None, None
        child = node[key]
        if isinstance(child, CommentedMap | CommentedSeq) and child:
            node = child
            continue
        return node, key


def _slot(owner: Any) -> int:
    return 2 if isinstance(owner, CommentedMap) else 0


def take_tail_comment(node: Any) -> str | None:
    """Entfernt nachfolgende Kommentarzeilen (Inline-Kommentar bleibt) und gibt sie zurück."""
    owner, key = _tail_owner(node)
    if owner is None:
        return None
    entry = owner.ca.items.get(key)
    token = entry[_slot(owner)] if entry and len(entry) > _slot(owner) else None
    if token is None:
        return None
    first, _, rest = token.value.partition("\n")
    if not rest.strip():
        return None
    if first.strip():
        token.value = first + "\n"
    else:
        entry[_slot(owner)] = None
    return rest


def put_tail_comment(node: Any, tail: str | None) -> None:
    if not tail:
        return
    owner, key = _tail_owner(node)
    if owner is None:
        return
    size = 4 if isinstance(owner, CommentedMap) else 2
    entry = owner.ca.items.setdefault(key, [None] * size)
    token = entry[_slot(owner)]
    if token is None:
        entry[_slot(owner)] = CommentToken("\n" + tail, CommentMark(0), None)
    else:
        token.value = token.value.rstrip("\n") + "\n" + tail


class ConfigStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._yaml.width = 120
        self._yaml.representer.add_representer(
            type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null")
        )
        self._lock = threading.Lock()
        self._last_good: AppConfig | None = None

    # ------------------------------------------------------------------ Lesen

    def current(self) -> tuple[AppConfig, str | None]:
        """Aktuelle Konfiguration. Ist die Datei kaputt: letzte gültige + Fehlermeldung."""
        try:
            cfg = load_config(self.path)
        except ConfigError as exc:
            if self._last_good is None:
                raise
            return self._last_good, str(exc)
        self._last_good = cfg
        return cfg, None

    def load_raw(self) -> CommentedMap:
        with self.path.open(encoding="utf-8") as fh:
            data = self._yaml.load(fh)
        return data if isinstance(data, CommentedMap) else CommentedMap()

    # ------------------------------------------------------------------ Schreiben

    def dump(self, raw: CommentedMap) -> str:
        buf = io.StringIO()
        self._yaml.dump(raw, buf)
        return buf.getvalue()

    def save(self, raw: CommentedMap) -> AppConfig:
        """Validiert und schreibt. Wirft ``ConfigError`` – dann bleibt die Datei unverändert."""
        text = self.dump(raw)
        cfg = parse_config(yaml.safe_load(text) or {})
        with self._lock:
            if self.path.exists():
                shutil.copy2(self.path, self.path.with_name(self.path.name + ".bak"))
            self._write(text)
        self._last_good = cfg
        log.info("Konfiguration über die Weboberfläche gespeichert")
        return cfg

    def _write(self, text: str) -> None:
        directory = self.path.parent
        try:
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".config-", suffix=".yaml")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, self.path)
        except OSError:
            # z.B. Docker-Bind-Mount einer Einzeldatei: dann direkt überschreiben
            with self.path.open("w", encoding="utf-8") as fh:
                fh.write(text)

    # ------------------------------------------------------------------ Karten-Helfer

    @staticmethod
    def cards(raw: CommentedMap) -> CommentedSeq:
        cards = raw.get("cards")
        if not isinstance(cards, list):
            cards = CommentedSeq()
            raw["cards"] = cards
        return cards

    def append_card(self, raw: CommentedMap, card: CommentedMap) -> None:
        cards = self.cards(raw)
        tail = take_tail_comment(cards[-1]) if cards else None
        cards.fa.set_block_style()  # "cards: []" würde sonst als Flow-Liste geschrieben
        cards.append(card)
        put_tail_comment(card, tail)

    def update_card(
        self, raw: CommentedMap, idx: int, mutate: Callable[[CommentedMap], None]
    ) -> CommentedMap:
        """Bearbeitet eine Kopie der Karte (``mutate`` darf Exceptions werfen) und setzt sie ein."""
        cards = self.cards(raw)
        tail = take_tail_comment(cards[idx]) if idx == len(cards) - 1 else None
        edited = copy.deepcopy(cards[idx])
        mutate(edited)  # bei Fehlern wird ``raw`` vom Aufrufer verworfen
        put_tail_comment(edited, tail)
        cards[idx] = edited
        return edited

    def delete_card(self, raw: CommentedMap, idx: int) -> None:
        cards = self.cards(raw)
        tail = take_tail_comment(cards[idx]) if idx == len(cards) - 1 else None
        del cards[idx]
        if cards:
            put_tail_comment(cards[-1], tail)
        elif tail:
            # keine Karten mehr: Kommentar an "cards: []" kann ruamel nicht halten -> verwerfen
            log.debug("Kommentar nach der letzten Karte entfernt")

    def find_card(self, raw: CommentedMap, key: str) -> tuple[int, CommentedMap] | None:
        for idx, card in enumerate(self.cards(raw)):
            if isinstance(card, dict) and card_key_of(card) == key:
                return idx, card
        return None
