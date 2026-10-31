# Contributing

<!-- --8<-- [start:guide] -->
Thanks for your interest in Cardmarket Tracker! Bug reports, ideas, documentation fixes,
translations and code are all welcome. Issues and pull requests may be written in **English or
German**.

## Reporting bugs and requesting features

- Search the [existing issues](https://github.com/mgummich/cardmarkettracker/issues) first.
- Use the issue templates. For bugs, include the version (`cmtracker --version`), how you run
  it (Docker / pip), the data source and the relevant log lines. **Remove tokens and passwords.**
- Scraper problems: include the product URL that fails.
- Security issues: please follow the [security policy](https://github.com/mgummich/cardmarkettracker/blob/main/SECURITY.md)
  instead of opening an issue.

## Development setup

```bash
git clone https://github.com/mgummich/cardmarkettracker.git
cd cardmarkettracker
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,docs]'
pre-commit install          # optional: ruff on every commit
cp config.example.yaml config.yaml
cmtracker run               # demo data, web UI on http://127.0.0.1:8080
```

## Checks

Run the same checks as CI before opening a pull request:

```bash
ruff check . && ruff format --check .
pytest
mkdocs build --strict       # if you changed the docs
```

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep pull requests focused; one topic per PR.
3. Add or update tests for behaviour changes.
4. Update the documentation – **in both languages** (`docs/*.md` and `docs/*.de.md`).
   If you can only write one language, say so in the PR and we'll help with the other.
5. Add an entry under *Unreleased* in `CHANGELOG.md`.
6. Make sure CI is green.

## Code style

- Python ≥ 3.11, formatted and linted with ruff (line length 100).
- Type hints for public functions.
- User-facing texts (messages, web UI) are currently German; code, comments in new modules
  and commit messages may be English or German.
- No new runtime dependency without a good reason.

## Documentation

The docs are built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) and
[mkdocs-static-i18n](https://github.com/ultrabug/mkdocs-static-i18n). English pages are
`name.md`, German pages `name.de.md`. Preview locally:

```bash
mkdocs serve
```

## License

By contributing you agree that your contribution is licensed under the
[MIT License](https://github.com/mgummich/cardmarkettracker/blob/main/LICENSE).
<!-- --8<-- [end:guide] -->
