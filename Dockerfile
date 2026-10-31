FROM python:3.12-slim

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
VOLUME ["/srv/data", "/config"]
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8080/api/status', timeout=4)" || exit 1

ENTRYPOINT ["cmtracker"]
# Tracker + Weboberfläche; im Container muss die Oberfläche auf allen Interfaces lauschen
CMD ["run", "--host", "0.0.0.0"]
