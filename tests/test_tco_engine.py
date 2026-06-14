"""
Unit tests for the Tesla Semi Benelux TCO engine.

Run:  python -m pytest tests/ -q     (or: python tests/test_tco_engine.py)
Covers happy paths, edge cases, validation, and a hand-checked reference case.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.tco_engine import (  # noqa: E402
    SemiInputs, calculate, effective_consumption, inputs_from_assumptions,
    ROUTE_FACTORS,
)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_default_inputs_are_valid():
    assert SemiInputs().validate() == []


def test_zero_fleet_is_rejected():
    bad = SemiInputs(fleet_size=0)
    assert any("Fleet size" in m for m in bad.validate())
    try:
        calculate(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_negative_price_rejected():
    assert SemiInputs(electricity_eur_per_kwh=-1).validate()


def test_bad_route_profile_rejected():
    assert SemiInputs(route_profile="rocket").validate()  # type: ignore[arg-type]


def test_return_to_depot_bounds():
    assert SemiInputs(return_to_depot_pct=0).validate()
    assert SemiInputs(return_to_depot_pct=150).validate()
    assert SemiInputs(return_to_depot_pct=100).validate() == []


# --------------------------------------------------------------------------- #
# Consumption adjustment
# --------------------------------------------------------------------------- #
def test_route_profile_changes_consumption():
    base = SemiInputs(route_profile="regional", payload_t=19.0)
    urban = SemiInputs(route_profile="urban", payload_t=19.0)
    assert effective_consumption(urban) > effective_consumption(base)


def test_payload_above_reference_increases_consumption():
    light = SemiInputs(payload_t=19.0)
    heavy = SemiInputs(payload_t=30.0)
    assert effective_consumption(heavy) > effective_consumption(light)


def test_regional_reference_payload_equals_base():
    inp = SemiInputs(route_profile="regional", payload_t=19.0, semi_kwh_per_km_base=1.10)
    assert math.isclose(effective_consumption(inp), 1.10, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# Energy & charging
# --------------------------------------------------------------------------- #
def test_energy_scales_with_fleet():
    one = calculate(SemiInputs(fleet_size=1))
    ten = calculate(SemiInputs(fleet_size=10))
    # outputs are rounded to 1 dp, so allow for accumulated display rounding
    assert math.isclose(ten.fleet_daily_energy_kwh, one.fleet_daily_energy_kwh * 10, abs_tol=1.0)


def test_more_chargers_when_dwell_is_short():
    long_dwell = calculate(SemiInputs(dwell_time_h=10))
    short_dwell = calculate(SemiInputs(dwell_time_h=1.5))
    assert short_dwell.chargers_needed >= long_dwell.chargers_needed


def test_load_profile_length_matches_dwell():
    res = calculate(SemiInputs(dwell_time_h=9))
    assert len(res.load_profile_kw) == 9
    assert all(kw >= 0 for kw in res.load_profile_kw)


def test_grid_capacity_flagged_when_exceeded():
    res = calculate(SemiInputs(fleet_size=40, charger_power_kw=350, depot_capacity_kw=400, dwell_time_h=2))
    assert res.depot_capacity_ok is False


# --------------------------------------------------------------------------- #
# Duty-cycle fit
# --------------------------------------------------------------------------- #
def test_distance_beyond_range_is_no_fit():
    res = calculate(SemiInputs(daily_distance_km=900, semi_range_km=800))
    assert res.duty_cycle_fit == "No fit"


def test_comfortable_duty_cycle_is_fit():
    res = calculate(SemiInputs(daily_distance_km=300, semi_range_km=800, dwell_time_h=10,
                               charger_power_kw=350, fleet_size=5, depot_capacity_kw=2000))
    assert res.duty_cycle_fit == "Fit"


def test_short_dwell_makes_it_conditional():
    res = calculate(SemiInputs(daily_distance_km=400, dwell_time_h=0.5, charger_power_kw=150))
    assert res.duty_cycle_fit == "Conditional"


# --------------------------------------------------------------------------- #
# TCO & payback
# --------------------------------------------------------------------------- #
def test_diesel_more_expensive_in_base_case():
    res = calculate(SemiInputs())
    assert res.diesel_tco_eur > res.semi_tco_eur
    assert res.tco_saving_eur > 0


def test_toll_exemption_helps_semi():
    with_toll = calculate(SemiInputs(truck_toll_applies_to_zero_emission=True))
    without = calculate(SemiInputs(truck_toll_applies_to_zero_emission=False))
    assert without.semi_tco_eur < with_toll.semi_tco_eur


def test_bigger_subsidy_shortens_payback():
    small = calculate(SemiInputs(aanzet_subsidy_eur_per_truck=0))
    big = calculate(SemiInputs(aanzet_subsidy_eur_per_truck=60000))
    # both should pay back; bigger subsidy is never slower
    assert (big.simple_payback_years or 0) <= (small.simple_payback_years or 1e9)


def test_huge_subsidy_gives_immediate_payback():
    res = calculate(SemiInputs(semi_capex_eur=130000, aanzet_subsidy_eur_per_truck=60000,
                               diesel_capex_eur=130000))
    assert res.simple_payback_years == 0.0


def test_cost_per_km_positive():
    res = calculate(SemiInputs())
    assert res.semi_cost_per_km > 0 and res.diesel_cost_per_km > 0


# --------------------------------------------------------------------------- #
# Reference case (hand-checked anchors)
# --------------------------------------------------------------------------- #
def test_reference_case_anchors():
    """A 10-truck regional fleet, 350 km/day — sanity-anchored magnitudes."""
    res = calculate(SemiInputs(fleet_size=10, daily_distance_km=350, route_profile="regional",
                               payload_t=22, operating_days_per_year=300))
    # effective consumption: 1.10 * 1.0 * (1 + 3*0.006) = 1.10 * 1.018 = 1.1198
    assert math.isclose(res.effective_kwh_per_km, 1.12, abs_tol=0.005)
    # daily energy per truck ~ 350 * 1.12 = 392 kWh
    assert 380 <= res.daily_energy_per_truck_kwh <= 400
    # annual energy ~ 392 * 10 * 300 = ~1.176 GWh
    assert 1_100_000 <= res.annual_energy_kwh <= 1_250_000
    assert res.duty_cycle_fit in {"Fit", "Conditional"}


def test_assumptions_loader_runs():
    inp = inputs_from_assumptions()
    assert inp.validate() == []


if __name__ == "__main__":
    # Lightweight runner so tests work even without pytest installed.
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in funcs:
        try:
            fn()
            passed += 1
            print(f"PASS  {fn.__name__}")
        except AssertionError as ex:
            print(f"FAIL  {fn.__name__}: {ex}")
        except Exception as ex:  # noqa: BLE001
            print(f"ERROR {fn.__name__}: {type(ex).__name__}: {ex}")
    print(f"\n{passed}/{len(funcs)} tests passed")
    sys.exit(0 if passed == len(funcs) else 1)
