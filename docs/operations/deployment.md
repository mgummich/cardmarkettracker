# Deployment

## Directory layout (Docker)

```text
cardmarket-tracker/
├── docker-compose.yml
├── .env                  # secrets: WEB_PASSWORD, API tokens, bot tokens
├── config/
│   ├── config.yaml       # edited by you and the web UI
│   └── config.yaml.bak   # previous version (written by the web UI)
└── data/
    ├── tracker.db        # SQLite: history, alerts, purchases
    └── reports/          # HTML reports
```

The image runs as UID `1000`, listens on port `8080` and has a health check on `/api/status`.

## Reverse proxy with HTTPS

Only expose the UI through a reverse proxy with TLS and **always set `web.password`**.
The UI works at the root of a (sub)domain, e.g. `tracker.example.com`; serving it under a
sub-path is not supported.

=== "Caddy"

    ```caddyfile
    tracker.example.com {
        reverse_proxy cardmarket-tracker:8080
    }
    ```

=== "Traefik (labels)"

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

!!! note "Host header"
    Form submissions are only accepted from the same origin. The proxy must pass the original
    `Host` header (Caddy and Traefik do this by default; nginx needs `proxy_set_header Host $host`).

When the proxy runs on the same host, bind the port to localhost only:
`ports: ["127.0.0.1:8080:8080"]`.

## Raspberry Pi / NAS

The image is published for `linux/arm64` (Raspberry Pi 3/4/5 with a 64-bit OS, most current
NAS). The tracker needs about 60 MB RAM and almost no CPU.

## Backups

Everything worth keeping is in `config/`, `data/tracker.db` and `.env`.

```bash
# consistent copy of the database while the tracker is running
sqlite3 data/tracker.db ".backup 'backup/tracker-$(date +%F).db'"
cp config/config.yaml .env backup/
```

## Resource usage and limits

- Each check makes 1–2 requests per card (API) or 1 page request per card (scraper).
- The database grows by about 1.5–5 KB per card and check, depending on how many matching
  offers are stored (`general.keep_offers`, default 20). 50 cards checked hourly ≈ 50–160 MB per
  month. Lower `keep_offers` or the interval if storage matters; automatic history cleanup is on
  the roadmap.
- Stay well within Cardmarket's API limits; choose the interval accordingly.
