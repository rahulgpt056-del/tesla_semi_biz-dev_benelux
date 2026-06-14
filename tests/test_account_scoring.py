"""Unit tests for engine/account_scoring.py. Run with pytest or directly."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.account_scoring import (
    Account,
    load_accounts,
    score_account,
    score_accounts,
    tier_for_score,
    tier_summary,
)


def _account(**overrides) -> Account:
    base = dict(
        name="Test Co",
        country="NL",
        hq_city="Utrecht",
        lat=52.0907,
        lon=5.1214,
        sector="Test",
        fleet_scale=1,
        regional_share=0.5,
        depot_charging_feasible=1,
        sustainability_signal=1,
    )
    base.update(overrides)
    return Account(**base)


def test_tier_thresholds():
    assert tier_for_score(75.0) == "A"
    assert tier_for_score(74.9) == "B"
    assert tier_for_score(55.0) == "B"
    assert tier_for_score(54.9) == "C"


def test_best_possible_account_scores_100_and_tier_a():
    best = _account(fleet_scale=3, regional_share=1.0, depot_charging_feasible=3, sustainability_signal=3)
    scored = score_account(best)
    assert scored.fit_score == 100.0
    assert scored.tier == "A"


def test_worst_possible_account_scores_0_and_tier_c():
    worst = _account(fleet_scale=0, regional_share=0.0, depot_charging_feasible=0, sustainability_signal=0)
    scored = score_account(worst)
    assert scored.fit_score == 0.0
    assert scored.tier == "C"


def test_regional_share_has_largest_single_weight():
    base = _account()
    higher_regional = _account(regional_share=1.0)
    base_score = score_account(base).fit_score
    higher_score = score_account(higher_regional).fit_score
    # regional share moves from 0.5 -> 1.0, i.e. +1.5 raw points * 0.30 weight / 3 * 100
    assert higher_score - base_score > 0
    assert round(higher_score - base_score, 1) == 15.0


def test_score_accounts_sorted_descending():
    accounts = [
        _account(name="Low", fleet_scale=0, regional_share=0.0, depot_charging_feasible=0, sustainability_signal=0),
        _account(name="High", fleet_scale=3, regional_share=1.0, depot_charging_feasible=3, sustainability_signal=3),
        _account(name="Mid", fleet_scale=1, regional_share=0.5, depot_charging_feasible=1, sustainability_signal=1),
    ]
    ranked = score_accounts(accounts)
    assert [s.account.name for s in ranked] == ["High", "Mid", "Low"]


def test_tier_summary_counts_all_accounts():
    accounts = [
        _account(name="A1", fleet_scale=3, regional_share=1.0, depot_charging_feasible=3, sustainability_signal=3),
        _account(name="B1", fleet_scale=2, regional_share=0.6, depot_charging_feasible=2, sustainability_signal=2),
        _account(name="C1", fleet_scale=0, regional_share=0.0, depot_charging_feasible=0, sustainability_signal=0),
    ]
    summary = tier_summary(score_accounts(accounts))
    assert sum(summary.values()) == len(accounts)
    assert summary["A"] >= 1
    assert summary["C"] >= 1


def test_load_accounts_from_real_data_file():
    accounts = load_accounts()
    assert len(accounts) >= 30
    names = {a.name for a in accounts}
    assert "PostNL" in names
    assert "Colruyt Group" in names
    for a in accounts:
        assert a.country in {"NL", "BE", "LU"}
        assert 0 <= a.regional_share <= 1
        assert 0 <= a.fleet_scale <= 3
        assert 0 <= a.depot_charging_feasible <= 3
        assert 0 <= a.sustainability_signal <= 3


def test_real_data_scores_are_within_bounds():
    ranked = score_accounts(load_accounts())
    for s in ranked:
        assert 0.0 <= s.fit_score <= 100.0
        assert s.tier in {"A", "B", "C"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
