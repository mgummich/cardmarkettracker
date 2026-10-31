# Releases & CI

All automation lives in `.github/workflows/`.

| Workflow | Trigger | What it does |
|---|---|---|
| **CI** (`ci.yml`) | push to `main`, pull requests | ruff lint + format check, tests on Python 3.11–3.13, build & `twine check` the package, `mkdocs build --strict`, Docker test build |
| **Docker** (`docker.yml`) | push to `main`, tags `v*`, manual | multi-arch image (`amd64`, `arm64`) → `ghcr.io/mgummich/cardmarkettracker`; on PRs build only |
| **Docs** (`docs.yml`) | push to `main` (docs changes), manual | builds this site and deploys it to GitHub Pages |
| **Release** (`release.yml`) | tags `v*` | checks tag = package version, builds wheel + sdist, creates a GitHub release with notes from `CHANGELOG.md` |

Dependabot keeps Python packages, GitHub Actions and the Docker base image up to date.

## Image tags

| Event | Tags |
|---|---|
| push to `main` | `latest`, `main`, `sha-<short>` |
| tag `v1.2.3` | `1.2.3`, `1.2`, `sha-<short>` |

Images carry OCI labels, an SBOM and build provenance.

## Making a release

1. Update `__version__` in `src/cmtracker/__init__.py` (single source of truth).
2. Move the entries under *Unreleased* in `CHANGELOG.md` to a new version section.
3. Commit, then tag and push:

    ```bash
    git tag -a v0.3.0 -m "v0.3.0"
    git push origin v0.3.0
    ```

4. The Release and Docker workflows publish the GitHub release and the versioned image.

Versioning follows [Semantic Versioning](https://semver.org); before 1.0, minor versions may
contain breaking changes (documented in the changelog).

## One-time repository setup

- **Pages:** *Settings → Pages → Build and deployment → Source: GitHub Actions*.
- **Packages:** after the first image push, open the package on GitHub
  (*Packages → cardmarkettracker → Package settings*) and set the visibility to **public**.
- **Branch protection (recommended):** require the CI checks on `main`.
