# Data sources

| | `mkm_api` | `scraper` | `demo` |
|---|---|---|---|
| Data | official Cardmarket API | public product page | simulated |
| Reliability | high | low (bot protection, HTML changes) | – |
| Offers per card | up to `max_articles` (default 300) | first page (~50 cheapest) | 12–30 |
| Price guide (trend, averages) | ✔ | ✔ (parsed) | ✔ (simulated) |
| Auto-buy `cart` mode | ✔ | – | – |
| Needs | API credentials | product URL | nothing |

## Cardmarket API (`mkm_api`) – recommended

Uses the [MKM API v2.0](https://api.cardmarket.com/ws/documentation) with OAuth 1.0a.

### Getting credentials

1. Log in to cardmarket.com and open **Account → Settings → API** (the exact location may change).
2. Create a **Dedicated App**. You receive an *App token* and *App secret*.
3. Generate an *Access token* and *Access token secret* for the app.
4. Put all four into `.env`:

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

!!! warning "API access is limited"
    Cardmarket does not grant API access to every account. If you cannot create an app,
    contact Cardmarket support or use the scraper as a fallback.

### Finding the product ID

The ID identifies the exact product (card + edition). With API access, search for it:

```text
GET https://api.cardmarket.com/ws/v2.0/output.json/products/find?search=The%20One%20Ring&idGame=1
```

`idGame`: 1 = Magic, 3 = Yu-Gi-Oh!, 6 = Pokémon (see the API docs for others). A `cmtracker
search` command is on the roadmap.

### Request budget

Per card and check: 1 request for the product + 1 per 100 offers. Example: 20 cards with
< 100 offers, checked hourly → 40 × 24 = **960 requests / day**. Stay well below the daily limit
of your access level; HTTP 429 is reported as error.

Server-side pre-filtering is used where the API supports it (single language, minimum
condition, foil, signed, altered); everything else is filtered locally.

## Scraper (`scraper`) – fallback

Fetches the public product page, e.g.
`https://www.cardmarket.com/en/Magic/Products/Singles/Alpha/Black-Lotus`, adds your filters as
URL parameters (`language`, `minCondition`, `isFoil`, `sellerType`, …) and parses the offers.

```yaml
provider:
  type: scraper
  scraper:
    locale: en
    request_delay_seconds: 8
cards:
  - name: Black Lotus
    url: https://www.cardmarket.com/en/Magic/Products/Singles/Alpha/Black-Lotus
```

!!! warning "Use responsibly"
    - Cardmarket uses bot protection (Cloudflare). Requests may fail with HTTP 403; the error
      is shown on the card. Use long intervals and generous delays.
    - HTML changes can break the parser. Please [open an issue](https://github.com/mgummich/cardmarkettracker/issues)
      with the card URL if parsing fails.
    - Check Cardmarket's terms of service before scraping.

## Demo (`demo`)

Generates reproducible, plausible offers that vary over time. Perfect to try the dashboard,
alerts, reports and notifications, or for development. No network access.
