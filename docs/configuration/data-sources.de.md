# Datenquellen

| | `mkm_api` | `scraper` | `demo` |
|---|---|---|---|
| Daten | offizielle Cardmarket-API | öffentliche Produktseite | simuliert |
| Zuverlässigkeit | hoch | gering (Bot-Schutz, HTML-Änderungen) | – |
| Angebote pro Karte | bis `max_articles` (Standard 300) | erste Seite (~50 günstigste) | 12–30 |
| Preisübersicht (Trend, Schnitte) | ✔ | ✔ (ausgelesen) | ✔ (simuliert) |
| Auto-Kauf-Modus `cart` | ✔ | – | – |
| Benötigt | API-Zugangsdaten | Produkt-URL | nichts |

## Cardmarket-API (`mkm_api`) – empfohlen

Nutzt die [MKM API v2.0](https://api.cardmarket.com/ws/documentation) mit OAuth 1.0a.

### Zugangsdaten bekommen

1. Auf cardmarket.com anmelden und **Konto → Einstellungen → API** öffnen (der genaue Ort kann sich ändern).
2. Eine **Dedicated App** anlegen. Du erhältst *App Token* und *App Secret*.
3. Für die App *Access Token* und *Access Token Secret* erzeugen.
4. Alle vier in die `.env` eintragen:

```bash title=".env"
MKM_APP_TOKEN=...
MKM_APP_SECRET=...
MKM_ACCESS_TOKEN=...
MKM_ACCESS_TOKEN_SECRET=...
```

```yaml title="config.yaml"
provider:
  type: mkm_api
  mkm_api:
    app_token: ${MKM_APP_TOKEN}
    app_secret: ${MKM_APP_SECRET}
    access_token: ${MKM_ACCESS_TOKEN}
    access_token_secret: ${MKM_ACCESS_TOKEN_SECRET}
```

!!! warning "API-Zugang ist eingeschränkt"
    Cardmarket vergibt nicht jedem Konto API-Zugang. Kannst du keine App anlegen, wende dich
    an den Cardmarket-Support oder nutze den Scraper als Notlösung.

### Produkt-ID finden

Die ID bezeichnet genau ein Produkt (Karte + Edition). Mit API-Zugang danach suchen:

```text
GET https://api.cardmarket.com/ws/v2.0/output.json/products/find?search=The%20One%20Ring&idGame=1
```

`idGame`: 1 = Magic, 3 = Yu-Gi-Oh!, 6 = Pokémon (weitere siehe API-Doku). Ein Befehl
`cmtracker search` steht auf der Roadmap.

### Request-Budget

Pro Karte und Prüfung: 1 Request für das Produkt + 1 pro 100 Angebote. Beispiel: 20 Karten mit
< 100 Angeboten, stündlich geprüft → 40 × 24 = **960 Requests / Tag**. Bleib deutlich unter dem
Tageslimit deines Zugangs; HTTP 429 wird als Fehler gemeldet.

Wo die API es unterstützt, wird serverseitig vorgefiltert (einzelne Sprache, Mindestzustand,
Foil, signiert, altered); alles andere wird lokal gefiltert.

## Scraper (`scraper`) – Notlösung

Ruft die öffentliche Produktseite ab, z.B.
`https://www.cardmarket.com/de/Magic/Products/Singles/Alpha/Black-Lotus`, hängt deine Filter
als URL-Parameter an (`language`, `minCondition`, `isFoil`, `sellerType`, …) und liest die
Angebote aus.

```yaml
provider:
  type: scraper
  scraper:
    locale: de
    request_delay_seconds: 8
cards:
  - name: Black Lotus
    url: https://www.cardmarket.com/de/Magic/Products/Singles/Alpha/Black-Lotus
```

!!! warning "Verantwortungsvoll nutzen"
    - Cardmarket nutzt einen Bot-Schutz (Cloudflare). Abrufe können mit HTTP 403 scheitern; der
      Fehler wird bei der Karte angezeigt. Lange Intervalle und großzügige Pausen verwenden.
    - Änderungen am HTML können den Parser brechen. Bitte [ein Issue anlegen](https://github.com/mgummich/cardmarkettracker/issues)
      und die betroffene Karten-URL angeben.
    - Vor dem Scraping die Nutzungsbedingungen von Cardmarket prüfen.

## Demo (`demo`)

Erzeugt reproduzierbare, plausible Angebote, die sich über die Zeit verändern. Ideal zum
Ausprobieren von Dashboard, Alarmen, Berichten und Benachrichtigungen oder für die
Entwicklung. Kein Netzwerkzugriff.
