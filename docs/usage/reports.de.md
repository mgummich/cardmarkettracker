# Berichte

Täglich (Standard `08:00`, lokale Zeitzone) entsteht ein ausführlicher HTML-Bericht:

- Übersichtstabelle: Tiefstpreis, Änderung 24 h / 7 T / 30 T, vs. Trend, Trend, Allzeit-Tief, Angebote
- pro Karte: Kennzahlen, Preisdiagramm (Tiefstpreis, Trend, 30-Tage-Schnitt), günstigste Angebote, Alarme
- Darkmode, funktioniert offline, keine externen Ressourcen

```yaml
reports:
  output_dir: data/reports
  daily_time: "08:00"      # null = kein automatischer Bericht
  history_days: 30
  top_offers: 5
  send_summary: true       # kurze Zusammenfassung über die Kanäle (Ereignis "report")
  attach_html: true        # HTML-Datei anhängen (Telegram, Discord, E-Mail)
  public_url: null         # z.B. https://tracker.example.com/reports
```

Dateien: `report_JJJJ-MM-TT_HHMM.html` sowie `latest.html`. In der Weboberfläche unter
`/reports/latest.html` und auf der Seite *System*.

## Manuelle Berichte und Exporte

```bash
cmtracker report            # erzeugen
cmtracker report --send     # erzeugen und Zusammenfassung verschicken
cmtracker export the-one-ring-ltr -o one-ring.csv   # gesamter Verlauf als CSV (Semikolon)
cmtracker history the-one-ring-ltr --days 14        # Verlauf im Terminal
```

CSV-Spalten: `taken_at`, `offers_matching`, `offers_total`, `min_price`, `avg5`, `median`,
`trend`, `avg1`, `avg7`, `avg30`, `low`.

Der Bericht wird in `general.language` geschrieben.

Für eigene Dashboards (Grafana, Home Assistant, Tabellen) gibt es die [JSON-API](../reference/api.md).
