# Configuration reference

Everything is configured in one YAML file, `config.yaml`. Most of it can also be edited in the
[web interface](../usage/web-ui.md). A fully commented template ships as
[`config.example.yaml`](https://github.com/mgummich/cardmarkettracker/blob/main/config.example.yaml).

- Location: `-c/--config PATH`, or the environment variable `CMTRACKER_CONFIG`
  (Docker: `/config/config.yaml`), otherwise `./config.yaml`.
- Check a file with `cmtracker validate` – it also prints the **effective** filters and rules
  of every card.
- Relative paths (database, reports) are relative to the working directory
  (Docker: `/srv`, i.e. `data/…` ends up in the `/srv/data` volume).

## Environment variables

Any string value may contain `${VAR}` or `${VAR:-default}`. Use this for all secrets and keep
them in `.env`:

```yaml
provider:
  mkm_api:
    app_token: ${MKM_APP_TOKEN}
web:
  password: ${WEB_PASSWORD:-}
```

A referenced variable without default that is not set is a configuration error.
Fields that use variables are read-only in the web UI.

## `general`

| Key | Default | Description |
|---|---|---|
| `interval_minutes` | `60` | minutes between two checks of all cards (≥ 1) |
| `jitter_seconds` | `60` | random extra delay per interval, so requests are not perfectly periodic |
| `database` | `data/tracker.db` | SQLite file |
| `timezone` | `Europe/Berlin` | IANA time zone for reports and display |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `keep_offers` | `20` | how many of the cheapest matching offers are stored per check (1–200) |
| `notify_errors` | `false` | send a notification (event `error`) when a card check fails |

## `provider`

| Key | Default | Description |
|---|---|---|
| `type` | `demo` | `mkm_api`, `scraper` or `demo` – see [Data sources](data-sources.md) |
| `mkm_api.app_token` / `app_secret` / `access_token` / `access_token_secret` | – | credentials of your Cardmarket "dedicated app" (required for `mkm_api`) |
| `mkm_api.base_url` | `https://api.cardmarket.com/ws/v2.0/output.json` | API endpoint |
| `mkm_api.max_articles` | `300` | max. offers fetched per card and check (1–1000) |
| `mkm_api.timeout` | `30` | HTTP timeout in seconds |
| `scraper.base_url` | `https://www.cardmarket.com` | |
| `scraper.locale` | `en` | language segment used in product URLs (`en`, `de`, …) |
| `scraper.request_delay_seconds` | `5` | minimum pause between two page requests |
| `scraper.timeout` | `30` | |
| `scraper.user_agent` | desktop Chrome | |
| `scraper.extra_headers` / `scraper.cookies` | `{}` | additional headers / cookies |
| `demo.seed` | `42` | seed for the simulated data |

## `defaults`

Default `filters` and `alerts` for every card (same keys as on a card, see below). A card only
needs to specify what differs.

## `cards`

A list of cards.

| Key | Default | Description |
|---|---|---|
| `name` | – | display name (required) |
| `key` | from `name` | unique ID, e.g. `the-one-ring-ltr`. Set it explicitly to track the same card twice with different filters. **Changing it detaches the history.** |
| `game` | `Magic` | free text (`Magic`, `Pokemon`, `YuGiOh`, …) |
| `product_id` | – | Cardmarket product ID, required for `mkm_api` |
| `url` | – | product page URL, required for `scraper` |
| `enabled` | `true` | `false` pauses the card |
| `notes` | – | free text |
| `filters` | – | overrides of `defaults.filters` |
| `alerts` | – | overrides of `defaults.alerts` |
| `buy` | – | auto-buy rules, see [Auto-buy](../usage/auto-buy.md) |

### Filters

Applied to every offer. **If a filter is set and the offer's attribute is unknown, the offer
does not match** – better one alert too few than a wrong purchase.

| Key | Type | Description |
|---|---|---|
| `languages` | list | e.g. `[German, English]`; also accepts `de`, `Deutsch`, IDs `1`–`11` |
| `min_condition` | string | `MT`, `NM`, `EX`, `GD`, `LP`, `PL`, `PO` (or `near mint`, …) – this or better |
| `foil` / `signed` / `altered` / `first_edition` | bool | `true` = only, `false` = never, `null` = don't care |
| `seller_countries` | list | only sellers from these countries (`DE`, `Germany`, `Deutschland`, …) |
| `exclude_seller_countries` | list | no sellers from these countries |
| `seller_types` | list | `private`, `professional`, `powerseller` |
| `exclude_sellers` | list | user names to ignore (case-insensitive) |
| `min_price` | number | ignore offers below this price (bait listings) |

Merging: keys **present** on the card replace the default; `null` explicitly means
"don't care"; missing keys inherit.

### Alerts

| Key | Default | Description |
|---|---|---|
| `enabled` | `true` | |
| `max_price` | – | target price |
| `drop_percent` | – | drop since the previous check, 0–100 |
| `below_reference_percent` | – | distance below the reference price, 0–100 |
| `reference` | `trend` | `trend`, `avg1`, `avg7`, `avg30`, `low` |
| `all_time_low` | `false` | alert on a new all-time low |
| `cooldown_hours` | `12` | see [Alerts](../usage/alerts.md#cooldown) |

### Buy

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | |
| `max_price` | – | required when enabled |
| `quantity` | `1` | how many copies in total |
| `filters` | – | additional filters for buying (applied on top of the card filters) |

## `notifications`

A list of channels; see [Notifications](notifications.md). Without any entry, messages go to
the log only.

## `reports`

| Key | Default | Description |
|---|---|---|
| `output_dir` | `data/reports` | |
| `daily_time` | `"08:00"` | `HH:MM` local time, `null` = off |
| `history_days` | `30` | period covered by the report |
| `top_offers` | `5` | offers per card in the report |
| `send_summary` | `true` | send a short summary (event `report`) |
| `attach_html` | `true` | attach the HTML file |
| `public_url` | – | base URL under which `/reports/` is reachable, linked in messages |

## `purchasing`

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | global switch |
| `mode` | `dry_run` | `dry_run` or `cart` (requires `mkm_api`) |
| `max_per_run` | `50` | budget per check (€) |
| `max_per_month` | `200` | budget per calendar month (€) |

## `web`

| Key | Default | Description |
|---|---|---|
| `enabled` | `true` | start the web UI together with `cmtracker run` |
| `host` | `127.0.0.1` | listen address (Docker image: `0.0.0.0` via command line) |
| `port` | `8080` | |
| `username` | `admin` | user for HTTP basic auth |
| `password` | – | enables HTTP basic auth – **set it** whenever the UI is reachable from other machines |

## Complete example

```yaml
--8<-- "config.example.yaml"
```
