# Sicherheit

## Empfehlungen

- **`web.password` setzen** (über `WEB_PASSWORD` in der `.env`), sobald die Oberfläche nicht nur
  über `localhost` erreichbar ist. Der Tracker warnt im Log, wenn er ohne Passwort auf einer
  öffentlichen Adresse lauscht.
- Ins Internet nur hinter einem Reverse-Proxy mit **HTTPS** – Basic-Auth schickt das Passwort
  mit jeder Anfrage.
- Geheimnisse in der `.env` ablegen und mit `${VAR}` referenzieren. `.env` und `config.yaml`
  nicht committen.
- Für den Auto-Kauf `dry_run` und kleine Budgets verwenden.

## Eingebaute Schutzmaßnahmen

| Schutz | Details |
|---|---|
| Anmeldung | optionale HTTP-Basic-Auth für alle Seiten, API und Dateien (zeitkonstanter Vergleich) |
| CSRF | ändernde Anfragen nur, wenn `Origin`/`Referer` zum `Host` passen |
| Geheimnisse in der Oberfläche | API-Zugangsdaten, Benachrichtigungs-Tokens und die `web`-Einstellungen sind im Browser weder sichtbar noch änderbar; Ziele der Kanäle werden maskiert |
| Sicheres Speichern | Eingaben werden vor dem Schreiben geprüft; `${ENV}`-Felder sind schreibgeschützt; vorige Konfiguration als `.bak` |
| Header | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` |
| Container | läuft als Nicht-Root-Benutzer `1000` |
| Berichtsdateien | nur einfache `*.html`-Dateinamen aus dem Berichtsordner werden ausgeliefert |

## Sicherheitslücke melden

Bitte **kein** öffentliches Issue anlegen. Siehe
[SECURITY.md](https://github.com/mgummich/cardmarkettracker/blob/main/SECURITY.md).
