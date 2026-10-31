# JSON API

Read-only JSON endpoints for your own dashboards and automations. They use the same
authentication as the web UI (HTTP basic auth if `web.password` is set). Interactive OpenAPI
documentation is available at **`/api/docs`**.

## `GET /api/status`

```json
{
  "version": "0.2.0",
  "cards": 3,
  "provider": "mkm_api",
  "config_error": null,
  "runner": {
    "scheduling": true,
    "running": false,
    "busy": false,
    "current_task": null,
    "last_check_at": "2026-10-31T19:00:12Z",
    "next_check_at": "2026-10-31T20:01:40Z",
    "last_check_errors": 0
  }
}
```

## `GET /api/cards`

```json
[
  {
    "key": "the-one-ring-ltr",
    "name": "The One Ring (LTR)",
    "enabled": true,
    "state": "ok",
    "min_price": 43.9,
    "trend": 52.1,
    "offer_count": 4,
    "checked_at": "2026-10-31T19:00:10Z",
    "change_24h": -3.5,
    "change_7d": -11.2,
    "target": 45.0,
    "all_time_low": 41.5,
    "error": null
  }
]
```

`state`: `ok`, `hit` (target reached), `error`, `new`, `paused`. Changes are percentages.

## `GET /api/cards/{key}/history?days=30`

`days` may be omitted for the full history.

```json
[
  {
    "taken_at": "2026-10-31T19:00:10+00:00",
    "min_price": 43.9,
    "avg5_price": 47.2,
    "median_price": 49.0,
    "offer_count": 4,
    "trend": 52.1,
    "avg30": 50.3
  }
]
```

## Examples

```bash
curl -u admin:$WEB_PASSWORD http://localhost:8080/api/cards | jq '.[] | {name, min_price}'
```

??? example "Home Assistant REST sensor"
    ```yaml
    rest:
      - resource: http://cardmarket-tracker:8080/api/cards
        authentication: basic
        username: admin
        password: !secret cmtracker_password
        scan_interval: 900
        sensor:
          - name: One Ring low
            unit_of_measurement: "€"
            value_template: >
              {{ (value_json | selectattr('key', 'eq', 'the-one-ring-ltr') | first).min_price }}
    ```
