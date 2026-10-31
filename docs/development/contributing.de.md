# Mitmachen

Danke für dein Interesse an Cardmarket Tracker! Fehlerberichte, Ideen, Doku-Verbesserungen,
Übersetzungen und Code sind willkommen. Issues und Pull Requests dürfen auf **Deutsch oder
Englisch** geschrieben werden.

## Fehler melden und Wünsche äußern

- Zuerst die [vorhandenen Issues](https://github.com/mgummich/cardmarkettracker/issues) durchsuchen.
- Die Issue-Vorlagen nutzen. Bei Fehlern bitte Version (`cmtracker --version`), Betriebsart
  (Docker / pip), Datenquelle und die passenden Log-Zeilen angeben. **Tokens und Passwörter entfernen.**
- Scraper-Probleme: die betroffene Produkt-URL angeben.
- Sicherheitslücken bitte gemäß [Sicherheitsrichtlinie](https://github.com/mgummich/cardmarkettracker/blob/main/SECURITY.md)
  melden statt als Issue.

## Entwicklungsumgebung

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,docs]'
pre-commit install          # optional: ruff bei jedem Commit
cp config.example.yaml config.yaml
cmtracker run               # Demo-Daten, Weboberfläche auf http://127.0.0.1:8080
```

## Prüfungen

Vor einem Pull Request dieselben Prüfungen wie die CI ausführen:

```bash
ruff check . && ruff format --check .
pytest
mkdocs build --strict       # wenn du die Doku geändert hast
```

## Pull Requests

1. Repository forken und einen Branch von `main` anlegen.
2. Pull Requests klein halten; ein Thema pro PR.
3. Für Verhaltensänderungen Tests ergänzen oder anpassen.
4. Die Doku aktualisieren – **in beiden Sprachen** (`docs/*.md` und `docs/*.de.md`).
   Wenn du nur eine Sprache schreiben kannst, sag es im PR – wir helfen bei der anderen.
5. Einen Eintrag unter *Unreleased* in `CHANGELOG.md` ergänzen.
6. Sicherstellen, dass die CI grün ist.

## Code-Stil

- Python ≥ 3.11, formatiert und geprüft mit ruff (Zeilenlänge 100).
- Typannotationen für öffentliche Funktionen.
- Texte für Nutzer (Nachrichten, Weboberfläche) sind derzeit deutsch; Code, Kommentare in
  neuen Modulen und Commit-Nachrichten dürfen englisch oder deutsch sein.
- Keine neue Laufzeit-Abhängigkeit ohne guten Grund.

## Dokumentation

Die Doku wird mit [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) und
[mkdocs-static-i18n](https://github.com/ultrabug/mkdocs-static-i18n) gebaut. Englische Seiten
heißen `name.md`, deutsche `name.de.md`. Lokale Vorschau:

```bash
mkdocs serve
```

## Lizenz

Mit deinem Beitrag stimmst du zu, dass er unter der
[MIT-Lizenz](https://github.com/mgummich/cardmarkettracker/blob/main/LICENSE) steht.
