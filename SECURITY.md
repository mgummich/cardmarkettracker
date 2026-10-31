# Security Policy

## Supported versions

Security fixes are made for the latest release and the `main` branch.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report it privately via
[GitHub Security Advisories](https://github.com/mgummich/cardmarkettracker/security/advisories/new)
("Report a vulnerability"). Include a description, the affected version and steps to reproduce.
You will get a response as soon as possible; please allow reasonable time for a fix before
public disclosure.

## Scope

Particularly relevant: authentication bypass or CSRF in the web interface, disclosure of
secrets (API tokens, passwords), unsafe file access, and anything that could trigger unwanted
purchases.

Hardening tips for operators are in the
[security documentation](https://mgummich.github.io/cardmarkettracker/operations/security/).
