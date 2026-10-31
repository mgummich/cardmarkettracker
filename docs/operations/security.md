# Security

## Recommendations

- **Set `web.password`** (via `WEB_PASSWORD` in `.env`) whenever the UI can be reached from
  anything other than `localhost`. The tracker logs a warning when it listens on a public
  interface without a password.
- Expose it to the internet only behind a reverse proxy with **HTTPS** – basic auth sends the
  password with every request.
- Keep secrets in `.env` and reference them with `${VAR}`. Don't commit `.env` or `config.yaml`.
- Use `dry_run` and small budgets for auto-buy.

## Built-in protections

| Protection | Details |
|---|---|
| Authentication | optional HTTP basic auth for every page, API and asset (constant-time comparison) |
| CSRF | state-changing requests are only accepted if `Origin`/`Referer` match the `Host` |
| Secrets in the UI | API credentials, notification tokens and the `web` settings cannot be viewed or edited in the browser; notification targets are masked |
| Safe saving | input is validated before writing; `${ENV}` fields are read-only; previous config kept as `.bak` |
| Headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` |
| Container | runs as non-root user `1000` |
| Report files | only plain `*.html` file names from the report directory are served |

## Reporting a vulnerability

Please do **not** open a public issue. See
[SECURITY.md](https://github.com/mgummich/cardmarkettracker/blob/main/SECURITY.md).
