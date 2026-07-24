"""Data access: fetching raw sessions from FastF1, merging qualifying with race
results into per-season master files, and loading them back."""

from __future__ import annotations

import logging

import pandas as pd

from .config import (
    FASTF1_CACHE_DIR,
    PROCESSED_DIR,
    RAW_QUALY_DIR,
    RAW_RACE_DIR,
    master_file,
)

log = logging.getLogger(__name__)

RACE_COLUMNS = [
    "Position", "FullName", "TeamName",
    "Status", "Points", "Laps", "GridPosition",
]
QUALY_COLUMNS = ["Position", "FullName", "TeamName", "Q1", "Q2", "Q3"]

# Sessions merged on these keys; race adds the outcome columns.
MERGE_KEYS = ["Year", "RoundNumber", "EventName", "FullName", "TeamName"]
RACE_OUTCOME_COLUMNS = ["GridPosition", "RacePos", "Status", "Points", "Laps"]


# ---------------------------------------------------------------- fetching

def fetch_year(year: int, kind: str = "both") -> list[str]:
    """Download session results for a season via FastF1 and save raw CSVs.

    kind: "race", "qualifying" or "both". Returns list of files written.
    """
    import fastf1  # lazy: heavy import + not needed for offline work

    FASTF1_CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(FASTF1_CACHE_DIR)

    kinds = ["qualifying", "race"] if kind == "both" else [kind]
    schedule = fastf1.get_event_schedule(year)
    written: list[str] = []

    for _, event in schedule.iterrows():
        event_name = event["EventName"]
        round_number = event["RoundNumber"]
        if round_number == 0:
            continue  # pre-season testing has no meaningful classification

        for k in kinds:
            session_code = "R" if k == "race" else "Q"
            out_dir = (RAW_RACE_DIR if k == "race" else RAW_QUALY_DIR) / str(year)
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                session = fastf1.get_session(year, event_name, session_code)
                session.load(telemetry=False, weather=False, messages=False)
            except Exception as exc:  # race may not have happened yet
                log.warning("Skipping %s %s (%s): %s", year, event_name, k, exc)
                continue
            if session.results is None or len(session.results) == 0:
                log.warning("No results for %s %s (%s)", year, event_name, k)
                continue

            cols = RACE_COLUMNS if k == "race" else QUALY_COLUMNS
            results = session.results[cols].copy()
            results.insert(0, "EventName", event_name)
            results.insert(0, "RoundNumber", round_number)
            results.insert(0, "Year", year)

            suffix = "Race" if k == "race" else "Qualifying"
            name = f"{year}_Round_{str(round_number).zfill(2)}_{event_name.replace(' ', '_')}_{suffix}.csv"
            path = out_dir / name
            results.to_csv(path, index=False)
            written.append(str(path))
            log.info("Saved %s", path)

    return written


# ----------------------------------------------------------------- merging

def merge_year(year: int) -> pd.DataFrame:
    """Combine raw qualifying + race CSVs for a season into one master file."""
    qualy_dir = RAW_QUALY_DIR / str(year)
    race_dir = RAW_RACE_DIR / str(year)

    qualy_files = sorted(qualy_dir.glob("*.csv"))
    race_files = sorted(race_dir.glob("*.csv"))
    if not qualy_files:
        raise FileNotFoundError(
            f"No qualifying CSVs in {qualy_dir}. Run `f1ml fetch --year {year}` first."
        )
    if not race_files:
        raise FileNotFoundError(
            f"No race CSVs in {race_dir}. Run `f1ml fetch --year {year}` first."
        )

    # header-only CSVs (races fetched before they ran) would poison concat dtypes
    qualy_frames = [f for f in map(pd.read_csv, qualy_files) if not f.empty]
    race_frames = [f for f in map(pd.read_csv, race_files) if not f.empty]
    qualy = pd.concat(qualy_frames, ignore_index=True)
    race = pd.concat(race_frames, ignore_index=True)

    qualy = qualy.rename(columns={"Position": "QualyPos"})
    race = race.rename(columns={"Position": "RacePos"})

    master = qualy.merge(
        race[MERGE_KEYS + RACE_OUTCOME_COLUMNS], on=MERGE_KEYS, how="left"
    )
    master = master.sort_values(["Year", "RoundNumber", "QualyPos"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = master_file(year)
    master.to_csv(out_path, index=False)
    log.info("Master file for %s saved to %s (%d rows)", year, out_path, len(master))
    return master


# ----------------------------------------------------------------- loading

def available_years() -> list[int]:
    """Seasons that have a master results file."""
    years = []
    for path in PROCESSED_DIR.glob("*_master_results.csv"):
        prefix = path.name.split("_", 1)[0]
        if prefix.isdigit():
            years.append(int(prefix))
    return sorted(years)


def load_master(years: list[int] | None = None) -> pd.DataFrame:
    """Load and concatenate master result files for the given seasons."""
    years = years or available_years()
    if not years:
        raise FileNotFoundError(
            f"No master result files in {PROCESSED_DIR}. Run `f1ml merge` first."
        )
    frames = [pd.read_csv(master_file(y)) for y in years if master_file(y).exists()]
    if not frames:
        raise FileNotFoundError(f"No master files found for years {years}.")
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------- standings

def compute_standings(master: pd.DataFrame, year: int) -> dict:
    """Driver and constructor standings for a season, from race results."""
    from .features import DRIVER_MAPPING, TEAM_MAPPING  # avoid import cycle

    df = master[master["Year"] == year].copy()
    df = df[~df["EventName"].str.contains("Pre-Season", case=False, na=False)]
    df = df[df["RacePos"].notna()]
    df["FullName"] = df["FullName"].replace(DRIVER_MAPPING)
    df["TeamName"] = df["TeamName"].replace(TEAM_MAPPING)
    df["Points"] = df["Points"].fillna(0)

    drivers = (
        df.groupby("FullName")
        .agg(
            Team=("TeamName", "last"),
            Points=("Points", "sum"),
            Wins=("RacePos", lambda s: int((s == 1).sum())),
            Podiums=("RacePos", lambda s: int((s <= 3).sum())),
            Races=("RacePos", "count"),
        )
        .sort_values(["Points", "Wins"], ascending=False)
        .reset_index()
    )
    drivers.insert(0, "Pos", range(1, len(drivers) + 1))

    teams = (
        df.groupby("TeamName")
        .agg(
            Points=("Points", "sum"),
            Wins=("RacePos", lambda s: int((s == 1).sum())),
            Podiums=("RacePos", lambda s: int((s <= 3).sum())),
        )
        .sort_values(["Points", "Wins"], ascending=False)
        .reset_index()
    )
    teams.insert(0, "Pos", range(1, len(teams) + 1))

    return {"drivers": drivers, "constructors": teams}
