# Kommandozeile

```text
cmtracker [-c CONFIG] [--log-level LEVEL] [--version] <befehl> [optionen]
```

| Option | Beschreibung |
|---|---|
| `-c`, `--config` | Pfad zur `config.yaml` (Standard: `$CMTRACKER_CONFIG` oder `./config.yaml`) |
| `--log-level` | überschreibt `general.log_level` |

Ausgabesprache: `general.language` aus der Konfiguration. Meldungen vor dem Laden der
Konfiguration (z.B. „Datei nicht gefunden“) richten sich nach der Umgebungsvariable
`CMTRACKER_LANGUAGE` (`en`/`de`, Standard `en`).

Unter Docker den Befehlen `docker compose exec tracker` voranstellen, z.B.
`docker compose exec tracker cmtracker check`.

## `run`

Dauerbetrieb: Prüfungen nach Zeitplan, Tagesbericht, Weboberfläche. Legt eine
Start-Konfiguration an, falls keine existiert. Beendet sich bei `SIGTERM` / `Strg+C` sauber
(eine laufende Prüfung wird zuerst abgeschlossen).

```bash
cmtracker run [--no-web] [--host HOST] [--port PORT]
```

## `web`

Nur die Weboberfläche; Prüfungen laufen nur per *Jetzt prüfen*. Nützlich neben einem anderen
Scheduler oder zum reinen Ansehen.

```bash
cmtracker web [--host HOST] [--port PORT]
```

## `check`

Einmalige Prüfung aller (oder ausgewählter) Karten, danach Ende. Alarme und Auto-Kauf
funktionieren wie gewohnt. Exit-Code `1`, wenn alle Karten fehlschlagen.

```bash
cmtracker check
cmtracker check --card the-one-ring-ltr --card sol-ring-foil
```

## `report`

```bash
cmtracker report          # data/reports/report_….html und latest.html schreiben
cmtracker report --send   # … und Zusammenfassung an die "report"-Kanäle schicken
```

## `validate`

Prüft die Konfiguration und zeigt die effektiven Filter, Alarme und Kauf-Regeln jeder Karte.
Exit-Code `2` bei Fehlern – praktisch in CI oder vor einem Neustart.

## `test-notify`

Schickt für jeden Ereignistyp eine Testnachricht an alle Kanäle.

## `history`, `export`, `purchases`

```bash
cmtracker history the-one-ring-ltr --days 14     # Tabelle im Terminal
cmtracker export the-one-ring-ltr -o ring.csv    # gesamter Verlauf als CSV (;)
cmtracker purchases --limit 20                   # (simulierte) Käufe
```

## `serve`

Liefert nur den Berichtsordner per HTTP aus (älterer Befehl; die Weboberfläche zeigt Berichte
auch unter `/reports/`).

```bash
cmtracker serve --port 8080
```
