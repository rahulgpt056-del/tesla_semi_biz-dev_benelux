"""
Enrich data/accounts.json with live company/fleet/sustainability signals.

Design: this script is OFF by default. It only runs the enrichment calls if
the relevant API credentials are present in the environment, and it never
overwrites fields it cannot verify — it only adds an `enrichment` block per
account with whatever it found, plus a `checked_at` date. Scoring in
engine/account_scoring.py continues to use the hand-curated seed fields
unless you choose to merge enrichment results in by hand.

Configured sources (enable by setting the env var):
  - APIFY_TOKEN      -> uses the Apify API to run a LinkedIn company actor
                        (e.g. harvestapi/linkedin-company) per account name,
                        to confirm employee count / industry / HQ.
  - APOLLO_API_KEY   -> uses the Apollo.io API to fetch organization size,
                        industry tags, and key BD/operations contacts.

Usage:  python scripts/enrich_accounts.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "accounts.json")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")

APIFY_ACTOR = "harvestapi~linkedin-company"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"
APOLLO_ORG_SEARCH_URL = "https://api.apollo.io/v1/organizations/search"


def _post_json(url: str, payload: dict, headers: dict) -> list | dict | None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"  ! request to {url} failed: {exc}")
        return None


def enrich_via_apify(company_name: str) -> dict | None:
    if not APIFY_TOKEN:
        return None
    items = _post_json(
        f"{APIFY_RUN_URL}?token={APIFY_TOKEN}",
        {"companyNames": [company_name], "maxItems": 1},
        {},
    )
    if not items:
        return None
    item = items[0] if isinstance(items, list) else items
    return {
        "source": "apify:harvestapi/linkedin-company",
        "employee_count": item.get("employeeCount"),
        "industry": item.get("industry"),
        "linkedin_url": item.get("url"),
    }


def enrich_via_apollo(company_name: str) -> dict | None:
    if not APOLLO_API_KEY:
        return None
    result = _post_json(
        APOLLO_ORG_SEARCH_URL,
        {"q_organization_name": company_name, "page": 1, "per_page": 1},
        {"X-Api-Key": APOLLO_API_KEY},
    )
    if not result or not result.get("organizations"):
        return None
    org = result["organizations"][0]
    return {
        "source": "apollo.io",
        "employee_count": org.get("estimated_num_employees"),
        "industry": org.get("industry"),
        "website": org.get("website_url"),
    }


def main() -> int:
    if not APIFY_TOKEN and not APOLLO_API_KEY:
        print("No APIFY_TOKEN or APOLLO_API_KEY set — nothing to do.")
        print("Set one of these environment variables to enable enrichment.")
        return 0

    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    today = dt.date.today().isoformat()
    for account in data["accounts"]:
        name = account["name"]
        print(f"Enriching: {name}")
        enrichment = enrich_via_apify(name) or enrich_via_apollo(name)
        if enrichment:
            enrichment["checked_at"] = today
            account["enrichment"] = enrichment
        else:
            print(f"  - no enrichment data found for {name}")

    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, DATA)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
