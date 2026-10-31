# Konfigurationsreferenz

Alles wird in einer YAML-Datei konfiguriert: `config.yaml`. Das meiste lässt sich auch in der
[Weboberfläche](../usage/web-ui.md) bearbeiten. Eine vollständig kommentierte Vorlage liegt als
[`config.example.yaml`](https://github.com/mgummich/cardmarkettracker/blob/main/config.example.yaml) bei.

- Speicherort: `-c/--config PFAD` oder Umgebungsvariable `CMTRACKER_CONFIG`
  (Docker: `/config/config.yaml`), sonst `./config.yaml`.
- Prüfen mit `cmtracker validate` – zeigt auch die **effektiven** Filter und Regeln jeder Karte.
- Relative Pfade (Datenbank, Berichte) gelten relativ zum Arbeitsverzeichnis
  (Docker: `/srv`, d.h. `data/…` landet im Volume `/srv/data`).

## Umgebungsvariablen

Jeder Text-Wert darf `${VAR}` oder `${VAR:-standard}` enthalten. Nutze das für alle Geheimnisse
und lege sie in der `.env` ab:

```yaml
provider:
  mkm_api:
    app_token: ${MKM_APP_TOKEN}
web:
  password: ${WEB_PASSWORD:-}
```

Eine referenzierte Variable ohne Standardwert, die nicht gesetzt ist, ist ein
Konfigurationsfehler. Felder mit Variablen sind in der Weboberfläche schreibgeschützt.

## `general`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `language` | `en` | `en` oder `de` – Sprache von Benachrichtigungen, Berichten, Kommandozeile und Log. Die Weboberfläche nutzt die Browsersprache bzw. den EN/DE-Umschalter. **Für Deutsch `de` setzen.** |
| `interval_minutes` | `60` | Minuten zwischen zwei Prüfungen aller Karten (≥ 1) |
| `jitter_seconds` | `60` | zufällige Zusatzverzögerung pro Intervall, damit Abrufe nicht exakt getaktet sind |
| `database` | `data/tracker.db` | SQLite-Datei |
| `timezone` | `Europe/Berlin` | IANA-Zeitzone für Berichte und Anzeige |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `keep_offers` | `20` | wie viele der günstigsten passenden Angebote pro Prüfung gespeichert werden (1–200) |
| `notify_errors` | `false` | Benachrichtigung (Ereignis `error`), wenn eine Kartenprüfung fehlschlägt |

## `provider`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `type` | `demo` | `mkm_api`, `scraper` oder `demo` – siehe [Datenquellen](data-sources.md) |
| `mkm_api.app_token` / `app_secret` / `access_token` / `access_token_secret` | – | Zugangsdaten deiner Cardmarket-„Dedicated App“ (Pflicht für `mkm_api`) |
| `mkm_api.base_url` | `https://api.cardmarket.com/ws/v2.0/output.json` | API-Adresse |
| `mkm_api.max_articles` | `300` | max. Angebote pro Karte und Prüfung (1–1000) |
| `mkm_api.timeout` | `30` | HTTP-Timeout in Sekunden |
| `scraper.base_url` | `https://www.cardmarket.com` | |
| `scraper.locale` | `en` | Sprachsegment in Produkt-URLs (`en`, `de`, …) |
| `scraper.request_delay_seconds` | `5` | Mindestpause zwischen zwei Seitenabrufen |
| `scraper.timeout` | `30` | |
| `scraper.user_agent` | Desktop-Chrome | |
| `scraper.extra_headers` / `scraper.cookies` | `{}` | zusätzliche Header / Cookies |
| `demo.seed` | `42` | Startwert für die simulierten Daten |

## `defaults`

Standard-`filters` und -`alerts` für jede Karte (gleiche Schlüssel wie bei einer Karte, siehe
unten). Eine Karte muss nur angeben, was abweicht.

## `cards`

Liste der Karten.

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `name` | – | Anzeigename (Pflicht) |
| `key` | aus `name` | eindeutige ID, z.B. `the-one-ring-ltr`. Explizit setzen, um dieselbe Karte mehrfach mit anderen Filtern zu tracken. **Eine Änderung trennt den Verlauf ab.** |
| `game` | `Magic` | freier Text (`Magic`, `Pokemon`, `YuGiOh`, …) |
| `product_id` | – | Cardmarket-Produkt-ID, Pflicht für `mkm_api` |
| `url` | – | URL der Produktseite, Pflicht für `scraper` |
| `enabled` | `true` | `false` pausiert die Karte |
| `notes` | – | freier Text |
| `filters` | – | Abweichungen von `defaults.filters` |
| `alerts` | – | Abweichungen von `defaults.alerts` |
| `buy` | – | Kauf-Regeln, siehe [Auto-Kauf](../usage/auto-buy.md) |

### Filter

Werden auf jedes Angebot angewendet. **Ist ein Filter gesetzt und das Attribut des Angebots
unbekannt, passt das Angebot nicht** – lieber ein Alarm zu wenig als ein Fehlkauf.

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `languages` | Liste | z.B. `[German, English]`; auch `de`, `Deutsch`, IDs `1`–`11` |
| `min_condition` | Text | `MT`, `NM`, `EX`, `GD`, `LP`, `PL`, `PO` (oder `near mint`, …) – dieser oder besser |
| `foil` / `signed` / `altered` / `first_edition` | bool | `true` = nur, `false` = nie, `null` = egal |
| `seller_countries` | Liste | nur Verkäufer aus diesen Ländern (`DE`, `Germany`, `Deutschland`, …) |
| `exclude_seller_countries` | Liste | keine Verkäufer aus diesen Ländern |
| `seller_types` | Liste | `private`, `professional`, `powerseller` |
| `exclude_sellers` | Liste | zu ignorierende Benutzernamen (Groß-/Kleinschreibung egal) |
| `min_price` | Zahl | Angebote unter diesem Preis ignorieren (Lockangebote) |

Zusammenführung: Bei der Karte **vorhandene** Schlüssel ersetzen den Standard; `null` heißt
ausdrücklich „egal“; fehlende Schlüssel werden geerbt.

### Alarme

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `enabled` | `true` | |
| `max_price` | – | Zielpreis |
| `drop_percent` | – | Fall seit der letzten Prüfung, 0–100 |
| `below_reference_percent` | – | Abstand unter dem Referenzpreis, 0–100 |
| `reference` | `trend` | `trend`, `avg1`, `avg7`, `avg30`, `low` |
| `all_time_low` | `false` | Alarm bei neuem Allzeit-Tief |
| `cooldown_hours` | `12` | siehe [Preisalarme](../usage/alerts.md#wartezeit-cooldown) |

### Kauf

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `enabled` | `false` | |
| `max_price` | – | Pflicht, wenn aktiviert |
| `quantity` | `1` | wie viele Exemplare insgesamt |
| `filters` | – | zusätzliche Filter für den Kauf (zusätzlich zu den Filtern der Karte) |

## `notifications`

Liste von Kanälen; siehe [Benachrichtigungen](notifications.md). Ohne Eintrag landen Meldungen
nur im Log.

## `reports`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `output_dir` | `data/reports` | |
| `daily_time` | `"08:00"` | `HH:MM` Ortszeit, `null` = aus |
| `history_days` | `30` | Zeitraum des Berichts |
| `top_offers` | `5` | Angebote pro Karte im Bericht |
| `send_summary` | `true` | kurze Zusammenfassung verschicken (Ereignis `report`) |
| `attach_html` | `true` | HTML-Datei anhängen |
| `public_url` | – | Basis-URL, unter der `/reports/` erreichbar ist; wird in Nachrichten verlinkt |

## `purchasing`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `enabled` | `false` | globaler Schalter |
| `mode` | `dry_run` | `dry_run` oder `cart` (benötigt `mkm_api`) |
| `max_per_run` | `50` | Budget pro Prüfung (€) |
| `max_per_month` | `200` | Budget pro Kalendermonat (€) |

## `web`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `enabled` | `true` | Weboberfläche zusammen mit `cmtracker run` starten |
| `host` | `127.0.0.1` | Adresse (Docker-Image: `0.0.0.0` per Kommandozeile) |
| `port` | `8080` | |
| `username` | `admin` | Benutzer für HTTP-Basic-Auth |
| `password` | – | aktiviert HTTP-Basic-Auth – **setzen**, sobald die Oberfläche von anderen Rechnern erreichbar ist |

## Vollständiges Beispiel

Die Vorlage ist englisch kommentiert. Für deutsche Nachrichten und Berichte
`general.language: de` setzen.

```yaml
--8<-- "config.example.yaml"
```
