# Web interface

`cmtracker run` starts the tracker **and** the web interface (default port `8080`).

!!! note "Language"
    The web interface is currently in **German**. This page gives the German labels in
    *italics* next to the English description. An English UI is on the roadmap –
    contributions welcome!

## Dashboard

![Dashboard](../assets/screenshots/dashboard.png)

| Column | Meaning |
|---|---|
| Status | *aktiv* (active), *Ziel erreicht* (target price reached), *Fehler* (last check failed), *neu* (no data yet), *pausiert* (paused) |
| Low (*Tiefstpreis*) | cheapest offer that matches **your filters** |
| 7 days (*7 Tage*) | sparkline of the low over the last 7 days (green = falling) |
| 24 h / 7 d | change of the low compared with 24 hours / 7 days ago |
| vs. trend | low compared with Cardmarket's price trend |
| Target (*Zielpreis*) | your `max_price` alert rule and the distance to it |
| All-time low (*Allzeit-Tief*) | lowest low since tracking started |
| Offers (*Angebote*) | matching offers / all offers |

The header shows the background status (*nächste Prüfung* = next check) and the
**↻ Check now** (*Jetzt prüfen*) button. When a check finishes, the page reloads automatically.

## Card page

![Card page](../assets/screenshots/card-detail.png)

- **Price history** (*Preisverlauf*): range 7 d / 30 d / 90 d / 1 y / all; hover a point to see
  its exact value. Lines: your filtered low, Cardmarket trend, 30-day average, target price.
- Key figures, the cheapest matching offers of the last check, alerts and purchases.
- Buttons: check now, edit (*Bearbeiten*), pause / resume (*Pausieren* / *Fortsetzen*).

## Adding and editing cards

![Edit card](../assets/screenshots/card-edit.png)

Every filter and alert field can be

| Choice | German | Written to `config.yaml` |
|---|---|---|
| use the global default | *Standard* | key is removed |
| explicitly "don't care" | *egal* | `null` |
| a specific value | *Auswahl…* / value | the value |

Numeric alert fields: leave empty to use the default, type `aus` (off) to disable a rule for
this card. Decimal comma and point are both accepted.

The **key** is fixed after creation, so the price history stays attached even if you rename
the card. When deleting a card you can optionally delete its history as well.

## Settings

*Einstellungen* contains: defaults for all cards (filters and alerts), check schedule,
data source, report and auto-buy. Fields filled from environment variables are locked and
marked with an `${ENV}` badge.

## System

*System* shows the background service (last / next check, duration, errors), the configured
notification channels (targets masked), a **test message** button, report generation and
links to the JSON API.

## How saving works

1. The form is validated; errors are shown and nothing is written.
2. `config.yaml` is updated **round-trip**: comments, ordering and `${ENV}` placeholders stay
   untouched. The previous version is kept as `config.yaml.bak`.
3. The background service reloads the configuration immediately – no restart needed.

Manual edits to `config.yaml` are picked up automatically too. If the file becomes invalid,
the UI shows a warning and the last valid configuration keeps running.

!!! info "Not editable in the browser"
    API credentials, notification channels and the web settings themselves (`web:`) are only
    edited in `config.yaml` / `.env`, so secrets cannot be changed or read from the browser.
