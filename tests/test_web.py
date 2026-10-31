from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from cmtracker.runtime import STARTER_CONFIG, Runner
from cmtracker.storage import Storage
from cmtracker.web.app import create_app
from cmtracker.web.config_store import ConfigStore

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    runner = Runner(cfg, schedule=False)
    runner.start()
    client = TestClient(create_app(cfg, runner), base_url="http://testserver")
    yield client, cfg, runner
    runner.stop()


def load(cfg_path):
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def test_pages_render(env):
    client, _, runner = env
    runner.request_check(None)
    assert runner.wait_idle()
    for url in [
        "/",
        "/cards/the-one-ring-ltr",
        "/cards/the-one-ring-ltr?range=all",
        "/cards/charizard-obf-223/edit",
        "/cards-new",
        "/settings",
        "/system",
        "/activity",
        "/api/status",
        "/api/cards",
        "/api/cards/sol-ring-foil/history?days=7",
    ]:
        r = client.get(url)
        assert r.status_code == 200, url
    cards = client.get("/api/cards").json()
    assert {c["key"] for c in cards} == {"the-one-ring-ltr", "charizard-obf-223", "sol-ring-foil"}
    # demo data may have 0 matching offers in a given hour -> check that every card was checked
    assert all(c["checked_at"] is not None and c["error"] is None for c in cards)
    assert client.get("/cards/unknown").status_code == 404


def test_create_edit_delete_card_keeps_comments(env):
    client, cfg_path, runner = env
    r = client.post(
        "/cards-new",
        data={
            "name": "Ragavan",
            "game": "Magic",
            "product_id": "555",
            "url": "",
            "enabled": ["0", "1"],
            "a_max_price": "39,50",
            "a_drop_percent": "aus",
            "a_reference": "inherit",
            "a_all_time_low": "inherit",
            "a_enabled": "inherit",
            "f_languages_mode": "custom",
            "f_languages": ["Japanese", "de"],
            "f_seller_countries_mode": "custom",
            "f_seller_countries": "Deutschland, at",
            "f_min_condition": "NM",
            "f_foil": "inherit",
            "f_seller_types_mode": "inherit",
            "b_enabled": "0",
            "b_max_price": "",
            "b_quantity": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"].startswith("/cards/ragavan")
    text = cfg_path.read_text(encoding="utf-8")
    assert (
        "# Notifications – any number of channels." in text
        and "${CMTRACKER_PROVIDER:-demo}" in text
    )
    # neue Karte steht vor dem Kommentarblock des nächsten Abschnitts
    assert text.index("name: Ragavan") < text.index("# Notifications – any number of channels.")
    card = load(cfg_path)["cards"][-1]
    assert card == {
        "name": "Ragavan",
        "game": "Magic",
        "product_id": 555,
        "filters": {
            "languages": ["Japanese", "German"],
            "seller_countries": ["DE", "AT"],
            "min_condition": "NM",
        },
        "alerts": {"max_price": 39.5, "drop_percent": None},
    }
    assert (cfg_path.parent / "config.yaml.bak").exists()

    # Bearbeiten: Name ändern -> Key bleibt stabil, Auto-Kauf aktivieren
    r = client.post(
        "/cards/ragavan/edit",
        data={
            "name": "Ragavan (MH2)",
            "enabled": ["0", "1"],
            "b_enabled": ["0", "1"],
            "b_max_price": "35",
            "b_quantity": "2",
            "f_languages_mode": "inherit",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    card = load(cfg_path)["cards"][-1]
    assert card["key"] == "ragavan" and card["name"] == "Ragavan (MH2)"
    assert card["buy"] == {"enabled": True, "max_price": 35, "quantity": 2}
    assert "languages" not in card["filters"]

    # Ungültige Eingabe -> Fehlermeldung, Datei unverändert
    before = cfg_path.read_text(encoding="utf-8")
    r = client.post("/cards/ragavan/edit", data={"name": "X", "a_max_price": "abc"})
    assert r.status_code == 200 and "is not a number" in r.text
    assert cfg_path.read_text(encoding="utf-8") == before

    # Pausieren / Löschen
    client.post("/cards/ragavan/toggle")
    assert load(cfg_path)["cards"][-1]["enabled"] is False
    r = client.post("/cards/ragavan/delete", data={"purge": "1"}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    assert "err=" not in r.headers["location"], r.headers["location"]
    text = cfg_path.read_text(encoding="utf-8")
    assert "Ragavan" not in text, text[text.find("Ragavan") - 400 : text.find("Ragavan") + 200]
    assert "# Notifications – any number of channels." in text
    assert text.index('name: "Sol Ring (Foil)"') < text.index(
        "# Notifications – any number of channels."
    )


def test_settings_and_validation(env):
    client, cfg_path, _ = env
    r = client.post(
        "/settings/general",
        data={"interval_minutes": "30", "notify_errors": ["0", "1"]},
        follow_redirects=False,
    )
    assert r.status_code == 303 and "msg=" in r.headers["location"]
    data = load(cfg_path)
    assert data["general"]["interval_minutes"] == 30 and data["general"]["notify_errors"] is True
    r = client.post("/settings/general", data={"timezone": "Mars/Olympus"})
    assert "unknown time zone" in r.text
    r = client.post(
        "/settings/defaults",
        data={
            "df_languages_mode": "any",
            "df_min_condition": "LP",
            "df_foil": "any",
            "da_drop_percent": "",
            "da_cooldown_hours": "6",
            "da_reference": "avg7",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    d = load(cfg_path)["defaults"]
    assert "languages" not in d["filters"] and d["filters"]["min_condition"] == "LP"
    assert "foil" not in d["filters"] and "drop_percent" not in d["alerts"]
    assert d["alerts"]["cooldown_hours"] == 6 and d["alerts"]["reference"] == "avg7"
    # Provider-Typ steht in der Beispieldatei als ${ENV} -> wird nicht überschrieben
    client.post("/settings/provider", data={"locale": "en"})
    assert "${CMTRACKER_PROVIDER:-demo}" in cfg_path.read_text(encoding="utf-8")


def test_check_now_and_report(env):
    client, _, runner = env
    client.post("/cards/sol-ring-foil/check")
    assert runner.wait_idle()
    assert runner.status.last_check_at is not None
    storage = Storage("data/tracker.db")
    assert storage.latest_snapshot("sol-ring-foil") is not None
    assert storage.latest_snapshot("the-one-ring-ltr") is None  # nur die eine Karte geprüft
    assert storage.card_status("sol-ring-foil")["error"] is None
    storage.close()
    client.post("/report", data={"send": "0"})
    assert runner.wait_idle()
    assert client.get("/reports/latest.html").status_code == 200
    assert client.get("/reports/..%2Fconfig.yaml").status_code == 404


def test_security(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEB_PW", "geheim")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(STARTER_CONFIG.replace("${WEB_PASSWORD:-}", "${WEB_PW}"), encoding="utf-8")
    client = TestClient(create_app(cfg, None))
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("admin", "falsch")).status_code == 401
    assert client.get("/", auth=("admin", "geheim")).status_code == 200
    r = client.post(
        "/settings/general",
        auth=("admin", "geheim"),
        headers={"Origin": "https://evil.example"},
        data={"interval_minutes": "5"},
    )
    assert r.status_code == 403


def test_empty_starter_config_add_first_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(STARTER_CONFIG, encoding="utf-8")
    client = TestClient(create_app(cfg, None))
    assert "No cards yet" in client.get("/").text
    client.post("/cards-new", data={"name": "Sol Ring"})
    text = cfg.read_text(encoding="utf-8")
    assert "  - name: Sol Ring" in text and "[" not in text.split("cards:")[1].split("\n")[0]
    assert ConfigStore(cfg).current()[0].cards[0].key == "sol-ring"


def test_runner_reloads_changed_file(env):
    _, cfg_path, runner = env
    runner.request_check(None)
    assert runner.wait_idle()
    first = runner.status.reloads
    text = cfg_path.read_text(encoding="utf-8").replace(
        "interval_minutes: 60", "interval_minutes: 15"
    )
    cfg_path.write_text(text, encoding="utf-8")
    import os
    import time

    os.utime(cfg_path, (time.time() + 5, time.time() + 5))
    runner.notify_config_changed()
    deadline = time.time() + 10
    while runner.status.reloads == first and time.time() < deadline:
        time.sleep(0.05)
    assert runner.status.reloads == first + 1

    # kaputte Datei -> Fehler wird gemeldet, alte Konfiguration läuft weiter
    cfg_path.write_text("general: [kaputt", encoding="utf-8")
    runner.notify_config_changed()
    deadline = time.time() + 10
    while not runner.status.config_error and time.time() < deadline:
        time.sleep(0.05)
    assert "YAML" in runner.status.config_error


def test_ui_language_selection(env):
    client, cfg_path, _runner = env
    # browser preference
    r = client.get("/", headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert '<html lang="de">' in r.text and "Karte hinzufügen" in r.text
    r = client.get("/", headers={"Accept-Language": "en-US"})
    assert '<html lang="en">' in r.text and "Add card" in r.text
    # explicit switch via cookie wins over the browser
    r = client.get("/lang/de?next=/settings", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/settings"
    r = client.get("/settings", headers={"Accept-Language": "en-US"})
    assert "Standardwerte für alle Karten" in r.text
    # error messages are translated as well
    r = client.post("/cards/the-one-ring-ltr/edit", data={"name": "X", "a_max_price": "abc"})
    assert "ist keine Zahl" in r.text
    r = client.get("/api/status")
    assert r.status_code == 200
    # open redirects are not possible
    r = client.get("/lang/en?next=https://evil.example", follow_redirects=False)
    assert r.headers["location"] == "/"
    r = client.get("/lang/en?next=//evil.example", follow_redirects=False)
    assert r.headers["location"] == "/"
    client.cookies.clear()


def test_language_setting_saved_from_ui(env):
    client, cfg_path, _runner = env
    r = client.post("/settings/general", data={"language": "de"}, follow_redirects=False)
    assert r.status_code == 303
    assert load(cfg_path)["general"]["language"] == "de"
    r = client.post("/settings/general", data={"language": "fr"})
    assert "general.language" in r.text
