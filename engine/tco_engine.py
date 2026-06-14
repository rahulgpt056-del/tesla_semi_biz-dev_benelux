"""
Tesla Semi Benelux — TCO & Deployment calculation engine.

Pure, dependency-free logic shared by the Streamlit web app and the Excel model.
Every public figure is an input (see data/assumptions.json) so the model stays
auditable and refreshable. All inputs are validated at the boundary; the engine
never returns a silently-wrong number.

Author: Rahul — Tesla Semi Benelux BD portfolio (Req. ID 267880)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from typing import Literal

RouteProfile = Literal["urban", "regional", "longhaul"]

# Route profile multipliers on base kWh/km. Urban duty (stop-start, lower speed,
# more regen but more idling) vs steady long-haul (aero-dominated at speed).
ROUTE_FACTORS: dict[str, float] = {
    "urban": 1.15,
    "regional": 1.00,
    "longhaul": 1.08,
}

# Payload sensitivity: energy use rises modestly with payload above a reference.
# ~0.6% extra kWh/km per tonne above a 19 t reference, bounded to stay realistic.
PAYLOAD_REFERENCE_T = 19.0
PAYLOAD_SENSITIVITY_PER_T = 0.006

CHARGE_EFFICIENCY = 0.92          # AC->battery / charger losses
USABLE_DEPOT_CAPACITY = 0.90      # headroom on nameplate grid connection

DEFAULT_ASSUMPTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "assumptions.json"
)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass
class SemiInputs:
    # Fleet & duty cycle
    fleet_size: int = 10
    daily_distance_km: float = 350.0
    operating_days_per_year: int = 300
    payload_t: float = 22.0
    route_profile: RouteProfile = "regional"
    return_to_depot_pct: float = 100.0   # % of charging done at the depot
    dwell_time_h: float = 9.0            # available depot charging window

    # Energy & prices
    semi_kwh_per_km_base: float = 1.10
    electricity_eur_per_kwh: float = 0.137
    diesel_eur_per_litre: float = 2.15
    diesel_l_per_100km: float = 32.0

    # Charging & site
    charger_power_kw: float = 350.0
    depot_capacity_kw: float = 1400.0
    semi_range_km: float = 800.0

    # Capex / opex
    semi_capex_eur: float = 230000.0
    diesel_capex_eur: float = 130000.0
    semi_maint_eur_per_km: float = 0.12
    diesel_maint_eur_per_km: float = 0.19

    # Incentives & policy
    aanzet_subsidy_eur_per_truck: float = 38000.0
    truck_toll_eur_per_km: float = 0.167
    truck_toll_applies_to_zero_emission: bool = False

    # Analysis
    analysis_years: int = 5
    discount_rate: float = 0.07

    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        e: list[str] = []
        if self.fleet_size <= 0:
            e.append("Fleet size must be at least 1.")
        if self.daily_distance_km <= 0:
            e.append("Daily distance must be greater than 0 km.")
        if not (1 <= self.operating_days_per_year <= 366):
            e.append("Operating days per year must be between 1 and 366.")
        if self.payload_t < 0:
            e.append("Payload cannot be negative.")
        if self.route_profile not in ROUTE_FACTORS:
            e.append(f"Route profile must be one of {sorted(ROUTE_FACTORS)}.")
        if not (0 < self.return_to_depot_pct <= 100):
            e.append("Return-to-depot % must be between 1 and 100.")
        if self.dwell_time_h <= 0:
            e.append("Dwell time must be greater than 0 hours.")
        if self.semi_kwh_per_km_base <= 0:
            e.append("Semi energy consumption must be greater than 0 kWh/km.")
        if self.electricity_eur_per_kwh < 0 or self.diesel_eur_per_litre < 0:
            e.append("Energy prices cannot be negative.")
        if self.diesel_l_per_100km <= 0:
            e.append("Diesel consumption must be greater than 0 L/100km.")
        if self.charger_power_kw <= 0:
            e.append("Charger power must be greater than 0 kW.")
        if self.depot_capacity_kw <= 0:
            e.append("Depot capacity must be greater than 0 kW.")
        if self.semi_range_km <= 0:
            e.append("Semi range must be greater than 0 km.")
        if self.analysis_years <= 0:
            e.append("Analysis horizon must be at least 1 year.")
        if self.discount_rate < 0:
            e.append("Discount rate cannot be negative.")
        return e


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass
class TCOResults:
    # Energy / duty cycle
    effective_kwh_per_km: float
    daily_energy_per_truck_kwh: float
    fleet_daily_energy_kwh: float
    annual_energy_kwh: float
    diesel_litres_displaced_per_year: float

    # Charging / site
    charge_time_per_truck_h: float
    chargers_needed: int
    peak_charge_load_kw: float
    depot_capacity_ok: bool
    load_profile_kw: list[float]          # hourly kW across the dwell window

    # Duty-cycle fit
    duty_cycle_fit: str                   # "Fit" | "Conditional" | "No fit"
    fit_limiting_factor: str

    # TCO (whole fleet, over analysis horizon)
    semi_tco_eur: float
    diesel_tco_eur: float
    tco_saving_eur: float
    semi_cost_per_km: float
    diesel_cost_per_km: float

    # Payback
    annual_opex_saving_eur: float
    net_incremental_capex_eur: float
    simple_payback_years: float | None
    discounted_payback_years: float | None

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Core calculation
# --------------------------------------------------------------------------- #
def effective_consumption(inp: SemiInputs) -> float:
    """kWh/km adjusted for route profile and payload."""
    route = ROUTE_FACTORS[inp.route_profile]
    payload_adj = 1.0 + max(0.0, inp.payload_t - PAYLOAD_REFERENCE_T) * PAYLOAD_SENSITIVITY_PER_T
    return inp.semi_kwh_per_km_base * route * payload_adj


def _load_profile(dwell_h: float, fleet_daily_energy_kwh: float, peak_kw: float) -> list[float]:
    """
    Simple flat-within-window depot load profile across whole-hour buckets.
    Returns kW delivered in each hour of the dwell window (capped at peak_kw).
    """
    hours = max(1, math.ceil(dwell_h))
    if dwell_h <= 0:
        return [0.0]
    avg_kw = fleet_daily_energy_kwh / dwell_h
    profile = []
    remaining = dwell_h
    for _ in range(hours):
        frac = min(1.0, remaining)            # last bucket may be partial
        profile.append(round(min(avg_kw, peak_kw) * frac, 1))
        remaining -= 1.0
    return profile


def _payback(net_capex: float, annual_saving: float, years: int,
             rate: float) -> tuple[float | None, float | None]:
    """Simple and discounted payback in years; None if it never pays back."""
    if annual_saving <= 0:
        return None, None
    simple = net_capex / annual_saving
    # Discounted: accumulate discounted savings until they cover net capex.
    cum = 0.0
    disc = None
    for y in range(1, years * 3 + 1):                 # search beyond horizon
        cum += annual_saving / ((1 + rate) ** y)
        if cum >= net_capex:
            # linear interpolation within the year for a smooth figure
            prev = cum - annual_saving / ((1 + rate) ** y)
            disc = (y - 1) + (net_capex - prev) / (annual_saving / ((1 + rate) ** y))
            break
    return round(simple, 2), (round(disc, 2) if disc is not None else None)


def calculate(inp: SemiInputs) -> TCOResults:
    """Run the full model. Raises ValueError if inputs are invalid."""
    problems = inp.validate()
    if problems:
        raise ValueError("Invalid inputs: " + "; ".join(problems))

    # --- Energy & duty cycle ---
    eff = effective_consumption(inp)
    daily_per_truck = inp.daily_distance_km * eff
    depot_share = inp.return_to_depot_pct / 100.0
    fleet_daily = daily_per_truck * inp.fleet_size * depot_share
    annual_energy = fleet_daily * inp.operating_days_per_year
    annual_km_per_truck = inp.daily_distance_km * inp.operating_days_per_year
    diesel_litres_year = (annual_km_per_truck * inp.fleet_size) * (inp.diesel_l_per_100km / 100.0)

    # --- Charging / site ---
    energy_to_charge_per_truck = daily_per_truck * depot_share
    charge_time = energy_to_charge_per_truck / (inp.charger_power_kw * CHARGE_EFFICIENCY)
    # How many trucks one charger can service sequentially within the dwell window:
    trucks_per_charger = max(1.0, inp.dwell_time_h / charge_time) if charge_time > 0 else inp.fleet_size
    chargers_needed = max(1, math.ceil(inp.fleet_size / trucks_per_charger))
    peak_load = chargers_needed * inp.charger_power_kw
    usable_capacity = inp.depot_capacity_kw * USABLE_DEPOT_CAPACITY
    capacity_ok = peak_load <= usable_capacity
    profile = _load_profile(inp.dwell_time_h, fleet_daily, peak_load)

    # --- Duty-cycle fit ---
    fit, limit = _assess_fit(inp, charge_time, capacity_ok)

    # --- TCO (fleet, over horizon) ---
    yrs = inp.analysis_years
    annual_energy_cost = annual_energy * inp.electricity_eur_per_kwh
    annual_diesel_fuel = diesel_litres_year * inp.diesel_eur_per_litre
    fleet_annual_km = annual_km_per_truck * inp.fleet_size

    semi_toll = (inp.truck_toll_eur_per_km * fleet_annual_km) if inp.truck_toll_applies_to_zero_emission else 0.0
    diesel_toll = inp.truck_toll_eur_per_km * fleet_annual_km

    semi_capex_net = (inp.semi_capex_eur - inp.aanzet_subsidy_eur_per_truck) * inp.fleet_size
    diesel_capex = inp.diesel_capex_eur * inp.fleet_size

    semi_opex_year = annual_energy_cost + inp.semi_maint_eur_per_km * fleet_annual_km + semi_toll
    diesel_opex_year = annual_diesel_fuel + inp.diesel_maint_eur_per_km * fleet_annual_km + diesel_toll

    semi_tco = semi_capex_net + semi_opex_year * yrs
    diesel_tco = diesel_capex + diesel_opex_year * yrs
    saving = diesel_tco - semi_tco

    total_km = fleet_annual_km * yrs
    semi_cpk = semi_tco / total_km if total_km else 0.0
    diesel_cpk = diesel_tco / total_km if total_km else 0.0

    # --- Payback ---
    annual_opex_saving = diesel_opex_year - semi_opex_year
    net_incremental_capex = semi_capex_net - diesel_capex
    if net_incremental_capex <= 0:
        # Semi is cheaper up front (after subsidy) — pays back immediately.
        simple_pb, disc_pb = 0.0, 0.0
    else:
        simple_pb, disc_pb = _payback(net_incremental_capex, annual_opex_saving, yrs, inp.discount_rate)

    return TCOResults(
        effective_kwh_per_km=round(eff, 3),
        daily_energy_per_truck_kwh=round(daily_per_truck, 1),
        fleet_daily_energy_kwh=round(fleet_daily, 1),
        annual_energy_kwh=round(annual_energy, 0),
        diesel_litres_displaced_per_year=round(diesel_litres_year, 0),
        charge_time_per_truck_h=round(charge_time, 2),
        chargers_needed=chargers_needed,
        peak_charge_load_kw=round(peak_load, 1),
        depot_capacity_ok=capacity_ok,
        load_profile_kw=profile,
        duty_cycle_fit=fit,
        fit_limiting_factor=limit,
        semi_tco_eur=round(semi_tco, 0),
        diesel_tco_eur=round(diesel_tco, 0),
        tco_saving_eur=round(saving, 0),
        semi_cost_per_km=round(semi_cpk, 3),
        diesel_cost_per_km=round(diesel_cpk, 3),
        annual_opex_saving_eur=round(annual_opex_saving, 0),
        net_incremental_capex_eur=round(net_incremental_capex, 0),
        simple_payback_years=simple_pb,
        discounted_payback_years=disc_pb,
    )


def _assess_fit(inp: SemiInputs, charge_time: float, capacity_ok: bool) -> tuple[str, str]:
    """Verdict + the single binding constraint."""
    if inp.daily_distance_km > inp.semi_range_km:
        return "No fit", (
            f"Daily distance ({inp.daily_distance_km:.0f} km) exceeds single-charge "
            f"range ({inp.semi_range_km:.0f} km) with no mid-route charging modelled."
        )
    if charge_time > inp.dwell_time_h:
        return "Conditional", (
            f"Charging needs {charge_time:.1f} h but depot dwell window is "
            f"{inp.dwell_time_h:.1f} h — raise charger power or extend dwell."
        )
    if not capacity_ok:
        return "Conditional", (
            "Peak charging load exceeds usable depot grid capacity — a grid upgrade "
            "or load staggering is required."
        )
    if inp.daily_distance_km > 0.85 * inp.semi_range_km:
        return "Conditional", (
            "Daily distance is close to single-charge range — viable but with little "
            "margin for detours, cold weather, or payload peaks."
        )
    return "Fit", "Within range, charges inside the depot window, grid capacity sufficient."


# --------------------------------------------------------------------------- #
# Assumptions loading (volatile, refreshable)
# --------------------------------------------------------------------------- #
def load_assumptions(path: str = DEFAULT_ASSUMPTIONS_PATH) -> dict:
    """Load refreshable public assumptions; fall back to engine defaults on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def inputs_from_assumptions(base: SemiInputs | None = None,
                            path: str = DEFAULT_ASSUMPTIONS_PATH) -> SemiInputs:
    """Seed a SemiInputs with the latest refreshable public values."""
    inp = base or SemiInputs()
    a = load_assumptions(path)
    if not a:
        return inp
    ep = a.get("energy_prices", {})
    pol = a.get("policy", {})
    veh = a.get("vehicle", {})
    inp.electricity_eur_per_kwh = ep.get("electricity_eur_per_kwh", inp.electricity_eur_per_kwh)
    inp.diesel_eur_per_litre = ep.get("diesel_eur_per_litre", inp.diesel_eur_per_litre)
    inp.aanzet_subsidy_eur_per_truck = pol.get("aanzet_subsidy_eur_per_truck", inp.aanzet_subsidy_eur_per_truck)
    inp.truck_toll_eur_per_km = pol.get("truck_toll_eur_per_km", inp.truck_toll_eur_per_km)
    inp.truck_toll_applies_to_zero_emission = pol.get(
        "truck_toll_applies_to_zero_emission", inp.truck_toll_applies_to_zero_emission)
    inp.semi_kwh_per_km_base = veh.get("semi_kwh_per_km_base", inp.semi_kwh_per_km_base)
    inp.semi_range_km = veh.get("semi_range_km", inp.semi_range_km)
    inp.diesel_l_per_100km = veh.get("diesel_l_per_100km", inp.diesel_l_per_100km)
    return inp
