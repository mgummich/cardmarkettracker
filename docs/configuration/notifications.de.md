# Benachrichtigungen

Unter `notifications` beliebig viele Kanäle eintragen. Jeder Kanal hat zwei optionale Schlüssel:

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `name` | Kanaltyp | Name in Log und Oberfläche |
| `events` | alle | welche Ereignisse der Kanal bekommt: `alert`, `report`, `purchase`, `error` |

```yaml
notifications:
  - type: telegram           # alles an Telegram
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
  - type: email              # nur den Tagesbericht per E-Mail
    events: [report]
    ...
```

Alle Kanäle testen: **System → Testnachricht senden** oder `cmtracker test-notify`.
Ein fehlerhafter Kanal wird protokolliert und blockiert nie die anderen.

## Telegram

1. [@BotFather](https://t.me/BotFather) anschreiben, `/newbot` senden und das Token kopieren.
2. Dem neuen Bot eine beliebige Nachricht schicken.
3. Chat-ID ermitteln: `https://api.telegram.org/bot<TOKEN>/getUpdates` öffnen und
   `message.chat.id` ablesen (oder [@userinfobot](https://t.me/userinfobot) fragen). Gruppen-IDs sind negativ.

```yaml
- type: telegram
  bot_token: ${TELEGRAM_BOT_TOKEN}
  chat_id: ${TELEGRAM_CHAT_ID}
```

Berichte kommen als Nachricht plus HTML-Dokument.

## Discord

Kanaleinstellungen → **Integrationen → Webhooks → Neuer Webhook** → URL kopieren.

```yaml
- type: discord
  webhook_url: ${DISCORD_WEBHOOK_URL}
  username: Cardmarket Tracker   # optional
```

Nachrichten erscheinen als Embeds (orange = Alarm, grün = Kauf, rot = Fehler).

## ntfy

Push-Benachrichtigungen auf Handy und Desktop über [ntfy](https://ntfy.sh) – öffentlicher
Server oder selbst gehostet.

```yaml
- type: ntfy
  server: https://ntfy.sh      # oder dein eigener Server
  topic: ${NTFY_TOPIC}         # auf ntfy.sh etwas schwer Erratbares wählen!
  token: ${NTFY_TOKEN:-}       # optional, für geschützte Topics
  priority: 4                  # optional, 1–5
```

Ein Tipp auf die Benachrichtigung öffnet die Karte auf Cardmarket.

## E-Mail (SMTP)

```yaml
- type: email
  host: smtp.example.com
  port: 587
  security: starttls        # starttls (587) | ssl (465) | none
  username: ${SMTP_USER}
  password: ${SMTP_PASSWORD}
  sender: tracker@example.com
  recipients: [ich@example.com]
  events: [report, purchase]
```

Der HTML-Bericht wird angehängt, wenn `reports.attach_html` aktiv ist. Für Gmail ein
App-Passwort verwenden.

## Webhook

Sendet JSON an eine beliebige URL – ideal für Home Assistant, n8n, Node-RED oder eigene Skripte.

```yaml
- type: webhook
  url: https://example.com/hook
  headers:
    Authorization: Bearer ${WEBHOOK_TOKEN}
```

Inhalt:

```json
{
  "event": "alert",
  "title": "Preisalarm: The One Ring (LTR)",
  "message": "Günstigstes passendes Angebot: 43,90 € …",
  "url": "https://www.cardmarket.com/de/Magic/Products/Singles/…"
}
```

??? example "Home-Assistant-Automation"
    ```yaml
    automation:
      - alias: Cardmarket-Alarm
        trigger:
          - platform: webhook
            webhook_id: cardmarket-tracker
            local_only: true
        action:
          - service: notify.mobile_app_mein_handy
            data:
              title: "{{ trigger.json.title }}"
              message: "{{ trigger.json.message }}"
              data:
                url: "{{ trigger.json.url }}"
    ```
    Kanal-URL: `http://homeassistant.local:8123/api/webhook/cardmarket-tracker`

## Konsole

Schreibt Meldungen ins Log – Standard, wenn kein Kanal eingerichtet ist.

```yaml
- type: console
```
