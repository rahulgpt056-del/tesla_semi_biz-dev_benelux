# Tesla Semi · Benelux — TCO & Duty-Cycle Calculator

A self-updating business case tool for evaluating Tesla Semi fleet conversions
in the Benelux market (NL primary). Built as part of a portfolio supporting an
application to Tesla's **Business Development Manager, Semi — Benelux**
role (Req. ID 267880).

**Live app:** _add Streamlit Community Cloud URL here after deploying_

---

## What this is

A three-part model that turns a prospect's fleet profile (size, daily
distance, payload, route type, depot setup) into:

1. **Duty-cycle fit** — Fit / Conditional / No fit, based on range, charge
   time vs. dwell time, and depot grid capacity.
2. **Energy & charging plan** — daily/annual energy draw, chargers needed,
   peak load vs. depot capacity, hourly load profile.
3. **Total cost of ownership** — Semi vs. diesel over a configurable horizon,
   including AanZET subsidy, vrachtwagenheffing (Dutch truck toll), simple
   and discounted payback.

It exists in three forms that all share the same calculation logic:

| Component | Purpose |
|---|---|
| [`engine/tco_engine.py`](engine/tco_engine.py) | Pure-Python calculation core, unit tested |
| [`app/streamlit_app.py`](app/streamlit_app.py) | Interactive web app for live what-if conversations with prospects |
| [`model/Tesla-Semi-Benelux-TCO-Model.xlsx`](model/Tesla-Semi-Benelux-TCO-Model.xlsx) | Spreadsheet version with live formulas, for offline use / sharing with finance teams |

## Why it exists

Benelux fleet operators evaluating a switch to Tesla Semi need a fast,
defensible answer to three questions: *Does this route actually work on one
charge? What does it do to our depot's power bill and grid connection? And
does the economics case stand up over 5 years, with and without subsidy?*
This tool answers all three from a handful of inputs, using public
Dutch/Benelux pricing and policy data — so a BD conversation can move from
"interesting" to "here's your number" in the same meeting.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`).

## Running the tests

```bash
python tests/test_tco_engine.py
```

22 tests cover input validation, route/payload energy adjustments,
charging/energy scaling, duty-cycle fit logic, and TCO/payback economics
against a hand-checked reference case.

## Regenerating the Excel model

```bash
python scripts/build_excel_model.py
```

Writes `model/Tesla-Semi-Benelux-TCO-Model.xlsx`. The Inputs sheet has
55 named ranges; the Model sheet mirrors `engine/tco_engine.py` formula-for-
formula so the spreadsheet and the web app always agree.

## Assumptions & self-updating data

[`data/assumptions.json`](data/assumptions.json) holds the volatile public
inputs (electricity price, diesel price, AanZET subsidy, truck toll, Semi
specs). A weekly GitHub Actions job
([`.github/workflows/refresh-prices.yml`](.github/workflows/refresh-prices.yml))
runs [`scripts/refresh_prices.py`](scripts/refresh_prices.py) every Monday,
re-checks energy prices, runs the engine test suite as a guard, and commits
any change — which triggers Streamlit Community Cloud to auto-redeploy with
the latest numbers. If a fetch fails or returns an implausible value, the
script keeps the last known-good figure (never publishes a broken number).

Sources for current defaults are documented inline in
`data/assumptions.json` and on the Excel model's **Sources** sheet:
NL industrial electricity (Eurostat/Intratec), NL diesel pump price
(GlobalPetrolPrices), AanZET (RVO), vrachtwagenheffing tariff, and Tesla's
published Semi efficiency/range/Megacharger specs.

## Deploying

1. Push this repo to GitHub.
2. On [Streamlit Community Cloud](https://share.streamlit.io), create a new
   app pointing at `app/streamlit_app.py` on the `main` branch.
3. Add the repo's GitHub Actions workflow — no extra secrets are required
   for the current (keep-last-good) refresh script.

## Project structure

```
tesla-semi-benelux/
├── app/streamlit_app.py          # web app
├── engine/tco_engine.py          # calculation core
├── tests/test_tco_engine.py      # 22 unit tests
├── model/                         # generated Excel model
├── scripts/
│   ├── build_excel_model.py      # regenerates the Excel model
│   └── refresh_prices.py         # weekly price refresh
├── data/assumptions.json         # shared, refreshable inputs
├── .github/workflows/refresh-prices.yml
└── requirements.txt
```
