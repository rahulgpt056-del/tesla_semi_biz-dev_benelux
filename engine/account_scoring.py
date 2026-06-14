"""
Tesla Semi Benelux — target-account fit scoring.

Combines four 0-3 signals from data/accounts.json into a single 0-100
fit score and an A/B/C outreach tier. Mirrors the duty-cycle logic in
tco_engine.py at a portfolio level: regional, depot-based fleets with a
sustainability mandate score highest.

Run:    python engine/account_scoring.py
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ACCOUNTS_PATH = os.path.join(ROOT, "data", "accounts.json")

# Weights sum to 1.0. Regional share is scaled from 0-1 to 0-3 before weighting.
WEIGHT_FLEET_SCALE = 0.25
WEIGHT_REGIONAL_SHARE = 0.30
WEIGHT_DEPOT_CHARGING = 0.25
WEIGHT_SUSTAINABILITY = 0.20

TIER_A_THRESHOLD = 75.0
TIER_B_THRESHOLD = 55.0

MAX_SIGNAL = 3.0


@dataclass(frozen=True)
class Account:
    name: str
    country: str
    hq_city: str
    lat: float
    lon: float
    sector: str
    fleet_scale: int
    regional_share: float
    depot_charging_feasible: int
    sustainability_signal: int
    notes: str = ""


@dataclass(frozen=True)
class ScoredAccount:
    account: Account
    fit_score: float
    tier: str


def load_accounts(path: str = DEFAULT_ACCOUNTS_PATH) -> list[Account]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Account(**row) for row in data["accounts"]]


def tier_for_score(score: float) -> str:
    if score >= TIER_A_THRESHOLD:
        return "A"
    if score >= TIER_B_THRESHOLD:
        return "B"
    return "C"


def score_account(account: Account) -> ScoredAccount:
    regional_signal = account.regional_share * MAX_SIGNAL
    raw = (
        account.fleet_scale * WEIGHT_FLEET_SCALE
        + regional_signal * WEIGHT_REGIONAL_SHARE
        + account.depot_charging_feasible * WEIGHT_DEPOT_CHARGING
        + account.sustainability_signal * WEIGHT_SUSTAINABILITY
    )
    fit_score = round((raw / MAX_SIGNAL) * 100, 1)
    return ScoredAccount(account=account, fit_score=fit_score, tier=tier_for_score(fit_score))


def score_accounts(accounts: list[Account]) -> list[ScoredAccount]:
    scored = [score_account(a) for a in accounts]
    return sorted(scored, key=lambda s: s.fit_score, reverse=True)


def tier_summary(scored: list[ScoredAccount]) -> dict[str, int]:
    summary = {"A": 0, "B": 0, "C": 0}
    for s in scored:
        summary[s.tier] += 1
    return summary


if __name__ == "__main__":
    ranked = score_accounts(load_accounts())
    for s in ranked:
        print(f"{s.tier}  {s.fit_score:5.1f}  {s.account.name} ({s.account.country})")
    print()
    print("Tier summary:", tier_summary(ranked))
