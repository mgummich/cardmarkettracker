# Alerts

Alerts compare the **current low** – the cheapest offer that matches the card's filters –
with your rules. All rules can be combined; each one is evaluated independently.

| Rule | Config key | Fires when |
|---|---|---|
| Target price | `max_price` | low ≤ target price |
| Price drop | `drop_percent` | low fell by at least X % since the previous check |
| Below reference | `below_reference_percent` + `reference` | low is at least X % below the reference price |
| All-time low | `all_time_low: true` | low is lower than every previous low of this card |

`reference` is one of `trend` (default), `avg1`, `avg7`, `avg30` (Cardmarket's 1/7/30-day
averages) or `low` (Cardmarket's "from" price). For foil filters (`foil: true`) the foil price
guide is used when the data source provides it.

## Cooldown

To avoid spam, the same rule for the same card fires at most once per `cooldown_hours`
(default 12) – **unless the price fell further** since the last alert of that rule.

Example with `max_price: 45`, `cooldown_hours: 12`:

| Time | Low | Alert? |
|---|---|---|
| 08:00 | 47.00 € | no |
| 09:00 | 44.50 € | **yes** – below target |
| 10:00 | 44.50 € | no – cooldown |
| 11:00 | 43.90 € | **yes** – cheaper than at the last alert |
| 21:30 | 44.10 € | **yes** – cooldown expired |

All rules triggered in one check are combined into one message (messages are currently
German):

```text
Preisalarm: The One Ring (LTR)
Günstigstes passendes Angebot: 43,90 € (NM, Englisch) – seller_x, Deutschland [2x verfügbar]
Passende Angebote: 4 (von 31)
Preistrend: 52,10 €

Ausgelöst durch:
• Preis ≤ Zielpreis 45,00 €
• 15,7 % unter Preistrend (52,10 €)
```

## Defaults and overrides

```yaml
defaults:
  alerts:
    drop_percent: 10
    below_reference_percent: 15
    all_time_low: true
    cooldown_hours: 12

cards:
  - name: The One Ring (LTR)
    alerts:
      max_price: 45          # added for this card
      drop_percent: null     # disabled for this card
```

Keys set on the card override the defaults; `null` disables a rule. In the web UI that is
"empty = default" and `aus` = off.

!!! tip "Good starting values"
    - Cards you want to *buy*: `max_price` slightly below what you would pay.
    - Cards you *watch*: `below_reference_percent: 15` with `reference: avg30` catches real
      deals and ignores normal fluctuation.
    - Use `min_price` in the filters to ignore bait offers (e.g. 0.02 € listings).
