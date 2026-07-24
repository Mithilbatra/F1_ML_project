"""Deeper analysis for the level-up features: circuit history, teammate
battles, driver profiles (from the local master data — fast, no network), plus
practice long-run pace and qualifying analysis (from FastF1 sessions).
"""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from .data import compute_standings, load_master
from .features import DRIVER_MAPPING, TEAM_MAPPING


@functools.lru_cache(maxsize=8)
def _headshots(year: int) -> dict:
    """Map driver full name -> headshot URL from a season's results (cached).

    Best-effort: loads one session, so the first call for a year is slow. Any
    failure just yields an empty map and the UI falls back to no photo.
    """
    try:
        from .telemetry import load_session

        master = load_master([year])
        rnd = int(master[master["RoundNumber"] > 0]["RoundNumber"].max())
        res = load_session(year, str(rnd), "R", telemetry=False).results
        out = {}
        for _, r in res.iterrows():
            name = DRIVER_MAPPING.get(r["FullName"], r["FullName"])
            url = r.get("HeadshotUrl")
            if isinstance(url, str) and url.startswith("http"):
                out[name] = url
        return out
    except Exception:
        return {}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df["EventName"].str.contains("Pre-Season", case=False, na=False)].copy()
    df["FullName"] = df["FullName"].replace(DRIVER_MAPPING)
    df["TeamName"] = df["TeamName"].replace(TEAM_MAPPING)
    return df


def circuit_history(event_name: str, years: list[int] | None = None) -> dict:
    """Past results at a circuit: winners, and each driver's record here."""
    master = _clean(load_master(years))
    # match on the distinctive part of the name (handles "Grand Prix" suffix)
    key = event_name.replace("Grand Prix", "").strip()
    df = master[master["EventName"].str.contains(key, case=False, na=False)]
    df = df[df["RacePos"].notna()]
    if df.empty:
        return {"event": event_name, "editions": [], "driver_record": []}

    editions = []
    for (year, _), race in df.groupby(["Year", "EventName"]):
        podium = race[race["RacePos"] <= 3].sort_values("RacePos")
        pole = race[race["QualyPos"] == 1]
        editions.append({
            "year": int(year),
            "winner": podium["FullName"].iloc[0] if len(podium) else None,
            "winner_team": podium["TeamName"].iloc[0] if len(podium) else None,
            "podium": podium["FullName"].tolist(),
            "pole": pole["FullName"].iloc[0] if len(pole) else None,
        })
    editions.sort(key=lambda e: e["year"], reverse=True)

    record = (df.groupby("FullName")
                .agg(starts=("RacePos", "count"),
                     wins=("RacePos", lambda s: int((s == 1).sum())),
                     podiums=("RacePos", lambda s: int((s <= 3).sum())),
                     best=("RacePos", "min"),
                     avg=("RacePos", "mean"))
                .reset_index()
                .sort_values(["wins", "podiums", "avg"], ascending=[False, False, True]))
    driver_record = [{
        "driver": r["FullName"], "starts": int(r["starts"]), "wins": int(r["wins"]),
        "podiums": int(r["podiums"]), "best": int(r["best"]), "avg": round(float(r["avg"]), 1),
    } for _, r in record.iterrows()]

    return {"event": event_name, "editions": editions, "driver_record": driver_record}


def teammate_battles(year: int) -> list[dict]:
    """Per-team qualifying and race head-to-head between teammates."""
    df = _clean(load_master([year]))
    df = df[df["RacePos"].notna()]
    out = []
    for team, tdf in df.groupby("TeamName"):
        drivers = tdf["FullName"].value_counts().head(2).index.tolist()
        if len(drivers) < 2:
            continue
        a, b = drivers
        qa = qb = ra = rb = 0
        for _, race in tdf.groupby(["Year", "RoundNumber"]):
            da = race[race["FullName"] == a]
            db = race[race["FullName"] == b]
            if da.empty or db.empty:
                continue
            qa_p, qb_p = da["QualyPos"].iloc[0], db["QualyPos"].iloc[0]
            if pd.notna(qa_p) and pd.notna(qb_p):
                qa += qa_p < qb_p; qb += qb_p < qa_p
            ra_p, rb_p = da["RacePos"].iloc[0], db["RacePos"].iloc[0]
            ra += ra_p < rb_p; rb += rb_p < ra_p
        out.append({
            "team": team, "a": a, "b": b,
            "quali": [int(qa), int(qb)], "race": [int(ra), int(rb)],
        })
    out.sort(key=lambda t: t["team"])
    return out


def driver_profile(year: int, driver: str) -> dict:
    """Season snapshot for one driver: stats, form, teammate H2H, best/worst."""
    master = _clean(load_master([year]))
    standings = compute_standings(master, year)
    row = standings["drivers"][standings["drivers"]["FullName"] == driver]
    if row.empty:
        raise ValueError(f"No {year} data for {driver}.")
    r = row.iloc[0]

    drace = master[(master["FullName"] == driver) & master["RacePos"].notna()]
    best = drace.loc[drace["RacePos"].idxmin()] if len(drace) else None
    finishes = drace["RacePos"].tolist()

    # teammate this season
    team = r["Team"]
    mates = [b for b in teammate_battles(year) if driver in (b["a"], b["b"]) and b["team"] == team]
    tm = None
    if mates:
        bt = mates[0]
        me_first = bt["a"] == driver
        other = bt["b"] if me_first else bt["a"]
        tm = {
            "name": other,
            "quali": [bt["quali"][0 if me_first else 1], bt["quali"][1 if me_first else 0]],
            "race": [bt["race"][0 if me_first else 1], bt["race"][1 if me_first else 0]],
        }

    return {
        "driver": driver, "team": team, "year": year,
        "headshot": _headshots(year).get(driver),
        "position": int(r["Pos"]), "points": float(r["Points"]),
        "wins": int(r["Wins"]), "podiums": int(r["Podiums"]), "races": int(r["Races"]),
        "best_finish": int(best["RacePos"]) if best is not None else None,
        "best_finish_event": best["EventName"] if best is not None else None,
        "avg_finish": round(float(np.mean(finishes)), 1) if finishes else None,
        "teammate": tm,
    }


# --------------------------------------------------------- session-based

def practice_pace(year: int, rnd: int) -> dict:
    """Representative long-run pace from the practice sessions.

    For each driver we take the median of their longer green-flag laps across
    all practice sessions (a rough race-pace proxy the teams themselves study).
    """
    from .telemetry import load_session, session_drivers

    frames = []
    used = []
    for sc in ("FP1", "FP2", "FP3"):
        try:
            s = load_session(year, str(rnd), sc, telemetry=False)
        except Exception:
            continue
        laps = s.laps.pick_wo_box()
        laps = laps[laps["LapTime"].notna() & laps["IsAccurate"]]
        if not laps.empty:
            frames.append(laps[["Driver", "LapTime"]])
            used.append(sc)
    if not frames:
        return {"error": "No usable practice data for this event yet."}

    laps = pd.concat(frames)
    laps["sec"] = laps["LapTime"].dt.total_seconds()
    colors = {}
    try:
        colors = {d["abbr"]: d["color"] for d in session_drivers(
            load_session(year, str(rnd), used[-1], telemetry=False))}
    except Exception:
        pass

    rows = []
    for drv, d in laps.groupby("Driver"):
        clean = d["sec"][d["sec"] <= d["sec"].median() * 1.04]  # long-run-ish
        if len(clean) < 3:
            continue
        rows.append({"abbr": drv, "color": colors.get(drv, "#888"),
                     "pace": round(float(clean.median()), 3), "laps": int(len(clean))})
    rows.sort(key=lambda r: r["pace"])
    if rows:
        lead = rows[0]["pace"]
        for r in rows:
            r["gap"] = round(r["pace"] - lead, 3)
    return {"year": year, "sessions": used, "drivers": rows}


def qualifying_analysis(year: int, rnd: int) -> dict:
    """Gap to pole and Q1/Q2/Q3 for a qualifying session."""
    from .telemetry import load_session, session_drivers

    s = load_session(year, str(rnd), "Q", telemetry=False)
    res = s.results
    colors = {d["abbr"]: d["color"] for d in session_drivers(s)}

    def secs(v):
        return None if pd.isna(v) else round(pd.Timedelta(v).total_seconds(), 3)

    rows = []
    for _, r in res.iterrows():
        if pd.isna(r["Abbreviation"]):
            continue
        q = [secs(r["Q1"]), secs(r["Q2"]), secs(r["Q3"])]
        best = min([t for t in q if t is not None], default=None)
        rows.append({
            "abbr": r["Abbreviation"], "color": colors.get(r["Abbreviation"], "#888"),
            "pos": None if pd.isna(r["Position"]) else int(r["Position"]),
            "q1": q[0], "q2": q[1], "q3": q[2], "best": best,
        })
    rows = [r for r in rows if r["best"] is not None]
    rows.sort(key=lambda r: r["pos"] if r["pos"] else 99)
    if rows:
        pole = rows[0]["best"]
        for r in rows:
            r["gap"] = round(r["best"] - pole, 3)
    return {"year": year, "event": s.event["EventName"], "drivers": rows}
