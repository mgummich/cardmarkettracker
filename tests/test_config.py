import pytest

from cmtracker.config import ConfigError, parse_config


def test_env_expansion(monkeypatch):
    monkeypatch.setenv("TG_TOKEN", "abc")
    cfg = parse_config(
        {
            "notifications": [
                {"type": "telegram", "bot_token": "${TG_TOKEN}", "chat_id": "${TG_CHAT:-123}"}
            ]
        }
    )
    assert cfg.notifications[0].bot_token == "abc"
    assert cfg.notifications[0].chat_id == "123"


def test_missing_env_raises(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    with pytest.raises(ConfigError, match="NOPE"):
        parse_config({"general": {"database": "${NOPE}"}})


def test_defaults_are_merged_with_card_overrides():
    cfg = parse_config(
        {
            "defaults": {
                "filters": {"languages": ["de", "en"], "min_condition": "EX", "foil": False},
                "alerts": {"drop_percent": 10, "cooldown_hours": 6},
            },
            "cards": [
                {"name": "A", "filters": {"languages": ["Deutsch"]}, "alerts": {"max_price": 5}},
                {"name": "B", "filters": {"languages": None}},
            ],
        }
    )
    a, b = cfg.cards
    fa = cfg.card_filters(a)
    assert fa.languages == ["German"]
    assert fa.min_condition == "EX"
    assert fa.foil is False
    ra = cfg.card_alerts(a)
    assert ra.max_price == 5 and ra.drop_percent == 10 and ra.cooldown_hours == 6
    assert cfg.card_filters(b).languages is None


def test_normalization():
    cfg = parse_config(
        {
            "cards": [
                {
                    "name": "X",
                    "filters": {
                        "min_condition": "near mint",
                        "seller_countries": ["Deutschland", "at", "D"],
                        "seller_types": ["gewerblich"],
                    },
                }
            ]
        }
    )
    f = cfg.card_filters(cfg.cards[0])
    assert f.min_condition == "NM"
    assert f.seller_countries == ["DE", "AT", "DE"]
    assert f.seller_types == ["professional"]


def test_invalid_condition_is_reported():
    with pytest.raises(ConfigError, match="min_condition"):
        parse_config({"cards": [{"name": "X", "filters": {"min_condition": "great"}}]})


def test_duplicate_keys_rejected():
    with pytest.raises(ConfigError, match="used twice"):
        parse_config({"cards": [{"name": "X"}, {"name": "x"}]})


def test_provider_requirements():
    with pytest.raises(ConfigError, match="url"):
        parse_config({"provider": {"type": "scraper"}, "cards": [{"name": "X"}]})
    with pytest.raises(ConfigError, match="mkm_api"):
        parse_config({"provider": {"type": "mkm_api"}})


def test_buy_requires_max_price():
    with pytest.raises(ConfigError, match="max_price"):
        parse_config({"cards": [{"name": "X", "buy": {"enabled": True}}]})


def test_cart_mode_requires_api():
    with pytest.raises(ConfigError, match="cart"):
        parse_config({"purchasing": {"enabled": True, "mode": "cart"}})


def test_example_config_is_valid(monkeypatch):
    from pathlib import Path

    from cmtracker.config import load_config

    cfg = load_config(Path(__file__).parent.parent / "config.example.yaml")
    assert cfg.provider.type == "demo"
    assert len(cfg.cards) == 3
