# Reports

A detailed HTML report is generated daily (default `08:00`, local time zone):

- summary table: low, change 24 h / 7 d / 30 d, vs. trend, trend, all-time low, offers
- per card: key figures, price chart (low, trend, 30-day average), cheapest offers, alerts
- dark mode, works offline, no external resources

```yaml
reports:
  output_dir: data/reports
  daily_time: "08:00"      # null = no automatic report
  history_days: 30
  top_offers: 5
  send_summary: true       # short text summary via notification channels (event "report")
  attach_html: true        # attach the HTML file (Telegram, Discord, e-mail)
  public_url: null         # e.g. https://tracker.example.com/reports
```

Files: `report_YYYY-MM-DD_HHMM.html` plus `latest.html`. In the web UI they are available at
`/reports/latest.html` and listed under *System*.

## Manual reports and exports

```bash
cmtracker report            # generate
cmtracker report --send     # generate and send the summary
cmtracker export the-one-ring-ltr -o one-ring.csv   # full history as CSV (semicolon separated)
cmtracker history the-one-ring-ltr --days 14        # history in the terminal
```

CSV columns: `taken_at`, `offers_matching`, `offers_total`, `min_price`, `avg5`, `median`,
`trend`, `avg1`, `avg7`, `avg30`, `low`.

The report is written in `general.language`.

For your own dashboards (Grafana, Home Assistant, spreadsheets) use the [JSON API](../reference/api.md).
