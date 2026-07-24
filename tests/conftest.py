import numpy as np
import pandas as pd
import pytest


def _race_block(year: int, rnd: int, event: str, drivers: list[tuple]) -> pd.DataFrame:
    """One race worth of master-results rows.

    drivers: (name, team, qualy_pos, race_pos, status, points)
    """
    rows = []
    for name, team, qpos, rpos, status, points in drivers:
        rows.append({
            "Year": year, "RoundNumber": rnd, "EventName": event,
            "QualyPos": qpos, "FullName": name, "TeamName": team,
            "Q1": "0 days 00:01:30.500000",
            "Q2": "0 days 00:01:30.200000" if qpos <= 15 else np.nan,
            "Q3": f"0 days 00:01:{29.5 + qpos / 10:.6f}"[:26] if qpos <= 10 else np.nan,
            "GridPosition": qpos, "RacePos": rpos, "Status": status,
            "Points": points, "Laps": 57,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def master_df() -> pd.DataFrame:
    """Small synthetic two-season dataset with edge cases baked in."""
    points = [25, 18, 15, 12, 10, 8]
    field = ["Alpha Driver", "Beta Driver", "Gamma Driver",
             "Delta Driver", "Epsilon Driver", "Zeta Driver"]
    teams = ["McLaren", "McLaren", "Ferrari", "Ferrari", "RB", "Sauber"]

    races = []
    for year in (2024, 2025):
        # pre-season row that must be dropped
        races.append(_race_block(year, 0, "Pre-Season Testing",
                                 [(field[0], teams[0], 1, 1, "Finished", 25)]))
        for rnd in range(1, 7):
            order = list(range(len(field)))
            if rnd % 3 == 0:  # shuffle podium a bit between races
                order[0], order[2] = order[2], order[0]
            drivers = []
            for finish_idx, i in enumerate(order):
                status = "Finished"
                rpos: float = finish_idx + 1
                pts = points[finish_idx]
                if rnd == 4 and i == 5:  # a DNF
                    status, rpos, pts = "Retired", 6, 0
                drivers.append((field[i], teams[i], i + 1, rpos, status, pts))
            races.append(_race_block(year, rnd, f"Test Grand Prix {rnd}", drivers))

    df = pd.concat(races, ignore_index=True)
    # one DNS-style row: qualified but no race classification
    dns = _race_block(2025, 6, "Test Grand Prix 6",
                      [("Eta Driver", "Sauber", 7, np.nan, np.nan, 0)])
    return pd.concat([df, dns], ignore_index=True)
