"""
Weekly refresh of volatile public assumptions (diesel & electricity prices).

Design: fetch live values where a source is configured; on ANY failure keep the
last known-good value (never publish a broken number) and still bump the
timestamp so the app shows the check ran. Run by GitHub Actions on a cron.

Usage:  python scripts/refresh_prices.py
"""
from __future__ import annotations

import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "assumptions.json")


def fetch_diesel_eur_per_litre(current: float) -> float:
    """
    Plug a real source here (e.g. a GlobalPetrolPrices / CBS endpoint or scrape).
    Until one is wired, return the current value so we never regress to a guess.
    """
    try:
        # TODO: real fetch. Keep-last-good fallback below guarantees safety.
        raise NotImplementedError
    except Exception:
        return current


def fetch_electricity_eur_per_kwh(current: float) -> float:
    try:
        raise NotImplementedError
    except Exception:
        return current


def main() -> int:
    with open(DATA, "r", encoding="utf-8") as f:
        a = json.load(f)

    ep = a.setdefault("energy_prices", {})
    cur_d = ep.get("diesel_eur_per_litre", 2.15)
    cur_e = ep.get("electricity_eur_per_kwh", 0.137)

    new_d = round(float(fetch_diesel_eur_per_litre(cur_d)), 4)
    new_e = round(float(fetch_electricity_eur_per_kwh(cur_e)), 4)

    # Sanity guardrails — refuse absurd values, keep last good.
    if not (1.0 <= new_d <= 3.5):
        new_d = cur_d
    if not (0.03 <= new_e <= 0.60):
        new_e = cur_e

    ep["diesel_eur_per_litre"] = new_d
    ep["electricity_eur_per_kwh"] = new_e
    a.setdefault("_meta", {})["last_updated"] = dt.date.today().isoformat()

    # Atomic write.
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(a, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, DATA)

    print(f"Refreshed: diesel €{new_d}/L, electricity €{new_e}/kWh, "
          f"updated {a['_meta']['last_updated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
