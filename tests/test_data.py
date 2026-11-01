"""Championship standings."""

import pandas as pd
import pytest

from f1_ml.config import atomic_write
from f1_ml.data import compute_standings, driver_key


def test_atomic_write_never_leaves_a_half_written_file(tmp_path):
    target = tmp_path / "metrics.json"
    target.write_text("old")

    def crash_midway(p):
        p.write_text("half")
        raise OSError("disk full")

    with pytest.raises(OSError):
        atomic_write(target, crash_midway)
    assert target.read_text() == "old"
    assert list(tmp_path.iterdir()) == [target]  # no stray temp file

    atomic_write(target, lambda p: p.write_text("new"))
    assert target.read_text() == "new"


def test_driver_key_survives_fastf1_spelling_changes():
    raw = pd.Series(["Sergio Pérez", "Nico Hülkenberg", "Andrea Kimi Antonelli"])
    assert driver_key(raw).tolist() == ["Sergio Perez", "Nico Hulkenberg", "Kimi Antonelli"]


def test_standings_include_sprint_points(master_df):
    base = compute_standings(master_df, 2025)["drivers"].set_index("FullName")["Points"]

    df = master_df.copy()
    df["SprintPoints"] = 0.0
    won_sprint = (df["Year"] == 2025) & (df["RoundNumber"] == 2) & (df["FullName"] == "Zeta Driver")
    df.loc[won_sprint, "SprintPoints"] = 8
    got = compute_standings(df, 2025)["drivers"].set_index("FullName")["Points"]

    assert got["Zeta Driver"] == base["Zeta Driver"] + 8
    assert got["Alpha Driver"] == base["Alpha Driver"]
