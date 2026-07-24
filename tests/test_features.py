import numpy as np
import pandas as pd

from f1_ml.features import build_features, feature_columns


def test_drops_preseason_and_unclassified_rows(master_df):
    df = build_features(master_df)
    assert not df["EventName"].str.contains("Pre-Season").any()
    # the DNS row (no RacePos) must be gone, not turned into a fake P20
    assert "Eta Driver" not in df["FullName"].values
    assert df["RacePos"].notna().all()


def test_targets(master_df):
    df = build_features(master_df)
    race = df[(df["Year"] == 2024) & (df["RoundNumber"] == 1)]
    assert race["IsPodium"].sum() == 3
    assert race["IsRaceWinner"].sum() == 1
    winner = race.loc[race["IsRaceWinner"] == 1, "RacePos"].iloc[0]
    assert winner == 1


def test_lag_features_do_not_leak(master_df):
    """A driver's lag for round N must equal their result in round N-1 —
    never anything from round N itself."""
    df = build_features(master_df)
    alpha = df[df["FullName"] == "Alpha Driver"].sort_values(["Year", "RoundNumber"])
    r2024 = alpha[alpha["Year"] == 2024]
    for prev, cur in zip(r2024.itertuples(), list(r2024.itertuples())[1:]):
        assert cur.RacePos_Last_1 == prev.RacePos


def test_rolling_average_stays_within_driver(master_df):
    """Regression test for the old bug where .rolling() ran over a
    round-sorted frame and mixed neighbouring drivers' results."""
    df = build_features(master_df)
    zeta = df[(df["FullName"] == "Zeta Driver") & (df["Year"] == 2024)]
    zeta = zeta.sort_values("RoundNumber")
    # Zeta finishes P6 every round (never podiums, points 8 or 0 on DNF round)
    # so their rolling finish average can never dip below 5.
    later = zeta[zeta["RoundNumber"] >= 2]
    assert (later["driver_avg_finish_last_3"] >= 5).all()


def test_season_stats_reset_between_years(master_df):
    df = build_features(master_df)
    alpha_2025_r1 = df[
        (df["FullName"] == "Alpha Driver") & (df["Year"] == 2025) & (df["RoundNumber"] == 1)
    ].iloc[0]
    assert alpha_2025_r1["season_points"] == 0
    assert alpha_2025_r1["dnfs_season"] == 0


def test_dnf_counted_in_season_stats(master_df):
    df = build_features(master_df)
    zeta = df[(df["FullName"] == "Zeta Driver") & (df["Year"] == 2024)]
    after_dnf = zeta[zeta["RoundNumber"] == 5].iloc[0]  # DNF was round 4
    assert after_dnf["dnfs_season"] == 1


def test_team_normalisation(master_df):
    df = build_features(master_df)
    assert "Team_Racing Bulls" in df.columns  # 'RB' normalised
    assert "Team_Kick Sauber" in df.columns   # 'Sauber' normalised
    assert "Team_RB" not in df.columns
    assert "Team_Sauber" not in df.columns


def test_feature_columns_are_numeric_and_complete(master_df):
    df = build_features(master_df)
    cols = feature_columns(df)
    assert "QualyPos" in cols and "GridPosition" in cols  # known pre-race, must be in
    assert "RacePos" not in cols and "Points" not in cols  # outcomes must stay out
    assert df[cols].isna().sum().sum() == 0
    assert all(np.issubdtype(df[c].dtype, np.number) for c in cols)


def test_qualy_gap_to_pole(master_df):
    df = build_features(master_df)
    race = df[(df["Year"] == 2024) & (df["RoundNumber"] == 1)]
    assert race["QualyGapToPole"].min() == 0  # pole sitter
    assert (race["QualyGapToPole"] >= 0).all()
