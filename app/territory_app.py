"""
Tesla Semi Benelux — Target-Account Territory Map
Public Streamlit app. Scoring logic lives in engine/account_scoring.py (unit-tested).

Run locally:  streamlit run app/territory_app.py
"""
import os
import sys

import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.account_scoring import load_accounts, score_accounts, tier_summary  # noqa: E402

# --------------------------------------------------------------------------- #
# Page + theme
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Tesla Semi Benelux — Target-Account Territory Map",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAVY, RED, GREEN, AMBER, INK = "#0B2545", "#E31937", "#1B998B", "#E09F3E", "#13315C"
TIER_COLORS = {"A": RED, "B": AMBER, "C": "#9AA7B4"}
TIER_RGB = {"A": [227, 25, 55], "B": [224, 159, 62], "C": [154, 167, 180]}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1300px;}
      h1, h2, h3 {color: #0B2545; letter-spacing: -0.01em;}
      .hero {border-left: 6px solid #E31937; padding: 0.2rem 0 0.2rem 1rem; margin-bottom: 0.6rem;}
      .hero h1 {margin-bottom: 0.1rem; font-size: 2.0rem;}
      .hero p {color: #5B6670; margin-top: 0; font-size: 0.95rem;}
      div[data-testid="stMetric"] {background:#F6F9FC; border:1px solid #E1E9F0;
        border-radius:14px; padding:14px 16px;}
      div[data-testid="stMetricValue"] {color:#0B2545; font-weight:700;}
      .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem;
        font-weight:600; background:#EEF3F8; color:#13315C; margin-right:6px;}
      .src {color:#8A97A4; font-size:0.78rem;}
      footer {visibility:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

accounts = load_accounts()
ranked = score_accounts(accounts)
last_updated = "2026-06-14"

st.markdown(
    '<div class="hero"><h1>Tesla Semi&nbsp;·&nbsp;Benelux Target-Account Territory Map</h1>'
    '<p>Tiered prospect list for Benelux fleet operators, scored on duty-cycle fit signals '
    '(regional share, depot charging feasibility, fleet scale, sustainability mandate).</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<span class="pill">Accounts: {len(ranked)}</span>'
    f'<span class="pill">Seed data as of {last_updated}</span>'
    f'<span class="src">Illustrative public-domain estimates — verify before outreach.</span>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Filters")
    countries = sorted({s.account.country for s in ranked})
    sectors = sorted({s.account.sector for s in ranked})

    sel_countries = st.multiselect("Country", countries, default=countries)
    sel_tiers = st.multiselect("Tier", ["A", "B", "C"], default=["A", "B", "C"])
    sel_sectors = st.multiselect("Sector", sectors, default=sectors)

    st.markdown("---")
    st.markdown(
        "**Tier legend**\n\n"
        f"- :red[**A**] — top priority, lead with this account first\n"
        f"- :orange[**B**] — strong secondary wave\n"
        f"- **C** — longer-term / phase 2 once references exist"
    )

filtered = [
    s for s in ranked
    if s.account.country in sel_countries
    and s.tier in sel_tiers
    and s.account.sector in sel_sectors
]

if not filtered:
    st.warning("No accounts match the current filters.")
    st.stop()

# --------------------------------------------------------------------------- #
# Headline metrics
# --------------------------------------------------------------------------- #
summary_all = tier_summary(ranked)
summary_filtered = tier_summary(filtered)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Accounts shown", len(filtered))
c2.metric("Tier A", summary_filtered["A"], help=f"of {summary_all['A']} total")
c3.metric("Tier B", summary_filtered["B"], help=f"of {summary_all['B']} total")
c4.metric("Tier C", summary_filtered["C"], help=f"of {summary_all['C']} total")

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_map, tab_table, tab_plan = st.tabs(["🗺️ Map", "📋 Account list", "🗂 Territory plan"])

with tab_map:
    df_map = pd.DataFrame([
        {
            "name": s.account.name,
            "lat": s.account.lat,
            "lon": s.account.lon,
            "tier": s.tier,
            "fit_score": s.fit_score,
            "sector": s.account.sector,
            "color": TIER_RGB[s.tier],
            "radius": 4000 + (s.fit_score * 60),
        }
        for s in filtered
    ])

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_map,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.7,
        stroked=True,
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )
    view_state = pdk.ViewState(latitude=51.4, longitude=4.8, zoom=6.4, pitch=0)
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{name}\nTier {tier} · fit {fit_score}\n{sector}"},
            map_style=None,
        ),
        width="stretch",
    )
    st.caption("Marker size scales with fit score. Red = Tier A, amber = Tier B, grey = Tier C.")

with tab_table:
    df_table = pd.DataFrame([
        {
            "Tier": s.tier,
            "Fit score": s.fit_score,
            "Account": s.account.name,
            "Country": s.account.country,
            "HQ": s.account.hq_city,
            "Sector": s.account.sector,
            "Fleet scale": s.account.fleet_scale,
            "Regional share": s.account.regional_share,
            "Depot charging": s.account.depot_charging_feasible,
            "Sustainability": s.account.sustainability_signal,
            "Notes": s.account.notes,
        }
        for s in filtered
    ])
    st.dataframe(df_table, width="stretch", hide_index=True, height=560)
    st.download_button(
        "Download as CSV",
        df_table.to_csv(index=False).encode("utf-8"),
        file_name="tesla_semi_benelux_target_accounts.csv",
        mime="text/csv",
    )

with tab_plan:
    st.subheader("Suggested sequencing")
    st.markdown(
        """
        **Wave 1 — Tier A accounts (weeks 1-4)**
        Lead with national parcel/grocery distribution networks already running
        regional, depot-return routes with a public sustainability mandate.
        These are the easiest "Fit" cases in the [TCO & Duty-Cycle Calculator](../streamlit_app.py)
        and the most credible reference customers.

        **Wave 2 — Tier B accounts (weeks 5-10)**
        3PLs and FMCG distributors with mixed regional/long-haul fleets. Use the
        TCO calculator to identify which *lanes* (not the whole fleet) are a
        "Fit" or "Conditional" case, and propose a single-route pilot.

        **Wave 3 — Tier C accounts (phase 2)**
        Longer-haul, bulk/tank, or smaller fleets. Revisit once Wave 1/2
        references and AanZET subsidy rounds make the economics easier, or once
        Megacharger corridor coverage extends beyond depot range.
        """
    )

    st.subheader("How this links to the other two tools")
    st.markdown(
        """
        - **TCO & Duty-Cycle Calculator** — for any account above, plug in their
          fleet size, daily distance, and depot setup to get a fit verdict and
          a 5-year savings number to open the conversation with.
        - **Account intelligence enrichment** (`scripts/enrich_accounts.py`) —
          once connected, pulls company size, fleet/sustainability signals, and
          named contacts via Apify/Apollo to refine the `fleet_scale` and
          `sustainability_signal` fields above with live data.
        """
    )
