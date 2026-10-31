# Installation

Cardmarket Tracker läuft überall, wo Python 3.11+ oder Docker läuft – auf einem Heimserver,
NAS, Raspberry Pi (arm64) oder einem kleinen VPS.

## Docker (empfohlen)

Fertige Multi-Arch-Images (`linux/amd64`, `linux/arm64`) liegen in der GitHub Container
Registry: `ghcr.io/mgummich/cardmarkettracker`.

| Tag | Bedeutung |
|---|---|
| `latest` | neuester Stand des `main`-Branches |
| `0.2.0`, `0.2` | ein bestimmtes Release |
| `sha-<commit>` | ein bestimmter Commit |

### Docker Compose

```bash
mkdir cardmarket-tracker && cd cardmarket-tracker
curl -LO https://raw.githubusercontent.com/mgummich/cardmarkettracker/main/docker-compose.yml
curl -L -o .env https://raw.githubusercontent.com/mgummich/cardmarkettracker/main/.env.example
mkdir -p config data && sudo chown -R 1000:1000 config data
```

In der `.env` mindestens `WEB_PASSWORD` setzen. Die Compose-Datei sieht so aus:

```yaml
services:
  tracker:
    image: ghcr.io/mgummich/cardmarkettracker:latest
    build: .                 # nur bei "docker compose up --build" in einem Git-Checkout
    container_name: cardmarket-tracker
    restart: unless-stopped
    env_file: .env
    ports:
      - "8080:8080"
    volumes:
      - ./config:/config     # config.yaml (wird beim ersten Start angelegt, per Weboberfläche bearbeitbar)
      - ./data:/srv/data     # Datenbank + Berichte
```

```bash
docker compose up -d
docker compose logs -f
```

Dann **http://localhost:8080** öffnen (Benutzer `admin`, Passwort aus `WEB_PASSWORD`).

!!! tip "Deutsch einstellen"
    Die Oberfläche folgt deiner Browsersprache (Umschalter **EN / DE** oben rechts). Für
    deutsche Benachrichtigungen und Berichte unter *Einstellungen → Prüfung & Sprache* auf
    *Deutsch* stellen (entspricht `general.language: de`).

!!! info "Erster Start"
    Gibt es noch keine `config/config.yaml`, wird eine Start-Konfiguration mit der
    **Demo**-Datenquelle angelegt. Karten kannst du sofort in der Weboberfläche hinzufügen.
    Für die vollständig kommentierte Vorlage vor dem ersten Start
    `cp config.example.yaml config/config.yaml` ausführen.

!!! tip "Berechtigungen"
    Der Container läuft als Benutzer `1000`. `config/` und `data/` müssen für ihn beschreibbar
    sein, sonst kann die Weboberfläche nicht speichern und die Datenbank nicht angelegt werden.

### Einfaches `docker run`

```bash
docker run -d --name cardmarket-tracker --restart unless-stopped \
  -p 8080:8080 \
  -e WEB_PASSWORD=bitte-aendern \
  -v "$PWD/config:/config" -v "$PWD/data:/srv/data" \
  ghcr.io/mgummich/cardmarkettracker:latest
```

### Image selbst bauen

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
docker compose up -d --build
```

## Python / pip

Benötigt Python 3.11 oder neuer.

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
python -m venv .venv && source .venv/bin/activate
pip install .
cp config.example.yaml config.yaml
cmtracker run
```

Die Weboberfläche lauscht standardmäßig nur lokal auf **http://127.0.0.1:8080**.

### Als systemd-Dienst

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

## Aktualisieren

=== "Docker"

    ```bash
    docker compose pull && docker compose up -d
    ```

=== "pip"

    ```bash
    git pull && pip install . && sudo systemctl restart cardmarket-tracker
    ```

Das Datenbankschema wird automatisch angelegt und erweitert. Lies vor Updates über mehrere
Minor-Versionen den [Changelog](../changelog.md).
