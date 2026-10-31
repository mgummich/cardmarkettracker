# Troubleshooting & FAQ

## The web UI shows "config.yaml ist fehlerhaft"

The file contains an error (YAML syntax or invalid value). The message names the field, e.g.
`cards.2.alerts.max_price`. The last valid configuration keeps running. Fix the file or restore
`config.yaml.bak`. `cmtracker validate` shows the same messages.

## "Umgebungsvariable X ist nicht gesetzt"

The config references `${X}` without default and `X` is not set. Add it to `.env` (and restart
the container) or use `${X:-}` for an optional empty value.

## Saving in the web UI fails with "Permission denied"

The container user (UID 1000) cannot write to `config/`: `sudo chown -R 1000:1000 config data`.

## Forms fail with "Ungültige Herkunft der Anfrage (CSRF-Schutz)"

Your reverse proxy changes the `Host` header. Pass it through
(nginx: `proxy_set_header Host $host;`).

## A card shows "Fehler"

The error message is shown on the card page. Common causes:

| Message | Cause / fix |
|---|---|
| `Authentifizierung fehlgeschlagen (401/403)` | wrong or revoked API tokens |
| `Tageslimit an Requests erreicht (429)` | too many requests – increase `interval_minutes` |
| `HTTP 403 (Bot-Schutz/Rate-Limit)` | scraper blocked by Cloudflare – longer intervals or use the API |
| `Produkt … nicht gefunden` | wrong `product_id` |

Enable `general.notify_errors` to be informed about errors by message.

## A card has 0 matching offers

Your filters are stricter than the market. The card page shows "x matching of y offers".
Remember: if a filter is set and the offer attribute is unknown, the offer does not match.
Try relaxing `seller_countries`, `languages` or `min_condition`.

## No alert although the price is below my target

- Is the card enabled and does the check run (*System* page)?
- Alerts compare the **filtered** low, not Cardmarket's "from" price.
- Cooldown: the same rule only fires again after `cooldown_hours` unless the price fell further.
- Is a notification channel configured for the event `alert`? Use *Send test message*.

## The daily report was not sent

It is sent once per day after `reports.daily_time` (local time zone), only by `cmtracker run`
and only when at least one card is configured. If the tracker starts after that time, the
report is sent right away.

## Are shipping costs included?

No. All prices are article prices without shipping.

## Can it buy cards fully automatically?

Not yet. The `cart` mode puts the article into your Cardmarket shopping cart; you pay manually.
