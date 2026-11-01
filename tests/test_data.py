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


def test_fetch_leaves_sessions_not_run_yet_or_already_saved(tmp_path, monkeypatch):
    """FastF1 allows 500 calls an hour: a refresh must not re-download every race."""
    import fastf1
    from fastf1.events import EventSchedule

    from f1_ml import data

    now = pd.Timestamp.now("UTC").tz_localize(None)
    names = ["Old GP", "Unsaved GP", "Recent GP", "Future GP"]
    held = [now - pd.Timedelta(days=d) for d in (30, 30, 2, -3)]
    schedule = EventSchedule(pd.DataFrame({
        "RoundNumber": [1, 2, 3, 4], "EventName": names, "EventFormat": ["conventional"] * 4,
        **{f"Session{i}": [""] * 4 for i in range(1, 5)},
        "Session5": ["Race"] * 4, "Session5Date": held, "Session5DateUtc": held,
    }), year=2026)
    for rnd in (1, 3):  # already on disk
        saved = tmp_path / "2026" / f"2026_Round_0{rnd}_{names[rnd - 1].replace(' ', '_')}_Race.csv"
        saved.parent.mkdir(exist_ok=True)
        saved.write_text("Year\n2026\n")

    loaded = []

    def fake_get_session(year, gp, code):
        loaded.append(gp)
        raise ValueError("offline")

    monkeypatch.setattr(fastf1, "get_event_schedule", lambda year: schedule)
    monkeypatch.setattr(fastf1, "get_session", fake_get_session)
    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda path: None)
    monkeypatch.setitem(data._SESSIONS, "race", ("R", tmp_path))

    data.fetch_year(2026, "race")
    assert loaded == ["Unsaved GP", "Recent GP"]


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
