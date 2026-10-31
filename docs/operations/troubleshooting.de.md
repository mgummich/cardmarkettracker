# Fehlersuche & FAQ

## Die Oberfläche meldet „config.yaml ist fehlerhaft“

Die Datei enthält einen Fehler (YAML-Syntax oder ungültiger Wert). Die Meldung nennt das Feld,
z.B. `cards.2.alerts.max_price`. Die letzte gültige Konfiguration läuft weiter. Datei
korrigieren oder `config.yaml.bak` zurückkopieren. `cmtracker validate` zeigt dieselben Meldungen.

## „Umgebungsvariable X ist nicht gesetzt“

Die Konfiguration verwendet `${X}` ohne Standardwert und `X` ist nicht gesetzt. In die `.env`
eintragen (und den Container neu starten) oder `${X:-}` für einen optionalen leeren Wert nutzen.

## Speichern in der Oberfläche scheitert mit „Permission denied“

Der Container-Benutzer (UID 1000) darf nicht in `config/` schreiben:
`sudo chown -R 1000:1000 config data`.

## Formulare scheitern mit „Ungültige Herkunft der Anfrage (CSRF-Schutz)“

Dein Reverse-Proxy verändert den `Host`-Header. Weitergeben lassen
(nginx: `proxy_set_header Host $host;`).

## Eine Karte zeigt „Fehler“

Die Fehlermeldung steht auf der Kartenseite. Häufige Ursachen:

| Meldung | Ursache / Lösung |
|---|---|
| `Authentifizierung fehlgeschlagen (401/403)` | falsche oder widerrufene API-Tokens |
| `Tageslimit an Requests erreicht (429)` | zu viele Requests – `interval_minutes` erhöhen |
| `HTTP 403 (Bot-Schutz/Rate-Limit)` | Scraper von Cloudflare blockiert – längere Intervalle oder die API nutzen |
| `Produkt … nicht gefunden` | falsche `product_id` |

Mit `general.notify_errors` wirst du über Fehler per Nachricht informiert.

## Eine Karte hat 0 passende Angebote

Deine Filter sind strenger als der Markt. Die Kartenseite zeigt „x passende von y Angeboten“.
Wichtig: Ist ein Filter gesetzt und das Attribut unbekannt, passt das Angebot nicht. Versuche
`seller_countries`, `languages` oder `min_condition` zu lockern.

## Kein Alarm, obwohl der Preis unter meinem Ziel liegt

- Ist die Karte aktiv und läuft die Prüfung (Seite *System*)?
- Alarme vergleichen den **gefilterten** Tiefstpreis, nicht den „ab“-Preis von Cardmarket.
- Wartezeit: dieselbe Regel meldet erst nach `cooldown_hours` erneut, außer der Preis fiel weiter.
- Ist ein Kanal für das Ereignis `alert` eingerichtet? *Testnachricht senden* nutzen.

## Der Tagesbericht kam nicht

Er wird einmal pro Tag nach `reports.daily_time` (Ortszeit) verschickt, nur von `cmtracker run`
und nur, wenn mindestens eine Karte eingerichtet ist. Startet der Tracker nach dieser Uhrzeit,
kommt der Bericht sofort.

## Sind Versandkosten enthalten?

Nein. Alle Preise sind Artikelpreise ohne Versand.

## Kann er Karten vollautomatisch kaufen?

Noch nicht. Der Modus `cart` legt den Artikel in deinen Cardmarket-Warenkorb; bezahlt wird manuell.
