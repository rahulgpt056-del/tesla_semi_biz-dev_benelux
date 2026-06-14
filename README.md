# Tesla Semi · Benelux — BD Portfolio (TCO Calculator + Territory Map)

Two self-updating business-development tools for evaluating and prioritising
Tesla Semi fleet conversions in the Benelux market (NL primary). Built as part
of a portfolio supporting an application to Tesla's **Business Development
Manager, Semi — Benelux** role (Req. ID 267880).

**Live apps:**
- [TCO & Duty-Cycle Calculator](https://tco-and-duty-cycle-calculator.streamlit.app/)
- [Target-Account Territory Map](https://target-account-territory-map.streamlit.app/)

---

## Project 1 — TCO & Duty-Cycle Calculator

### What this is

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

### Running locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`).

### Running the tests

```bash
python tests/test_tco_engine.py
```

22 tests cover input validation, route/payload energy adjustments,
charging/energy scaling, duty-cycle fit logic, and TCO/payback economics
against a hand-checked reference case.

### Regenerating the Excel model

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

---

## Project 2 — Target-Account Territory Map

### What this is

A tiered (A/B/C) map of ~35 Benelux fleet operators — national parcel/grocery
networks, 3PLs, FMCG distributors, and bulk/port hauliers — scored on how well
their operations fit a Tesla Semi duty cycle: regional/depot-return share,
depot charging feasibility, fleet scale, and sustainability mandate.

| Component | Purpose |
|---|---|
| [`data/accounts.json`](data/accounts.json) | Seed dataset of target accounts and their fit signals |
| [`engine/account_scoring.py`](engine/account_scoring.py) | Scoring + tiering logic, unit tested |
| [`app/territory_app.py`](app/territory_app.py) | Interactive map + filterable account list + sequencing plan |
| [`scripts/enrich_accounts.py`](scripts/enrich_accounts.py) | Optional live enrichment via Apify (LinkedIn) or Apollo.io |

### Why it exists

A BD territory plan is only useful if it's prioritised. This tool turns public
signals about a fleet operator's network (depot-based vs. long-haul, existing
EV pilots, sustainability commitments) into a ranked outreach order — so the
first 10 conversations are the ones most likely to produce a "Fit" result in
the [TCO & Duty-Cycle Calculator](#project-1--tco--duty-cycle-calculator).

### Running locally

```bash
streamlit run app/territory_app.py
```

### Running the tests

```bash
python -m pytest tests/test_account_scoring.py -v
```

8 tests cover the tiering thresholds, scoring weights, sorting, and the
real seed dataset (35 accounts across NL/BE/LU).

### Enriching with live data (optional)

`scripts/enrich_accounts.py` is a no-op until you set `APIFY_TOKEN` or
`APOLLO_API_KEY`. With either set, it adds an `enrichment` block per account
(employee count, industry, LinkedIn/website URL) without overwriting the
hand-curated fit-scoring fields — use it to sanity-check or refine
`fleet_scale` and `sustainability_signal` before re-running the scoring.

```bash
APIFY_TOKEN=xxxx python scripts/enrich_accounts.py
# or
APOLLO_API_KEY=xxxx python scripts/enrich_accounts.py
```

---

## Project 3 — First 90 Days deck & site-readiness playbook

Two reference documents that tie P1 and P2 together into a BD plan (kept
locally under `docs/`, not pushed to the public repo — see "Personal vs.
public files" below):

- **`docs/Tesla-Semi-Benelux-First-90-Days.pptx`** — an 8-slide deck covering
  the Benelux opportunity and a phased 0-30 / 31-60 / 61-90 day plan that
  mirrors the deal lifecycle (qualify → spec → utility readiness → contract →
  onboarding → commissioning), generated by `docs/build_90day_deck.py`.
- **`docs/Tesla-Semi-Benelux-Site-Readiness-Playbook.docx`** — a six-stage
  checklist (qualify, spec, utility readiness, contract/incentives,
  onboarding, commissioning) plus a risk register covering DSO connection
  lead times, AanZET budget rounds, and toll-exemption rules, generated by
  `docs/build_site_readiness_playbook.py`.

Regenerate either with:

```bash
pip install -r docs/requirements.txt
python docs/build_90day_deck.py
python docs/build_site_readiness_playbook.py
```

### Personal vs. public files

`docs/` is excluded from this repo via `.gitignore`. It holds the job-
application strategy guide and the two documents above — useful as
interview leave-behinds, but not part of the public-facing project. The
generator scripts (`build_*.py`) are the only things worth keeping under
version control long-term if you want to reuse this approach for another
application; everything else in this README (P1 and P2) is the public
portfolio piece.

---

## Deploying

1. Push this repo to GitHub.
2. On [Streamlit Community Cloud](https://share.streamlit.io), create one app
   per entry point: `app/streamlit_app.py` (TCO calculator) and
   `app/territory_app.py` (territory map), both on the `main` branch.
3. Add the repo's GitHub Actions workflow — no extra secrets are required
   for the current (keep-last-good) refresh script.

## Project structure

```
tesla-semi-benelux/
├── app/
│   ├── streamlit_app.py          # P1: TCO & duty-cycle web app
│   └── territory_app.py          # P2: target-account territory map
├── engine/
│   ├── tco_engine.py             # P1 calculation core
│   └── account_scoring.py        # P2 scoring/tiering core
├── tests/
│   ├── test_tco_engine.py        # 22 unit tests
│   └── test_account_scoring.py   # 8 unit tests
├── model/                         # generated Excel model (P1)
├── scripts/
│   ├── build_excel_model.py      # regenerates the Excel model
│   ├── refresh_prices.py         # weekly price refresh (P1)
│   └── enrich_accounts.py        # optional live enrichment (P2)
├── data/
│   ├── assumptions.json          # P1 shared, refreshable inputs
│   └── accounts.json             # P2 target-account seed data
├── .github/workflows/refresh-prices.yml
└── requirements.txt
```
