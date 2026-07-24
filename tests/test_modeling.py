import pandas as pd
import pytest

from f1_ml.features import build_features
from f1_ml.modeling import race_order, split_by_cutoff


@pytest.fixture
def feature_df(master_df):
    return build_features(master_df)


def test_race_order_is_chronological(feature_df):
    order = race_order(feature_df)
    assert order == sorted(order)
    assert order[0][0] == 2024 and order[-1][0] == 2025


def test_split_by_explicit_cutoff(feature_df):
    train, test, cutoff = split_by_cutoff(feature_df, cutoff=(2024, 6))
    assert cutoff == (2024, 6)
    assert train["Year"].max() == 2024
    assert (test["Year"] == 2025).all()
    # no race appears on both sides
    train_races = set(map(tuple, train[["Year", "RoundNumber"]].to_numpy()))
    test_races = set(map(tuple, test[["Year", "RoundNumber"]].to_numpy()))
    assert not train_races & test_races


def test_split_default_holds_out_tail(feature_df):
    train, test, cutoff = split_by_cutoff(feature_df, test_last=3)
    assert test.groupby(["Year", "RoundNumber"]).ngroups == 3
    # test races are strictly after every train race
    assert (test["Year"] * 100 + test["RoundNumber"]).min() > \
           (train["Year"] * 100 + train["RoundNumber"]).max()


def test_split_rejects_too_large_holdout(feature_df):
    with pytest.raises(ValueError):
        split_by_cutoff(feature_df, test_last=999)
