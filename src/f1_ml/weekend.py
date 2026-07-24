"""Race-weekend companion: the next Grand Prix, its schedule, and a
form-based podium projection.

A real *pre-qualifying* forecast can't use grid or qualifying features (they
don't exist yet on a Friday), so this trains a **form-only** model — recent
finishing form, season stats and team pace — and applies it to each driver's
latest available form. It answers "who's in form going into the weekend",
which is what a fan actually wants before track action starts.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .config import RANDOM_STATE
from .features import feature_columns, load_features

# form signals only — everything knowable before the car turns a wheel
_FORM_DROP = {"QualyPos", "GridPosition", "QualyGapToPole"}


def _form_features(df: pd.DataFrame) -> list[str]:
    return [c for c in feature_columns(df) if c not in _FORM_DROP]


def next_race(now: datetime | None = None) -> dict | None:
    """The next Grand Prix at/after `now` (UTC), with its session schedule."""
    import fastf1

    from .telemetry import _enable_cache
    _enable_cache()
    now = now or datetime.now(timezone.utc)
    for year in (now.year, now.year + 1):
        try:
            sched = fastf1.get_event_schedule(year, include_testing=False)
        except Exception:
            continue
        for _, ev in sched.iterrows():
            race_utc = ev.get("Session5DateUtc")
            if pd.isna(race_utc):
                continue
            race_dt = pd.Timestamp(race_utc).tz_localize("UTC") \
                if pd.Timestamp(race_utc).tzinfo is None else pd.Timestamp(race_utc)
            if race_dt.to_pydatetime() < now:
                continue
            sessions = []
            for i in range(1, 6):
                name, dt = ev.get(f"Session{i}"), ev.get(f"Session{i}DateUtc")
                if pd.notna(name) and pd.notna(dt):
                    d = pd.Timestamp(dt)
                    d = d.tz_localize("UTC") if d.tzinfo is None else d
                    sessions.append({"name": name, "utc": d.isoformat()})
            return {
                "year": int(year),
                "round": int(ev["RoundNumber"]),
                "event": ev["EventName"],
                "country": ev["Country"],
                "location": ev["Location"],
                "format": ev.get("EventFormat", "conventional"),
                "race_utc": race_dt.isoformat(),
                "sessions": sessions,
            }
    return None


def form_forecast(top: int = 10) -> dict:
    """Podium probability for each driver from their latest form (no qualy)."""
    from sklearn.ensemble import RandomForestClassifier

    from .data import compute_standings, load_master

    df = load_features()
    feats = _form_features(df)
    model = RandomForestClassifier(
        n_estimators=400, min_samples_leaf=2, class_weight="balanced",
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(df[feats], df["IsPodium"])

    # each driver's most recent race row = their current form
    latest = (df.sort_values(["Year", "RoundNumber"])
                .groupby("FullName").tail(1))
    latest = latest[latest["Year"] == latest["Year"].max()]
    prob = model.predict_proba(latest[feats])[:, 1]
    latest = latest.assign(prob=prob).sort_values("prob", ascending=False)

    season = int(latest["Year"].max())
    standings = compute_standings(load_master([season]), season)
    team_of = dict(zip(standings["drivers"]["FullName"], standings["drivers"]["Team"]))

    rows = [{
        "driver": r["FullName"],
        "team": team_of.get(r["FullName"], ""),
        "prob": round(float(r["prob"]), 3),
        "form_points": round(float(r["driver_avg_points_last_3"]), 1),
        "avg_finish": round(float(r["driver_avg_finish_last_3"]), 1),
        "season_points": int(r["season_points"]),
    } for _, r in latest.head(top).iterrows()]

    return {"based_on_season": season, "n_drivers": int(len(latest)),
            "projection": rows}


def race_forecast(event_name: str | None = None, top: int = 10) -> dict:
    """Form projection, tilted toward each driver's record at *this* circuit.

    Generic form says who's fast right now; circuit history says who tends to
    go well *here*. We blend the two so the forecast is track-specific.
    """
    base = form_forecast(top=200)  # whole field, trimmed after blending
    proj = {r["driver"]: r for r in base["projection"]}

    circuit = None
    if event_name:
        from .analysis import circuit_history

        try:
            circuit = circuit_history(event_name)
        except Exception:
            circuit = None

    podium_rate = {}
    if circuit:
        for rec in circuit["driver_record"]:
            if rec["starts"]:
                podium_rate[rec["driver"]] = rec["podiums"] / rec["starts"]

    rows = []
    for name, r in proj.items():
        form_p = r["prob"]
        if name in podium_rate:
            blended = 0.7 * form_p + 0.3 * podium_rate[name]
        else:
            blended = form_p
        rows.append({**r, "form_prob": form_p,
                     "circuit_podium_rate": round(podium_rate.get(name, 0.0), 2),
                     "prob": round(blended, 3)})
    rows.sort(key=lambda r: r["prob"], reverse=True)

    return {
        "based_on_season": base["based_on_season"],
        "event": event_name,
        "has_circuit_history": bool(podium_rate),
        "projection": rows[:top],
    }


def circuit_guide(event_name: str, prefer_year: int | None = None) -> dict | None:
    """Racing line + lap time for a circuit, traced from a recent pole lap."""
    from .telemetry import fastest_lap_frame, load_session

    from . import racingline as rl

    # try the most recent completed season we have telemetry for
    for year in ([prefer_year] if prefer_year else []) + [2025, 2024]:
        if year is None:
            continue
        try:
            session = load_session(year, event_name, "Q")
            pole_abbr = session.results.iloc[0]["Abbreviation"]
            lap, tel = fastest_lap_frame(session, pole_abbr)
            # the pole lap's own distance is the track length
            length_km = float(tel["Distance"].max()) / 1000.0
            res = rl.analyze_from_xy(tel["X"].to_numpy(), tel["Y"].to_numpy(),
                                     track_length_km=length_km)
            res["source_year"] = year
            res["pole_driver"] = pole_abbr
            return res
        except Exception:
            continue
    return None
