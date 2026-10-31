from conftest import FakeProvider, market, offer

from cmtracker.app import App
from cmtracker.config import BuyRules
from cmtracker.purchasing import plan_purchases


def make_app(make_config, storage, hub, **cfg):
    provider = FakeProvider()
    app = App(make_config(**cfg), storage=storage, provider=provider, hub=hub)
    return app, provider


def test_alert_flow_with_cooldown(make_config, storage, hub, recorder):
    app, provider = make_app(
        make_config,
        storage,
        hub,
        cards=[{"name": "Test", "key": "test", "alerts": {"max_price": 10, "cooldown_hours": 12}}],
    )
    provider.push("test", market([12, 15]))
    provider.push("test", market([9.5, 15]))
    provider.push("test", market([9.5, 15]))
    provider.push("test", market([9.0, 15]))

    assert app.run_check()[0].alerts_sent == []
    assert [h.rule for h in app.run_check()[0].alerts_sent] == ["max_price"]
    assert app.run_check()[0].alerts_sent == []  # Cooldown
    assert [h.rule for h in app.run_check()[0].alerts_sent] == ["max_price"]  # weiter gefallen
    alerts = [n for n in recorder.sent if n.event == "alert"]
    assert len(alerts) == 2
    assert "9,50 €" in alerts[0].body
    assert len(storage.history("test")) == 4


def test_filters_applied_before_alerting(make_config, storage, hub):
    app, provider = make_app(
        make_config,
        storage,
        hub,
        cards=[
            {
                "name": "T",
                "key": "test",
                "filters": {"languages": ["de"]},
                "alerts": {"max_price": 10},
            }
        ],
    )
    provider.push("test", market([5], language="English"))
    result = app.run_check()[0]
    assert result.snapshot.offer_count == 0
    assert result.snapshot.total_offer_count == 1
    assert result.alerts_sent == []


def test_provider_error_does_not_stop_run(make_config, storage, hub, recorder):
    app, provider = make_app(
        make_config,
        storage,
        hub,
        general={"notify_errors": True},
        cards=[{"name": "A"}, {"name": "B", "alerts": {"max_price": 100}}],
    )
    provider.push("b", market([5]))
    results = app.run_check()
    assert results[0].error and not results[1].error
    assert {n.event for n in recorder.sent} == {"error", "alert"}


def test_dry_run_purchase_respects_quantity_and_budget(make_config, storage, hub, recorder):
    app, provider = make_app(
        make_config,
        storage,
        hub,
        purchasing={"enabled": True, "mode": "dry_run", "max_per_run": 25, "max_per_month": 100},
        cards=[
            {
                "name": "T",
                "key": "test",
                "buy": {
                    "enabled": True,
                    "max_price": 10,
                    "quantity": 3,
                    "filters": {"seller_countries": ["DE"]},
                },
            }
        ],
    )
    provider.push("test", market([8, 9, 11], quantity=1))
    provider.queue["test"][0].offers.insert(0, offer(1, article_id="fr", seller_country="FR"))
    r = app.run_check()[0]
    # FR-Angebot ausgeschlossen, 8 + 9 = 17 <= 25, 11 > max_price
    assert [(d.offer.price, d.quantity) for d, _ in r.purchases] == [(8, 1), (9, 1)]
    assert storage.bought_quantity("test", ("simulated",)) == 2
    # gleiche Artikel werden nicht erneut "gekauft"
    assert app.run_check()[0].purchases == []
    assert sum(1 for n in recorder.sent if n.event == "purchase") == 2


def test_planner_budget_limits():
    offers = [offer(10, quantity=5, article_id="x")]
    rules = BuyRules(enabled=True, max_price=10, quantity=5)
    d = plan_purchases("k", rules, offers, 0, set(), budget_left=35)
    assert d[0].quantity == 3 and d[0].total == 30
    assert plan_purchases("k", rules, offers, 5, set(), 100) == []
    assert plan_purchases("k", rules, offers, 0, {"x"}, 100) == []


def test_report_generation(make_config, storage, hub, recorder, tmp_path):
    app, provider = make_app(
        make_config,
        storage,
        hub,
        reports={"output_dir": str(tmp_path), "public_url": "https://t.example"},
        cards=[
            {"name": "<Lotus>", "key": "test", "alerts": {"max_price": 10}},
            {"name": "Empty", "key": "empty"},
        ],
    )
    provider.push("test", market([12, 13], trend=12.5))
    provider.push("test", market([9, 13], trend=12.0))
    app.run_check(["test"])
    app.run_check(["test"])
    path = app.run_report()
    html = path.read_text()
    assert "&lt;Lotus&gt;" in html and "<Lotus>" not in html
    assert "<svg" in html and "9,00 €" in html and "noch keine Daten" in html
    assert (tmp_path / "latest.html").exists()
    report_msg = [n for n in recorder.sent if n.event == "report"][0]
    assert "https://t.example/latest.html" in report_msg.body
    assert report_msg.attachments == [path]


def test_daily_report_due_once_per_day(make_config, storage, hub):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    app, _ = make_app(make_config, storage, hub, reports={"daily_time": "08:00"})
    tz = ZoneInfo("Europe/Berlin")
    assert not app._report_due(datetime(2026, 10, 31, 7, 59, tzinfo=tz))
    assert app._report_due(datetime(2026, 10, 31, 8, 0, tzinfo=tz))
    storage.set_meta("last_report_date", "2026-10-31")
    assert not app._report_due(datetime(2026, 10, 31, 22, 0, tzinfo=tz))
    assert app._report_due(datetime(2026, 11, 1, 8, 5, tzinfo=tz))
