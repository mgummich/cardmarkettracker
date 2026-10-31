# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] – 2026-10-31

### Added

- Web interface: dashboard with all cards (low, sparkline, 24 h / 7 d change, distance to
  target, status), card page with interactive price chart, activity and system pages.
- Configure cards, filters, alerts, schedule, data source, reports and auto-buy in the browser.
  `config.yaml` is edited round-trip (comments and `${ENV}` placeholders are preserved),
  validated before writing and backed up as `config.yaml.bak`.
- Background runner with immediate config reload, "check now" and report requests, graceful
  shutdown.
- JSON API (`/api/status`, `/api/cards`, `/api/cards/{key}/history`) with OpenAPI docs.
- Optional HTTP basic auth, CSRF protection via same-origin check, security headers.
- Starter configuration is created on first start.
- Bilingual documentation (English / German) with MkDocs, published on GitHub Pages.
- CI for lint, tests, package build, docs build and Docker; multi-arch images on GHCR;
  release workflow; Dependabot.
- `cmtracker web` command; `run` gained `--no-web`, `--host` and `--port`.

### Changed

- Docker image runs tracker and web UI on port 8080, uses a writable `/config` volume and
  has a health check.
- The package version is defined once in `src/cmtracker/__init__.py`.

## [0.1.0] – 2026-10-31

### Added

- Price tracking for Cardmarket cards with global and per-card filters (language, condition,
  foil / signed / altered / first edition, seller country and type, blocked sellers, minimum price).
- Data sources: Cardmarket API (OAuth 1.0a), HTML scraper fallback, demo mode.
- Alert rules: target price, price drop, percentage below trend / averages, all-time low,
  cooldown with re-alert on further drops.
- Notifications: Telegram, Discord, ntfy, e-mail, webhook, console.
- SQLite history, daily HTML report with charts, CSV export.
- Experimental auto-buy (dry run, add to cart) with quantity and budget limits.
- CLI, Docker image, docker-compose setup.

[Unreleased]: https://github.com/mgummich/cardmarkettracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mgummich/cardmarkettracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mgummich/cardmarkettracker/releases/tag/v0.1.0
