# Auto-buy (experimental)

!!! danger "Experimental"
    Auto-buy is new and only lightly tested against the real Cardmarket API. Always start
    with `dry_run`, use small budgets and check what happens. You use it at your own risk.

## What it does

When a card's matching offers include one at or below the card's **max buy price**, the
tracker "buys" it – within all limits:

1. `purchasing.enabled: true` (global switch) **and** `buy.enabled: true` on the card
2. the offer matches the card filters **and** the optional, stricter `buy.filters`
3. price ≤ `buy.max_price`
4. the wanted quantity (`buy.quantity`) is not reached yet
5. the budget per check (`max_per_run`) and per calendar month (`max_per_month`) is not exceeded

The cheapest offers are taken first; an article is never bought twice.

| Mode | Behaviour |
|---|---|
| `dry_run` (default) | nothing is bought – decisions are logged, stored and sent as notification (event `purchase`) |
| `cart` | the article is added to your Cardmarket **shopping cart** via the API. **You still pay manually** on cardmarket.com |

`cart` requires the `mkm_api` data source. A fully automatic checkout is not implemented.

## Configuration

```yaml
purchasing:
  enabled: true
  mode: dry_run
  max_per_run: 50       # € per check, without shipping
  max_per_month: 200    # € per calendar month

cards:
  - name: The One Ring (LTR)
    product_id: 710549
    buy:
      enabled: true
      max_price: 40
      quantity: 1
      filters:              # stricter filters only for buying
        min_condition: NM
        seller_countries: [DE, AT]
```

In dry-run mode, simulated purchases count towards quantity and budget (so the simulation
behaves like the real thing). List them with `cmtracker purchases` or on the *Activity* page.

## Limitations

- **Shipping costs are not considered.** Several cheap offers from different sellers can cost
  more in total than one slightly more expensive offer.
- Offers can disappear between check and purchase; failures are reported as `failed`.
- Budgets are tracked locally, not on Cardmarket.
