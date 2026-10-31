# Preisalarme

Alarme vergleichen den **aktuellen Tiefstpreis** – das günstigste Angebot, das den Filtern der
Karte entspricht – mit deinen Regeln. Alle Regeln lassen sich kombinieren und werden
unabhängig voneinander geprüft.

| Regel | Schlüssel | Löst aus, wenn |
|---|---|---|
| Zielpreis | `max_price` | Tiefstpreis ≤ Zielpreis |
| Preissturz | `drop_percent` | Tiefstpreis seit der letzten Prüfung um mind. X % gefallen |
| Unter Referenzpreis | `below_reference_percent` + `reference` | Tiefstpreis mind. X % unter dem Referenzpreis |
| Allzeit-Tief | `all_time_low: true` | Tiefstpreis niedriger als jeder bisherige dieser Karte |

`reference` ist `trend` (Standard), `avg1`, `avg7`, `avg30` (1-/7-/30-Tage-Schnitt von
Cardmarket) oder `low` (der „ab“-Preis). Bei Foil-Filtern (`foil: true`) wird – sofern die
Datenquelle sie liefert – die Foil-Preisübersicht verwendet.

## Wartezeit (Cooldown)

Gegen Spam meldet dieselbe Regel für dieselbe Karte höchstens einmal pro `cooldown_hours`
(Standard 12) – **außer der Preis ist seit dem letzten Alarm dieser Regel weiter gefallen**.

Beispiel mit `max_price: 45`, `cooldown_hours: 12`:

| Uhrzeit | Tiefstpreis | Alarm? |
|---|---|---|
| 08:00 | 47,00 € | nein |
| 09:00 | 44,50 € | **ja** – unter Zielpreis |
| 10:00 | 44,50 € | nein – Wartezeit |
| 11:00 | 43,90 € | **ja** – günstiger als beim letzten Alarm |
| 21:30 | 44,10 € | **ja** – Wartezeit abgelaufen |

Alle in einer Prüfung ausgelösten Regeln werden zu einer Nachricht zusammengefasst
(Sprache: `general.language`, hier `de`):

```text
Preisalarm: The One Ring (LTR)
Günstigstes passendes Angebot: 43,90 € (NM, Englisch) – seller_x, Deutschland [2x verfügbar]
Passende Angebote: 4 (von 31)
Preistrend: 52,10 €

Ausgelöst durch:
• Preis ≤ Zielpreis 45,00 €
• 15,7 % unter Preistrend (52,10 €)
```

## Standardwerte und Überschreiben

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
      max_price: 45          # zusätzlich für diese Karte
      drop_percent: null     # für diese Karte abgeschaltet
```

Bei der Karte gesetzte Schlüssel überschreiben die Standardwerte; `null` schaltet eine Regel
ab. In der Weboberfläche heißt das „leer = Standard“ und `aus` = abgeschaltet.

!!! tip "Gute Startwerte"
    - Karten, die du *kaufen* willst: `max_price` knapp unter dem, was du zahlen würdest.
    - Karten, die du *beobachtest*: `below_reference_percent: 15` mit `reference: avg30` findet
      echte Schnäppchen und ignoriert normale Schwankungen.
    - `min_price` in den Filtern blendet Lockangebote (z.B. 0,02 €) aus.
