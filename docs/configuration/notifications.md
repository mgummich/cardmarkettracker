# Notifications

Add any number of channels under `notifications`. Every channel has two optional keys:

| Key | Default | Description |
|---|---|---|
| `name` | channel type | name shown in logs and the UI |
| `events` | all | which events the channel receives: `alert`, `report`, `purchase`, `error` |

```yaml
notifications:
  - type: telegram           # everything to Telegram
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
  - type: email              # only the daily report by e-mail
    events: [report]
    ...
```

Test all channels with **System → Send test message** or `cmtracker test-notify`.
A failing channel is logged and never blocks the others.

## Telegram

1. Talk to [@BotFather](https://t.me/BotFather), send `/newbot` and copy the token.
2. Send any message to your new bot.
3. Get your chat ID: open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read
   `message.chat.id` (or ask [@userinfobot](https://t.me/userinfobot)). Group IDs are negative.

```yaml
- type: telegram
  bot_token: ${TELEGRAM_BOT_TOKEN}
  chat_id: ${TELEGRAM_CHAT_ID}
```

Reports are sent as message plus HTML document.

## Discord

Channel settings → **Integrations → Webhooks → New webhook** → copy URL.

```yaml
- type: discord
  webhook_url: ${DISCORD_WEBHOOK_URL}
  username: Cardmarket Tracker   # optional
```

Messages are sent as embeds (orange = alert, green = purchase, red = error).

## ntfy

Push notifications to phone and desktop via [ntfy](https://ntfy.sh) – public server or self-hosted.

```yaml
- type: ntfy
  server: https://ntfy.sh      # or your own server
  topic: ${NTFY_TOPIC}         # pick something hard to guess on ntfy.sh!
  token: ${NTFY_TOKEN:-}       # optional, for protected topics
  priority: 4                  # optional, 1–5
```

Tapping the notification opens the card on Cardmarket.

## E-mail (SMTP)

```yaml
- type: email
  host: smtp.example.com
  port: 587
  security: starttls        # starttls (587) | ssl (465) | none
  username: ${SMTP_USER}
  password: ${SMTP_PASSWORD}
  sender: tracker@example.com
  recipients: [me@example.com]
  events: [report, purchase]
```

The HTML report is attached when `reports.attach_html` is enabled. For Gmail use an
app password.

## Webhook

Posts JSON to any URL – ideal for Home Assistant, n8n, Node-RED or your own scripts.

```yaml
- type: webhook
  url: https://example.com/hook
  headers:
    Authorization: Bearer ${WEBHOOK_TOKEN}
```

Payload:

```json
{
  "event": "alert",
  "title": "Preisalarm: The One Ring (LTR)",
  "message": "Günstigstes passendes Angebot: 43,90 € …",
  "url": "https://www.cardmarket.com/en/Magic/Products/Singles/…"
}
```

??? example "Home Assistant automation"
    ```yaml
    automation:
      - alias: Cardmarket alert
        trigger:
          - platform: webhook
            webhook_id: cardmarket-tracker
            local_only: true
        action:
          - service: notify.mobile_app_my_phone
            data:
              title: "{{ trigger.json.title }}"
              message: "{{ trigger.json.message }}"
              data:
                url: "{{ trigger.json.url }}"
    ```
    Channel URL: `http://homeassistant.local:8123/api/webhook/cardmarket-tracker`

## Console

Writes messages to the log – the default when no channel is configured.

```yaml
- type: console
```
