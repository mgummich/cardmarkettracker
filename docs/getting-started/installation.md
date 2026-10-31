# Installation

Cardmarket Tracker runs anywhere Python 3.11+ or Docker runs – a home server, NAS,
Raspberry Pi (arm64) or a small VPS.

## Docker (recommended)

Prebuilt multi-arch images (`linux/amd64`, `linux/arm64`) are published to the GitHub Container
Registry: `ghcr.io/mgummich/cardmarkettracker`.

| Tag | Meaning |
|---|---|
| `latest` | latest build of the `main` branch |
| `0.2.0`, `0.2` | a specific release |
| `sha-<commit>` | a specific commit |

### Docker Compose

```bash
mkdir cardmarket-tracker && cd cardmarket-tracker
curl -LO https://raw.githubusercontent.com/mgummich/cardmarkettracker/main/docker-compose.yml
curl -L -o .env https://raw.githubusercontent.com/mgummich/cardmarkettracker/main/.env.example
mkdir -p config data && sudo chown -R 1000:1000 config data
```

Edit `.env` and set at least `WEB_PASSWORD`. The compose file looks like this:

```yaml
services:
  tracker:
    image: ghcr.io/mgummich/cardmarkettracker:latest
    build: .                 # only used with "docker compose up --build" in a git checkout
    container_name: cardmarket-tracker
    restart: unless-stopped
    env_file: .env
    ports:
      - "8080:8080"
    volumes:
      - ./config:/config     # config.yaml (created on first start, editable in the web UI)
      - ./data:/srv/data     # database + reports
```

```bash
docker compose up -d
docker compose logs -f
```

Open **http://localhost:8080** (user `admin`, password from `WEB_PASSWORD`).

!!! info "First start"
    If `config/config.yaml` does not exist, a starter configuration with the **demo** data
    source is created. You can add cards right away in the web UI. For the fully commented
    template run `cp config.example.yaml config/config.yaml` before the first start.

!!! tip "Permissions"
    The container runs as user `1000`. `config/` and `data/` must be writable for it, otherwise
    the web UI cannot save and the database cannot be created.

### Plain `docker run`

```bash
docker run -d --name cardmarket-tracker --restart unless-stopped \
  -p 8080:8080 \
  -e WEB_PASSWORD=change-me \
  -v "$PWD/config:/config" -v "$PWD/data:/srv/data" \
  ghcr.io/mgummich/cardmarkettracker:latest
```

### Build the image yourself

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
docker compose up -d --build
```

## Python / pip

Requires Python 3.11 or newer.

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
python -m venv .venv && source .venv/bin/activate
pip install .
cp config.example.yaml config.yaml
cmtracker run
```

The web UI listens on **http://127.0.0.1:8080** by default (local only).

### Run as a systemd service

```ini title="/etc/systemd/system/cardmarket-tracker.service"
[Unit]
Description=Cardmarket Tracker
After=network-online.target
Wants=network-online.target

[Service]
User=tracker
WorkingDirectory=/opt/cardmarket-tracker
EnvironmentFile=/opt/cardmarket-tracker/.env
ExecStart=/opt/cardmarket-tracker/.venv/bin/cmtracker -c config.yaml run
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now cardmarket-tracker
```

## Updating

=== "Docker"

    ```bash
    docker compose pull && docker compose up -d
    ```

=== "pip"

    ```bash
    git pull && pip install . && sudo systemctl restart cardmarket-tracker
    ```

The database schema is created and extended automatically. Read the
[changelog](../changelog.md) before updating across minor versions.
