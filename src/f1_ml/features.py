"""Feature engineering.

Every historical feature is shifted by one race within its group (driver,
team or driver-season) so a row only ever sees information available
*before* lights out. Fixes over the old notebook pipeline:

- rolling driver averages are computed per driver (the old code rolled
  across a round-sorted frame, mixing neighbouring drivers' results)
- QualyPos / GridPosition are kept as features — both are known pre-race
- rows without a race classification (DNS, races not yet run) are dropped
  instead of being filled in as fake P20 finishes
- street-circuit detection matches actual event names (the old list used
  'Jeddah'/'Baku'/'Albert Park', which never appear in EventName)
- adds qualifying gap-to-pole and rolling team form features
"""

from __future__ import annotations

import pandas as pd

from .config import FEATURES_FILE
from .data import load_master

# FastF1 renamed some drivers mid-season; without this, one driver becomes
# two and his rolling history resets in the middle of the year.
DRIVER_MAPPING = {
    "Andrea Kimi Antonelli": "Kimi Antonelli",
}

# Normalise team identities across the 2024/2025 seasons.
TEAM_MAPPING = {
    "RB": "Racing Bulls",
    "AlphaTauri": "Racing Bulls",
    "Visa Cash App RB": "Racing Bulls",
    "Alfa Romeo": "Kick Sauber",
    "Sauber": "Kick Sauber",
    "Stake F1 Team Kick Sauber": "Kick Sauber",
}

# Street / temporary circuits by the event name FastF1 actually reports.
STREET_EVENTS = (
    "Monaco", "Singapore", "Saudi Arabian", "Azerbaijan",
    "Miami", "Las Vegas", "Australian",
)

ROLL_WINDOW = 3

BASE_FEATURES = [
    "QualyPos", "GridPosition", "QualyGapToPole", "IsStreetCircuit",
    "RacePos_Last_1", "RacePos_Last_2", "RacePos_Last_3",
    "driver_avg_points_last_3", "driver_avg_finish_last_3", "driver_avg_qualy_last_3",
    "season_points", "dnfs_season", "team_avg_points_last_3",
]


def feature_columns(df: pd.DataFrame) -> list[str]:
    """The exact model input columns for a feature frame."""
    teams = sorted(c for c in df.columns if c.startswith("Team_"))
    return BASE_FEATURES + teams


def build_features(master: pd.DataFrame) -> pd.DataFrame:
    """Turn merged master results into a model-ready feature frame."""
    df = master.copy()

    # -- rows that can't be trained on -------------------------------------
    df = df[~df["EventName"].str.contains("Pre-Season", case=False, na=False)]
    df = df[df["RacePos"].notna()].copy()

    df["FullName"] = df["FullName"].replace(DRIVER_MAPPING)
    df["TeamName"] = df["TeamName"].replace(TEAM_MAPPING)
    df["Points"] = df["Points"].fillna(0)

    # -- qualifying pace ----------------------------------------------------
    for col in ("Q1", "Q2", "Q3"):
        df[col] = pd.to_timedelta(df[col], errors="coerce").dt.total_seconds()
    df["QualyBest"] = df[["Q1", "Q2", "Q3"]].min(axis=1)
    pole = df.groupby(["Year", "RoundNumber"])["QualyBest"].transform("min")
    df["QualyGapToPole"] = df["QualyBest"] - pole
    # no time set: place them one second behind the slowest runner
    worst = df.groupby(["Year", "RoundNumber"])["QualyGapToPole"].transform("max")
    df["QualyGapToPole"] = df["QualyGapToPole"].fillna(worst + 1.0).fillna(5.0)

    df["QualyPos"] = df["QualyPos"].fillna(20)
    df["GridPosition"] = df["GridPosition"].fillna(df["QualyPos"])

    # -- flags and targets ----------------------------------------------------
    df["IsStreetCircuit"] = (
        df["EventName"].str.contains("|".join(STREET_EVENTS), na=False).astype(int)
    )
    df["FinishedRace"] = df["Status"].str.contains("Finished|Lapped", na=False).astype(int)
    df["IsPodium"] = (df["RacePos"] <= 3).astype(int)
    df["IsRaceWinner"] = (df["RacePos"] == 1).astype(int)

    # -- per-driver history (chronological within driver) --------------------
    df = df.sort_values(["FullName", "Year", "RoundNumber"])
    by_driver = df.groupby("FullName", sort=False)
    for n in (1, 2, 3):
        df[f"RacePos_Last_{n}"] = by_driver["RacePos"].shift(n)

    def lagged_roll_mean(s: pd.Series) -> pd.Series:
        return s.shift(1).rolling(ROLL_WINDOW, min_periods=1).mean()

    df["driver_avg_points_last_3"] = by_driver["Points"].transform(lagged_roll_mean)
    df["driver_avg_finish_last_3"] = by_driver["RacePos"].transform(lagged_roll_mean)
    df["driver_avg_qualy_last_3"] = by_driver["QualyPos"].transform(lagged_roll_mean)

    # -- season-to-date stats (reset each year, shifted) ----------------------
    by_season = df.groupby(["Year", "FullName"], sort=False)
    df["season_points"] = by_season["Points"].transform(lambda s: s.shift(1).cumsum())
    df["dnfs_season"] = by_season["FinishedRace"].transform(
        lambda s: s.eq(0).shift(1).cumsum()
    )

    # -- team form: rolling mean of the team's total points per race ---------
    team_race = (
        df.groupby(["Year", "RoundNumber", "TeamName"], as_index=False)["Points"]
        .sum()
        .rename(columns={"Points": "_team_pts"})
        .sort_values(["TeamName", "Year", "RoundNumber"])
    )
    team_race["team_avg_points_last_3"] = team_race.groupby("TeamName")[
        "_team_pts"
    ].transform(lagged_roll_mean)
    df = df.merge(
        team_race[["Year", "RoundNumber", "TeamName", "team_avg_points_last_3"]],
        on=["Year", "RoundNumber", "TeamName"],
        how="left",
    )

    # -- neutral fills for a driver/team's first appearance ------------------
    fills = {
        "RacePos_Last_1": 20, "RacePos_Last_2": 20, "RacePos_Last_3": 20,
        "driver_avg_points_last_3": 0, "driver_avg_finish_last_3": 20,
        "driver_avg_qualy_last_3": 20, "season_points": 0, "dnfs_season": 0,
        "team_avg_points_last_3": 0,
    }
    for col, value in fills.items():
        df[col] = df[col].astype(float).fillna(value)

    # -- team one-hots (TeamName itself kept for reporting) ------------------
    dummies = pd.get_dummies(df["TeamName"], prefix="Team", dtype=int)
    df = pd.concat([df, dummies], axis=1)

    return df.sort_values(["Year", "RoundNumber", "QualyPos"]).reset_index(drop=True)


def build_and_save(years: list[int] | None = None) -> pd.DataFrame:
    """Build the feature frame from master files and persist it."""
    df = build_features(load_master(years))
    FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FEATURES_FILE, index=False)
    return df


def load_features(rebuild: bool = False) -> pd.DataFrame:
    """Load the cached feature frame, building it if missing."""
    if rebuild or not FEATURES_FILE.exists():
        return build_and_save()
    return pd.read_csv(FEATURES_FILE)
