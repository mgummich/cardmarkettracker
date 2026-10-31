# Deployment

## Verzeichnisstruktur (Docker)

```text
cardmarket-tracker/
├── docker-compose.yml
├── .env                  # Geheimnisse: WEB_PASSWORD, API-Tokens, Bot-Tokens
├── config/
│   ├── config.yaml       # bearbeitet von dir und der Weboberfläche
│   └── config.yaml.bak   # vorige Version (von der Weboberfläche geschrieben)
└── data/
    ├── tracker.db        # SQLite: Verlauf, Alarme, Käufe
    └── reports/          # HTML-Berichte
```

Das Image läuft als UID `1000`, lauscht auf Port `8080` und hat einen Healthcheck auf `/api/status`.

## Reverse-Proxy mit HTTPS

Die Oberfläche nur über einen Reverse-Proxy mit TLS veröffentlichen und **immer
`web.password` setzen**. Sie funktioniert im Wurzelverzeichnis einer (Sub-)Domain, z.B.
`tracker.example.com`; ein Unterpfad wird nicht unterstützt.

=== "Caddy"

    ```caddyfile
    tracker.example.com {
        reverse_proxy cardmarket-tracker:8080
    }
    ```

=== "Traefik (Labels)"

    ```yaml
    services:
      tracker:
        image: ghcr.io/mgummich/cardmarkettracker:latest
        labels:
          - traefik.enable=true
          - traefik.http.routers.cmtracker.rule=Host(`tracker.example.com`)
          - traefik.http.routers.cmtracker.entrypoints=websecure
          - traefik.http.routers.cmtracker.tls.certresolver=letsencrypt
          - traefik.http.services.cmtracker.loadbalancer.server.port=8080
    ```

=== "nginx"

    ```nginx
    server {
        listen 443 ssl;
        server_name tracker.example.com;
        # ssl_certificate ... ;

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

!!! note "Host-Header"
    Formulare werden nur von derselben Herkunft angenommen. Der Proxy muss den ursprünglichen
    `Host`-Header weitergeben (Caddy und Traefik tun das standardmäßig; nginx braucht
    `proxy_set_header Host $host`).

Läuft der Proxy auf demselben Rechner, den Port nur lokal freigeben:
`ports: ["127.0.0.1:8080:8080"]`.

## Raspberry Pi / NAS

Das Image gibt es für `linux/arm64` (Raspberry Pi 3/4/5 mit 64-Bit-System, die meisten
aktuellen NAS). Der Tracker braucht etwa 60 MB RAM und kaum CPU.

## Backups

Alles Wichtige liegt in `config/`, `data/tracker.db` und `.env`.

```bash
# konsistente Kopie der Datenbank im laufenden Betrieb
sqlite3 data/tracker.db ".backup 'backup/tracker-$(date +%F).db'"
cp config/config.yaml .env backup/
```

## Ressourcen und Grenzen

- Jede Prüfung macht 1–2 Requests pro Karte (API) bzw. 1 Seitenabruf pro Karte (Scraper).
- Die Datenbank wächst um etwa 1,5–5 KB pro Karte und Prüfung, je nachdem wie viele passende
  Angebote gespeichert werden (`general.keep_offers`, Standard 20). 50 Karten stündlich ≈
  50–160 MB pro Monat. Bei knappem Speicher `keep_offers` oder das Intervall senken; automatisches
  Aufräumen des Verlaufs steht auf der Roadmap.
- Bleib deutlich innerhalb der API-Limits von Cardmarket und wähle das Intervall entsprechend.
