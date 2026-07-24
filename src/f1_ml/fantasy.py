"""F1 Fantasy optimiser.

Projects each driver's and constructor's fantasy points from recent form,
assigns plausible prices from championship standing, and picks the highest-
scoring legal team within the budget (5 drivers + 2 constructors, one captain
scoring double).

Prices are *approximated* from standings — the official game publishes real
prices each week, and dropping those in would make the picks exact. The
optimiser and projections are the real work.
"""

from __future__ import annotations

from itertools import combinations

import pandas as pd

from .data import compute_standings, load_master
from .features import load_features

N_DRIVERS = 5
N_CONSTRUCTORS = 2
DEFAULT_BUDGET = 100.0

# Approximate F1-Fantasy race points by finishing position (P1..P20). Real
# scoring adds quali, overtakes and beating-teammate bonuses; this captures the
# dominant signal — finish high, score big — and tapers to a small floor for
# backmarkers who still bank points for finishing.
_FANTASY_POS = [35, 28, 24, 20, 17, 14, 12, 10, 8, 6, 5, 4, 3, 3, 2, 2, 1, 1, 1, 1]


def _points_for_finish(avg_finish: float) -> float:
    p = min(max(int(round(avg_finish)), 1), 20)
    return float(_FANTASY_POS[p - 1])


def _price_from_rank(rank: int, n: int, hi: float, lo: float) -> float:
    """Linear price by championship rank (best = most expensive)."""
    frac = rank / max(n - 1, 1)
    return round(hi - (hi - lo) * frac, 1)


def _projections(season: int | None = None) -> dict:
    """Projected fantasy points + prices for drivers and constructors."""
    df = load_features()
    season = season or int(df["Year"].max())
    standings = compute_standings(load_master([season]), season)
    drv_stand = standings["drivers"].reset_index(drop=True)
    con_stand = standings["constructors"].reset_index(drop=True)

    latest = (df[df["Year"] == season].sort_values(["Year", "RoundNumber"])
                .groupby("FullName").tail(1))
    form = dict(zip(latest["FullName"], latest["driver_avg_points_last_3"]))

    avg_fin = dict(zip(latest["FullName"], latest["driver_avg_finish_last_3"]))
    drivers = []
    n = len(drv_stand)
    for i, r in drv_stand.iterrows():
        name = r["FullName"]
        # projection: expected fantasy points from recent finishing position,
        # nudged by recent points form for drivers on a hot streak
        base = _points_for_finish(avg_fin.get(name, i + 1))
        proj = max(1.0, base + 0.15 * form.get(name, 0.0))
        drivers.append({
            "name": name, "team": r["Team"],
            "price": _price_from_rank(i, n, 30.0, 4.5),
            "proj": round(proj, 1),
        })

    constructors = []
    m = len(con_stand)
    for i, r in con_stand.iterrows():
        team = r["TeamName"]
        team_drivers = [d for d in drivers if d["team"] == team]
        proj = sum(d["proj"] for d in team_drivers) or 2.0
        constructors.append({
            "name": team,
            "price": _price_from_rank(i, m, 28.0, 6.0),
            "proj": round(proj, 1),
        })
    return {"season": season, "drivers": drivers, "constructors": constructors}


def optimise(budget: float = DEFAULT_BUDGET, season: int | None = None) -> dict:
    """Best legal fantasy team within budget. Captain doubles a driver's points."""
    proj = _projections(season)
    drivers, constructors = proj["drivers"], proj["constructors"]

    # cheapest constructor pairs first, so we can early-out by budget
    con_pairs = []
    for a, b in combinations(range(len(constructors)), 2):
        ca, cb = constructors[a], constructors[b]
        con_pairs.append((ca["price"] + cb["price"], ca["proj"] + cb["proj"], (a, b)))
    con_pairs.sort()

    best = None
    for combo in combinations(range(len(drivers)), N_DRIVERS):
        picks = [drivers[i] for i in combo]
        d_cost = sum(d["price"] for d in picks)
        if d_cost > budget:
            continue
        d_pts = sum(d["proj"] for d in picks)
        captain = max(picks, key=lambda d: d["proj"])
        d_pts += captain["proj"]  # captain scores double
        remaining = budget - d_cost
        for c_cost, c_pts, (a, b) in con_pairs:
            if c_cost > remaining:
                break  # sorted: no cheaper pair beyond here
            total = d_pts + c_pts
            if best is None or total > best["total"]:
                best = {
                    "total": total, "cost": round(d_cost + c_cost, 1),
                    "drivers": combo, "captain": captain["name"],
                    "constructors": (a, b),
                }

    if best is None:
        return {"error": f"No legal team fits a ${budget}M budget."}

    team_drivers = [{
        **drivers[i],
        "captain": drivers[i]["name"] == best["captain"],
    } for i in best["drivers"]]
    team_drivers.sort(key=lambda d: d["proj"], reverse=True)
    team_cons = [constructors[i] for i in best["constructors"]]

    return {
        "season": proj["season"],
        "budget": budget,
        "cost": best["cost"],
        "projected_points": round(best["total"], 1),
        "captain": best["captain"],
        "drivers": team_drivers,
        "constructors": team_cons,
        "all_drivers": sorted(drivers, key=lambda d: d["proj"], reverse=True),
        "all_constructors": sorted(constructors, key=lambda c: c["proj"], reverse=True),
    }
