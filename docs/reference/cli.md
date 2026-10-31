# Command line

```text
cmtracker [-c CONFIG] [--log-level LEVEL] [--version] <command> [options]
```

| Option | Description |
|---|---|
| `-c`, `--config` | path to `config.yaml` (default: `$CMTRACKER_CONFIG` or `./config.yaml`) |
| `--log-level` | overrides `general.log_level` |

Output language: `general.language` from the configuration. Messages printed before the
configuration is loaded (e.g. "file not found") use the environment variable
`CMTRACKER_LANGUAGE` (`en`/`de`, default `en`).

In Docker, prefix commands with `docker compose exec tracker`, e.g.
`docker compose exec tracker cmtracker check`.

## `run`

Continuous operation: checks on schedule, daily report, web UI. Creates a starter config if
none exists. Stops gracefully on `SIGTERM` / `Ctrl+C` (a running check is finished first).

```bash
cmtracker run [--no-web] [--host HOST] [--port PORT]
```

## `web`

Only the web UI; checks run only when triggered with *Check now*. Useful next to another
scheduler or for read-only browsing.

```bash
cmtracker web [--host HOST] [--port PORT]
```

## `check`

One check of all cards (or selected ones) and exit. Alerts and auto-buy work as usual.
Exit code `1` if every card failed.

```bash
cmtracker check
cmtracker check --card the-one-ring-ltr --card sol-ring-foil
```

## `report`

```bash
cmtracker report          # write data/reports/report_….html and latest.html
cmtracker report --send   # … and send the summary to the "report" channels
```

## `validate`

Validates the configuration and prints the effective filters, alerts and buy rules of every
card. Exit code `2` on errors – handy in CI or before a restart.

## `test-notify`

Sends a test message for each event type to all configured channels.

## `history`, `export`, `purchases`

```bash
cmtracker history the-one-ring-ltr --days 14     # table in the terminal
cmtracker export the-one-ring-ltr -o ring.csv    # full history as CSV (;)
cmtracker purchases --limit 20                   # (simulated) purchases
```

## `serve`

Serves only the report directory via HTTP (legacy; the web UI also serves reports at `/reports/`).

```bash
cmtracker serve --port 8080
```
