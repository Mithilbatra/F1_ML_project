"""FastF1 telemetry / timing access for the fan-facing features.

Loads race-weekend sessions and exposes the rich data FastF1 carries but the
rest of the app ignored: per-lap car telemetry (speed / throttle / brake /
gear), tyre stints, sector times and weather. Sessions are heavy to load, so
they are cached both on disk (FastF1) and in-process.
"""

from __future__ import annotations

import functools
import logging

import numpy as np
import pandas as pd

from .config import FASTF1_CACHE_DIR

log = logging.getLogger(__name__)

SESSION_CODES = {
    "FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3",
    "Q": "Qualifying", "SQ": "Sprint Qualifying", "S": "Sprint", "R": "Race",
}
COMPOUND_COLORS = {
    "SOFT": "#e10600", "MEDIUM": "#ffd12e", "HARD": "#f0f0f0",
    "INTERMEDIATE": "#43b02a", "WET": "#0067ad",
}


def _enable_cache() -> None:
    FASTF1_CACHE_DIR.mkdir(exist_ok=True)
    import fastf1

    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))


@functools.lru_cache(maxsize=16)
def load_session(year: int, gp: str, session: str, telemetry: bool = True):
    """Load and cache a session. `gp` is an event name or round number string."""
    import fastf1

    _enable_cache()
    key = int(gp) if str(gp).isdigit() else gp
    s = fastf1.get_session(year, key, session)
    s.load(telemetry=telemetry, laps=True, weather=True, messages=False)
    return s


def event_schedule(year: int) -> list[dict]:
    """Every round of a season with its date and location."""
    import fastf1

    _enable_cache()
    sched = fastf1.get_event_schedule(year, include_testing=False)
    out = []
    for _, ev in sched.iterrows():
        out.append({
            "round": int(ev["RoundNumber"]),
            "event": ev["EventName"],
            "country": ev["Country"],
            "location": ev["Location"],
            "date": str(ev["EventDate"].date()) if pd.notna(ev["EventDate"]) else None,
            "format": ev.get("EventFormat", "conventional"),
        })
    return out


def _color(hex_str: str) -> str:
    hex_str = str(hex_str or "").lstrip("#")
    return f"#{hex_str}" if len(hex_str) == 6 else "#888888"


def session_drivers(session) -> list[dict]:
    """Drivers in a session with team + colour, ordered by classification."""
    res = session.results
    out = []
    for _, r in res.iterrows():
        if pd.isna(r["Abbreviation"]):
            continue
        out.append({
            "abbr": r["Abbreviation"],
            "name": r["FullName"],
            "team": r["TeamName"],
            "color": _color(r["TeamColor"]),
            "position": None if pd.isna(r["Position"]) else int(r["Position"]),
        })
    return out


def _lap_seconds(td) -> float | None:
    return None if pd.isna(td) else round(td.total_seconds(), 3)


def _resample(distance, values, grid):
    return np.interp(grid, distance, values).tolist()


def fastest_lap_frame(session, driver: str):
    """The driver's fastest accurate lap and its distance-indexed telemetry."""
    laps = session.laps.pick_drivers(driver)
    lap = laps.pick_fastest()
    if lap is None or (isinstance(lap, pd.Series) and lap.empty):
        raise ValueError(f"No timed lap for {driver} in this session.")
    tel = lap.get_telemetry().add_distance()
    return lap, tel


def head_to_head(year: int, gp: str, session_code: str,
                 drv1: str, drv2: str, n: int = 400) -> dict:
    """Compare two drivers' fastest laps: traces, delta, track dominance."""
    import fastf1.utils as ff1u

    session = load_session(year, gp, session_code)
    drivers = {d["abbr"]: d for d in session_drivers(session)}

    lap1, tel1 = fastest_lap_frame(session, drv1)
    lap2, tel2 = fastest_lap_frame(session, drv2)

    total = float(min(tel1["Distance"].max(), tel2["Distance"].max()))
    grid = np.linspace(0, total, n)

    def traces(tel):
        d = tel["Distance"].to_numpy()
        return {
            "speed": _resample(d, tel["Speed"], grid),
            "throttle": _resample(d, tel["Throttle"], grid),
            "brake": _resample(d, tel["Brake"].astype(float) * 100, grid),
            "gear": _resample(d, tel["nGear"], grid),
        }

    # delta time (positive = drv2 slower than drv1) aligned to drv1's lap
    delta, ref, _ = ff1u.delta_time(lap1, lap2)
    dd = ref["Distance"].to_numpy()
    delta_grid = _resample(dd, np.asarray(delta, dtype=float), grid)

    # track dominance: drv1's racing line, coloured by who carries more speed
    x = _resample(tel1["Distance"].to_numpy(), tel1["X"], grid)
    y = _resample(tel1["Distance"].to_numpy(), tel1["Y"], grid)
    s1 = np.array(traces(tel1)["speed"])
    s2 = np.array(traces(tel2)["speed"])
    faster = np.where(s1 >= s2, 1, 2).tolist()

    def meta(lap, abbr):
        info = drivers.get(abbr, {"team": lap["Team"], "color": "#888", "name": abbr})
        return {
            "abbr": abbr, "name": info["name"], "team": info["team"],
            "color": info["color"], "lap_time": _lap_seconds(lap["LapTime"]),
            "compound": None if pd.isna(lap.get("Compound")) else lap["Compound"],
            "sectors": [_lap_seconds(lap[f"Sector{i}Time"]) for i in (1, 2, 3)],
            "top_speed": None if pd.isna(lap.get("SpeedST")) else float(lap["SpeedST"]),
        }

    return {
        "year": year, "session": SESSION_CODES.get(session_code, session_code),
        "event": session.event["EventName"],
        "distance": grid.tolist(),
        "d1": meta(lap1, drv1), "d2": meta(lap2, drv2),
        "traces": {"d1": traces(tel1), "d2": traces(tel2)},
        "delta": delta_grid,
        "track": {"x": x, "y": y, "faster": faster},
    }


def tyre_strategy(year: int, gp: str, session_code: str = "R") -> dict:
    """Per-driver tyre stints (compound + lap range) for a race."""
    session = load_session(year, gp, session_code, telemetry=False)
    laps = session.laps
    order = [d["abbr"] for d in session_drivers(session)]
    stints = (
        laps.groupby(["Driver", "Stint", "Compound"])
        .agg(start=("LapNumber", "min"), end=("LapNumber", "max"),
             laps=("LapNumber", "count"))
        .reset_index()
    )
    drivers = []
    for abbr in order:
        d = stints[stints["Driver"] == abbr].sort_values("start")
        if d.empty:
            continue
        drivers.append({
            "abbr": abbr,
            "stints": [{
                "compound": r["Compound"],
                "color": COMPOUND_COLORS.get(r["Compound"], "#888"),
                "start": int(r["start"]), "end": int(r["end"]), "laps": int(r["laps"]),
            } for _, r in d.iterrows()],
        })
    total_laps = int(laps["LapNumber"].max())
    return {"year": year, "event": session.event["EventName"],
            "total_laps": total_laps, "drivers": drivers}


def race_pace(year: int, gp: str, session_code: str = "R") -> dict:
    """Clean-lap race-pace distribution per driver (ignores in/out & safety laps)."""
    session = load_session(year, gp, session_code, telemetry=False)
    laps = session.laps.pick_wo_box()  # drop in/out laps
    laps = laps[laps["LapTime"].notna() & laps["IsAccurate"]]
    order = [d["abbr"] for d in session_drivers(session)]
    colors = {d["abbr"]: d["color"] for d in session_drivers(session)}

    rows = []
    for abbr in order:
        d = laps[laps["Driver"] == abbr]["LapTime"].dt.total_seconds()
        # trim slow outliers (traffic, SC) via 107% of the driver's own median
        if len(d) < 3:
            continue
        clean = d[d <= d.median() * 1.07]
        if clean.empty:
            continue
        rows.append({
            "abbr": abbr, "color": colors.get(abbr, "#888"),
            "median": round(float(clean.median()), 3),
            "best": round(float(clean.min()), 3),
            "laps": int(len(clean)),
            "q1": round(float(clean.quantile(0.25)), 3),
            "q3": round(float(clean.quantile(0.75)), 3),
        })
    rows.sort(key=lambda r: r["median"])
    if rows:
        leader = rows[0]["median"]
        for r in rows:
            r["gap"] = round(r["median"] - leader, 3)
    return {"year": year, "event": session.event["EventName"], "drivers": rows}
