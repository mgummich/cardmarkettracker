# Releases & CI

Alle Automatisierungen liegen in `.github/workflows/`.

| Workflow | Auslöser | Was passiert |
|---|---|---|
| **CI** (`ci.yml`) | Push auf `main`, Pull Requests | ruff (Lint + Format), Tests mit Python 3.11–3.13, Paket bauen & `twine check`, `mkdocs build --strict`, Docker-Testbuild |
| **Docker** (`docker.yml`) | Push auf `main`, Tags `v*`, manuell | Multi-Arch-Image (`amd64`, `arm64`) → `ghcr.io/mgummich/cardmarkettracker`; bei PRs nur bauen |
| **Docs** (`docs.yml`) | Push auf `main` (Doku-Änderungen), manuell | baut diese Seite und veröffentlicht sie auf GitHub Pages |
| **Release** (`release.yml`) | Tags `v*` | prüft Tag = Paketversion, baut Wheel + sdist, erstellt ein GitHub-Release mit Notizen aus `CHANGELOG.md` |

Dependabot hält Python-Pakete, GitHub Actions und das Docker-Basisimage aktuell.

## Image-Tags

| Ereignis | Tags |
|---|---|
| Push auf `main` | `latest`, `main`, `sha-<kurz>` |
| Tag `v1.2.3` | `1.2.3`, `1.2`, `sha-<kurz>` |

Images enthalten OCI-Labels, eine SBOM und Build-Provenance.

## Release erstellen

1. `__version__` in `src/cmtracker/__init__.py` anpassen (einzige Stelle für die Version).
2. Einträge unter *Unreleased* in `CHANGELOG.md` in einen neuen Versionsabschnitt verschieben.
3. Committen, dann taggen und pushen:

    ```bash
    git tag -a v0.3.0 -m "v0.3.0"
    git push origin v0.3.0
    ```

4. Die Workflows Release und Docker veröffentlichen das GitHub-Release und das versionierte Image.

Alternativ das Release in der GitHub-Oberfläche anlegen (*Releases → Draft a new release*,
neuer Tag `v0.3.0` auf `main`). Der Release-Workflow hängt dann die Pakete an und übernimmt
die Notizen aus dem Changelog.

Versionierung nach [Semantic Versioning](https://semver.org); vor 1.0 können Minor-Versionen
inkompatible Änderungen enthalten (im Changelog dokumentiert).

## Einmalige Einrichtung des Repositorys

- **Pages:** *Settings → Pages → Build and deployment → Source: GitHub Actions*.
- **Packages:** nach dem ersten Image-Push das Paket auf GitHub öffnen
  (*Packages → cardmarkettracker → Package settings*) und die Sichtbarkeit auf **public** stellen.
- **Branch-Schutz (empfohlen):** die CI-Prüfungen für `main` verpflichtend machen.
