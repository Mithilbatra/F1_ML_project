"""Race-day prediction: train on everything strictly before a given round,
then rank that round's field by podium probability. This mirrors what you
could really have known on the morning of the race."""

from __future__ import annotations

import pandas as pd

from .evaluate import CONTEXT_COLS
from .features import feature_columns, load_features
from .modeling import make_model


def predict_round(
    year: int,
    rnd: int,
    model_name: str = "rf",
    df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Podium probabilities for one race, sorted best first."""
    if df is None:
        df = load_features()

    key = df["Year"] * 100 + df["RoundNumber"]
    target_key = year * 100 + rnd
    race = df[key == target_key]
    if race.empty:
        available = df[df["Year"] == year]["RoundNumber"].unique()
        raise ValueError(
            f"No data for {year} round {rnd}. "
            f"Rounds available in {year}: {sorted(int(r) for r in available)}"
        )
    train = df[key < target_key]
    if len(train) < 40:  # ~2 races of field data
        raise ValueError(
            f"Not enough history before {year} round {rnd} to train on "
            f"({len(train)} rows)."
        )

    features = feature_columns(df)
    model = make_model(model_name)
    model.fit(train[features], train["IsPodium"])

    out = race[CONTEXT_COLS].copy()
    out["prob"] = model.predict_proba(race[features])[:, 1]
    out = out.sort_values("prob", ascending=False).reset_index(drop=True)
    out["PredictedPodium"] = [1] * min(3, len(out)) + [0] * max(0, len(out) - 3)
    return out
