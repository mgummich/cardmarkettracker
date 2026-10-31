# Auto-Kauf (experimentell)

!!! danger "Experimentell"
    Der Auto-Kauf ist neu und gegen die echte Cardmarket-API erst wenig getestet. Beginne
    immer mit `dry_run`, nutze kleine Budgets und kontrolliere, was passiert. Nutzung auf
    eigene Verantwortung.

## Was er tut

Ist unter den passenden Angeboten einer Karte eines zum **max. Kaufpreis** oder günstiger,
„kauft“ der Tracker es – innerhalb aller Grenzen:

1. `purchasing.enabled: true` (globaler Schalter) **und** `buy.enabled: true` bei der Karte
2. das Angebot erfüllt die Filter der Karte **und** die optionalen, strengeren `buy.filters`
3. Preis ≤ `buy.max_price`
4. die gewünschte Stückzahl (`buy.quantity`) ist noch nicht erreicht
5. das Budget pro Prüfung (`max_per_run`) und pro Kalendermonat (`max_per_month`) reicht

Die günstigsten Angebote werden zuerst genommen; ein Artikel wird nie doppelt gekauft.

| Modus | Verhalten |
|---|---|
| `dry_run` (Standard) | es wird nichts gekauft – Entscheidungen werden protokolliert, gespeichert und gemeldet (Ereignis `purchase`) |
| `cart` | der Artikel wird über die API in deinen Cardmarket-**Warenkorb** gelegt. **Bezahlen musst du selbst** auf cardmarket.com |

`cart` benötigt die Datenquelle `mkm_api`. Ein vollautomatischer Checkout ist nicht umgesetzt.

## Konfiguration

```yaml
purchasing:
  enabled: true
  mode: dry_run
  max_per_run: 50       # € pro Prüfung, ohne Versand
  max_per_month: 200    # € pro Kalendermonat

cards:
  - name: The One Ring (LTR)
    product_id: 710549
    buy:
      enabled: true
      max_price: 40
      quantity: 1
      filters:              # strengere Filter nur für den Kauf
        min_condition: NM
        seller_countries: [DE, AT]
```

Im Probelauf zählen simulierte Käufe für Stückzahl und Budget mit (die Simulation verhält
sich also wie echt). Anzeigen mit `cmtracker purchases` oder auf der Seite *Aktivität*.

## Einschränkungen

- **Versandkosten werden nicht berücksichtigt.** Mehrere günstige Angebote verschiedener
  Verkäufer können in Summe teurer sein als ein etwas teureres Angebot.
- Angebote können zwischen Prüfung und Kauf verschwinden; Fehler werden als `failed` gemeldet.
- Budgets werden lokal gezählt, nicht bei Cardmarket.
