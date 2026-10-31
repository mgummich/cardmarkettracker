from datetime import timedelta

from conftest import T0, market

from cmtracker.alerts import evaluate_rules, should_send
from cmtracker.config import AlertRules
from cmtracker.filters import build_snapshot
from cmtracker.storage import AlertRecord


def snap(prices, trend=None):
    m = market(prices, trend=trend)
    return build_snapshot("k", m, sorted(m.offers, key=lambda o: o.price), T0, 10)


def rules_of(hits):
    return {h.rule for h in hits}


def test_max_price():
    r = AlertRules(max_price=10)
    assert rules_of(evaluate_rules(r, snap([10, 12]), None, None)) == {"max_price"}
    assert evaluate_rules(r, snap([10.01]), None, None) == []


def test_drop_percent_against_previous():
    r = AlertRules(drop_percent=10)
    assert evaluate_rules(r, snap([9.5]), snap([10]), None) == []
    assert rules_of(evaluate_rules(r, snap([9]), snap([10]), None)) == {"drop_percent"}
    assert evaluate_rules(r, snap([5]), None, None) == []


def test_below_reference():
    r = AlertRules(below_reference_percent=20, reference="trend")
    assert rules_of(evaluate_rules(r, snap([8], trend=10), None, None)) == {"below_reference"}
    assert evaluate_rules(r, snap([8.5], trend=10), None, None) == []
    assert evaluate_rules(r, snap([1], trend=None), None, None) == []


def test_all_time_low_and_disabled():
    r = AlertRules(all_time_low=True)
    assert rules_of(evaluate_rules(r, snap([4]), None, 5)) == {"all_time_low"}
    assert evaluate_rules(r, snap([5]), None, 5) == []
    assert evaluate_rules(r, snap([4]), None, None) == []  # erste Messung ist kein Tief
    assert evaluate_rules(AlertRules(enabled=False, max_price=100), snap([1]), None, None) == []
    assert evaluate_rules(AlertRules(max_price=100), snap([]), None, None) == []


def test_cooldown():
    hit = evaluate_rules(AlertRules(max_price=10), snap([8]), None, None)[0]
    last = AlertRecord("k", "max_price", 8, "", T0)
    assert should_send(hit, None, 12, T0)
    assert not should_send(hit, last, 12, T0 + timedelta(hours=1))
    assert should_send(hit, last, 12, T0 + timedelta(hours=12))
    cheaper = evaluate_rules(AlertRules(max_price=10), snap([7]), None, None)[0]
    assert should_send(cheaper, last, 12, T0 + timedelta(hours=1))
