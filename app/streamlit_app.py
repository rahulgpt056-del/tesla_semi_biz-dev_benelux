"""
Tesla Semi Benelux — Deployment Readiness & TCO Simulator
Public Streamlit app. All logic lives in engine/tco_engine.py (unit-tested).

Run locally:  streamlit run app/streamlit_app.py
"""
import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.tco_engine import (  # noqa: E402
    SemiInputs, calculate, inputs_from_assumptions, load_assumptions, ROUTE_FACTORS,
)

# --------------------------------------------------------------------------- #
# Page + theme
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Tesla Semi Benelux — Deployment & TCO Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAVY, RED, GREEN, AMBER, INK = "#0B2545", "#E31937", "#1B998B", "#E09F3E", "#13315C"

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1250px;}
      h1, h2, h3 {color: #0B2545; letter-spacing: -0.01em;}
      .hero {border-left: 6px solid #E31937; padding: 0.2rem 0 0.2rem 1rem; margin-bottom: 0.6rem;}
      .hero h1 {margin-bottom: 0.1rem; font-size: 2.0rem;}
      .hero p {color: #5B6670; margin-top: 0; font-size: 0.95rem;}
      div[data-testid="stMetric"] {background:#F6F9FC; border:1px solid #E1E9F0;
        border-radius:14px; padding:14px 16px;}
      div[data-testid="stMetricValue"] {color:#0B2545; font-weight:700;}
      .verdict {border-radius:14px; padding:16px 20px; color:#fff; font-weight:600; font-size:1.05rem;}
      .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem;
        font-weight:600; background:#EEF3F8; color:#13315C; margin-right:6px;}
      .src {color:#8A97A4; font-size:0.78rem;}
      footer {visibility:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

assumptions = load_assumptions()
last_updated = assumptions.get("_meta", {}).get("last_updated", "—")

st.markdown(
    '<div class="hero"><h1>Tesla Semi&nbsp;·&nbsp;Benelux Deployment &amp; TCO Simulator</h1>'
    '<p>Duty-cycle fit, depot energy &amp; charging, and a diesel-vs-Semi business case for any '
    'fleet — built on public 2026 assumptions.</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<span class="pill">Netherlands / Benelux</span>'
    f'<span class="pill">2026 assumptions</span>'
    f'<span class="pill">AanZET · vrachtwagenheffing</span>'
    f'<span class="src">&nbsp; Volatile prices last refreshed: {last_updated}</span>',
    unsafe_allow_html=True,
)
st.write("")


# --------------------------------------------------------------------------- #
# Sidebar — inputs
# --------------------------------------------------------------------------- #
seed = inputs_from_assumptions()  # latest public prices/policy as defaults

with st.sidebar:
    st.header("Fleet & duty cycle")
    fleet_size = st.number_input("Fleet size (trucks)", 1, 2000, int(seed.fleet_size), 1)
    daily_distance_km = st.slider("Daily distance per truck (km)", 50, 1000, int(seed.daily_distance_km), 10)
    operating_days = st.slider("Operating days / year", 200, 365, int(seed.operating_days_per_year), 5)
    payload_t = st.slider("Average payload (t)", 0, 40, int(seed.payload_t), 1)
    route_profile = st.selectbox("Route profile", list(ROUTE_FACTORS.keys()),
                                 index=list(ROUTE_FACTORS.keys()).index(seed.route_profile))
    return_to_depot_pct = st.slider("Charging done at depot (%)", 10, 100, int(seed.return_to_depot_pct), 5)
    dwell_time_h = st.slider("Depot dwell / charging window (h)", 1.0, 14.0, float(seed.dwell_time_h), 0.5)

    st.header("Energy & prices")
    semi_kwh = st.slider("Semi consumption (kWh/km, base)", 0.8, 1.6, float(seed.semi_kwh_per_km_base), 0.01)
    elec_price = st.slider("Electricity price (€/kWh)", 0.05, 0.45, float(seed.electricity_eur_per_kwh), 0.001)
    diesel_price = st.slider("Diesel price (€/L)", 1.0, 3.0, float(seed.diesel_eur_per_litre), 0.01)
    diesel_l100 = st.slider("Diesel use (L/100km)", 20.0, 45.0, float(seed.diesel_l_per_100km), 0.5)

    st.header("Charging & site")
    charger_power_kw = st.select_slider("Charger power (kW)", [150, 250, 350, 500, 750, 1000, 1200],
                                        value=350)
    depot_capacity_kw = st.slider("Depot grid capacity (kW)", 200, 5000, int(seed.depot_capacity_kw), 50)

    st.header("Capex & incentives")
    semi_capex = st.number_input("Semi acquisition cost (€/truck)", 100000, 400000, int(seed.semi_capex_eur), 5000)
    diesel_capex = st.number_input("Diesel equivalent (€/truck)", 80000, 250000, int(seed.diesel_capex_eur), 5000)
    aanzet = st.number_input("AanZET subsidy (€/truck)", 0, 100000, int(seed.aanzet_subsidy_eur_per_truck), 1000)
    toll = st.slider("Truck toll — vrachtwagenheffing (€/km)", 0.0, 0.40, float(seed.truck_toll_eur_per_km), 0.001)
    ze_pays_toll = st.checkbox("Zero-emission trucks also pay the toll", value=False)

    st.header("Analysis")
    years = st.slider("Horizon (years)", 1, 10, int(seed.analysis_years), 1)

inp = SemiInputs(
    fleet_size=int(fleet_size), daily_distance_km=float(daily_distance_km),
    operating_days_per_year=int(operating_days), payload_t=float(payload_t),
    route_profile=route_profile, return_to_depot_pct=float(return_to_depot_pct),
    dwell_time_h=float(dwell_time_h), semi_kwh_per_km_base=float(semi_kwh),
    electricity_eur_per_kwh=float(elec_price), diesel_eur_per_litre=float(diesel_price),
    diesel_l_per_100km=float(diesel_l100), charger_power_kw=float(charger_power_kw),
    depot_capacity_kw=float(depot_capacity_kw), semi_capex_eur=float(semi_capex),
    diesel_capex_eur=float(diesel_capex), aanzet_subsidy_eur_per_truck=float(aanzet),
    truck_toll_eur_per_km=float(toll), truck_toll_applies_to_zero_emission=bool(ze_pays_toll),
    analysis_years=int(years),
)

problems = inp.validate()
if problems:
    st.error("Please fix these inputs:\n\n- " + "\n- ".join(problems))
    st.stop()

r = calculate(inp)


# --------------------------------------------------------------------------- #
# Headline metrics + duty-cycle verdict
# --------------------------------------------------------------------------- #
fit_color = {"Fit": GREEN, "Conditional": AMBER, "No fit": RED}[r.duty_cycle_fit]
pb = "Immediate" if r.simple_payback_years == 0 else (
    f"{r.simple_payback_years:.1f} yrs" if r.simple_payback_years is not None else "No payback")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{years}-yr TCO saving (fleet)", f"€{r.tco_saving_eur:,.0f}",
          help="Diesel TCO minus Semi TCO across the whole fleet and horizon.")
c2.metric("Simple payback", pb, help="On the subsidy-adjusted incremental capex vs. diesel.")
c3.metric("Energy / day (fleet)", f"{r.fleet_daily_energy_kwh:,.0f} kWh")
c4.metric("Chargers needed", f"{r.chargers_needed}",
          help=f"At {int(charger_power_kw)} kW within a {dwell_time_h:.1f} h dwell window.")

st.markdown(
    f'<div class="verdict" style="background:{fit_color}">Duty-cycle fit: {r.duty_cycle_fit}'
    f'<div style="font-weight:400;font-size:0.9rem;margin-top:4px">{r.fit_limiting_factor}</div></div>',
    unsafe_allow_html=True,
)
st.write("")

tab1, tab2, tab3 = st.tabs(["📊 Economics & energy", "🔌 Site & charging", "🗂 Deployment plan"])

# --------------------------------------------------------------------------- #
# Tab 1 — economics & energy
# --------------------------------------------------------------------------- #
with tab1:
    left, right = st.columns([1.05, 1])
    with left:
        st.subheader("5-year TCO comparison")
        tco_df = pd.DataFrame({
            "Powertrain": ["Tesla Semi", "Diesel equivalent"],
            "TCO (€)": [r.semi_tco_eur, r.diesel_tco_eur],
        })
        chart = (
            alt.Chart(tco_df).mark_bar(cornerRadiusEnd=6, size=70)
            .encode(
                x=alt.X("Powertrain:N", axis=alt.Axis(labelAngle=0, title=None)),
                y=alt.Y("TCO (€):Q", axis=alt.Axis(format="~s")),
                color=alt.Color("Powertrain:N",
                                scale=alt.Scale(domain=["Tesla Semi", "Diesel equivalent"],
                                                range=[NAVY, "#9AA7B4"]), legend=None),
                tooltip=[alt.Tooltip("TCO (€):Q", format=",.0f")],
            ).properties(height=300)
        )
        st.altair_chart(chart, width="stretch")
        st.caption(f"Semi €{r.semi_cost_per_km:.3f}/km vs diesel €{r.diesel_cost_per_km:.3f}/km · "
                   f"annual opex saving €{r.annual_opex_saving_eur:,.0f}")

    with right:
        st.subheader("Energy & savings")
        st.markdown(f"""
        | Metric | Value |
        |---|---|
        | Effective consumption | **{r.effective_kwh_per_km:.2f} kWh/km** |
        | Energy per truck / day | **{r.daily_energy_per_truck_kwh:,.0f} kWh** |
        | Fleet energy / year | **{r.annual_energy_kwh/1e6:,.2f} GWh** |
        | Diesel litres displaced / yr | **{r.diesel_litres_displaced_per_year:,.0f} L** |
        | Net incremental capex | **€{r.net_incremental_capex_eur:,.0f}** |
        | Discounted payback | **{('%.1f yrs' % r.discounted_payback_years) if r.discounted_payback_years not in (None, 0.0) else ('Immediate' if r.discounted_payback_years == 0.0 else 'Beyond horizon')}** |
        """)
        st.caption("AanZET subsidy reduces Semi capex; the truck toll widens diesel's running-cost gap.")

# --------------------------------------------------------------------------- #
# Tab 2 — site & charging
# --------------------------------------------------------------------------- #
with tab2:
    st.subheader("Depot load profile (charging window)")
    prof_df = pd.DataFrame({
        "Hour of dwell window": [f"H{i+1}" for i in range(len(r.load_profile_kw))],
        "Load (kW)": r.load_profile_kw,
    })
    usable = inp.depot_capacity_kw * 0.90
    bars = (
        alt.Chart(prof_df).mark_bar(cornerRadiusEnd=4, color=NAVY)
        .encode(x=alt.X("Hour of dwell window:N", axis=alt.Axis(labelAngle=0, title=None)),
                y=alt.Y("Load (kW):Q"),
                tooltip=["Load (kW)"])
        .properties(height=300)
    )
    cap_rule = (
        alt.Chart(pd.DataFrame({"cap": [usable]})).mark_rule(color=RED, strokeDash=[6, 4], size=2)
        .encode(y="cap:Q")
    )
    st.altair_chart(bars + cap_rule, width="stretch")
    st.caption(f"Red line = usable depot capacity ({usable:,.0f} kW, 90% of {inp.depot_capacity_kw:,.0f} kW). "
               f"Peak charging load = {r.peak_charge_load_kw:,.0f} kW.")

    st.subheader("Utility-readiness checklist")
    checks = [
        (r.depot_capacity_ok, f"Grid capacity covers peak load ({r.peak_charge_load_kw:,.0f} kW ≤ {usable:,.0f} kW usable)"),
        (r.charge_time_per_truck_h <= inp.dwell_time_h,
         f"Charging fits the dwell window ({r.charge_time_per_truck_h:.1f} h ≤ {inp.dwell_time_h:.1f} h)"),
        (inp.daily_distance_km <= inp.semi_range_km, "Daily distance within single-charge range"),
        (r.chargers_needed <= inp.fleet_size, "Charger count is practical for the fleet footprint"),
    ]
    for ok, label in checks:
        st.markdown(("✅ " if ok else "⚠️ ") + label)
    st.info("Next step on any ⚠️: engage the depot's grid operator (Stedin / Liander) early — "
            "a connection upgrade is the longest-lead item in a Semi deployment.")

# --------------------------------------------------------------------------- #
# Tab 3 — deployment plan, risks, narrative
# --------------------------------------------------------------------------- #
with tab3:
    st.subheader("Phased deployment plan")
    st.markdown("""
    1. **Qualify (weeks 0–2)** — confirm duty-cycle fit and run this TCO with the fleet's real routes & prices.
    2. **Spec & fund (weeks 2–6)** — finalise vehicle + charging spec; lodge AanZET / MIA-VAMIL applications.
    3. **Site readiness (weeks 4–12)** — depot grid assessment with the operator; size and order chargers.
    4. **Contract & onboard (weeks 8–14)** — Sales Contract; delivery slots; driver & depot onboarding.
    5. **Commission & scale (weeks 12+)** — energise, commission, measure real kWh/km, expand the order.
    """)

    st.subheader("Implementation risk register")
    risk_df = pd.DataFrame([
        ["Grid connection lead time", "High" if not r.depot_capacity_ok else "Medium",
         "Engage grid operator at qualification; pursue interim lower-power charging."],
        ["Subsidy budget exhausted (AanZET round)", "Medium",
         "Track RVO round status; submit early; model a no-subsidy fallback case."],
        ["Toll / policy change", "Medium",
         "Parameterised here — re-run on any tariff change; feed Tesla policy team."],
        ["Duty-cycle edge cases (cold, detours)", "Medium" if r.duty_cycle_fit == "Conditional" else "Low",
         "Keep range margin; validate with a pilot truck before full rollout."],
    ], columns=["Risk", "Severity", "Mitigation"])
    st.dataframe(risk_df, width="stretch", hide_index=True)

    st.caption("This simulator uses public, illustrative assumptions and is a scoping tool, not a quote. "
               "Confirm figures against primary sources before contracting.")

st.divider()
st.caption("Built by Rahul · Tesla Semi Benelux BD portfolio · engine is unit-tested · "
           "prices auto-refresh weekly. Sources: Tesla/Electrek (Semi), GlobalPetrolPrices & Eurostat "
           "(energy), RVO/RAI (AanZET), Rijksoverheid (vrachtwagenheffing).")
