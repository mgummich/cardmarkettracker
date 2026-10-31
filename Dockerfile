FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CMTRACKER_CONFIG=/config/config.yaml

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && useradd --create-home --uid 1000 tracker \
    && mkdir -p /srv/data /config && chown -R tracker:tracker /srv /config

USER tracker
# Relative Pfade aus der config (data/tracker.db, data/reports) landen im Volume /srv/data
WORKDIR /srv
VOLUME ["/srv/data"]

ENTRYPOINT ["cmtracker"]
CMD ["run"]
