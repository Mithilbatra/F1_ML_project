"""Walk-forward backtest: for every race of a season, retrain on all races
strictly before it and score the model's top-3 picks against the actual
podium — alongside the pick-the-top-3-qualifiers baseline. This is the
fairest picture of how the pipeline would have performed live."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .config import MODELS_DIR
from .features import load_features
from .predict import predict_round

MIN_TRAIN_ROWS = 60  # ~3 races of field data before we start predicting


def backtest_path(year: int, model_name: str):
    return MODELS_DIR / f"backtest_{year}_{model_name}.json"


def backtest_year(
    year: int, model_name: str = "rf", df: pd.DataFrame | None = None
) -> dict:
    if df is None:
        df = load_features()

    rounds = sorted(df.loc[df["Year"] == year, "RoundNumber"].unique())
    races = []
    for rnd in rounds:
        key = df["Year"] * 100 + df["RoundNumber"]
        if (key < year * 100 + rnd).sum() < MIN_TRAIN_ROWS:
            continue  # not enough history yet

        picks = predict_round(year, int(rnd), model_name, df)
        top3 = picks.head(3)
        actual = picks[picks["RacePos"] <= 3].sort_values("RacePos")
        qualy3 = picks.nsmallest(3, "QualyPos")

        races.append({
            "round": int(rnd),
            "event": picks["EventName"].iloc[0],
            "picks": top3["FullName"].tolist(),
            "pick_probs": [round(float(p), 3) for p in top3["prob"]],
            "actual": actual["FullName"].tolist(),
            "model_hits": int(top3["IsPodium"].sum()),
            "baseline_hits": int(qualy3["IsPodium"].sum()),
        })

    n = len(races)
    model_total = sum(r["model_hits"] for r in races)
    base_total = sum(r["baseline_hits"] for r in races)
    report = {
        "year": year,
        "model_name": model_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_races": n,
        "model_hit_rate": round(model_total / (3 * n), 4) if n else None,
        "baseline_hit_rate": round(base_total / (3 * n), 4) if n else None,
        "races": races,
    }
    MODELS_DIR.mkdir(exist_ok=True)
    backtest_path(year, model_name).write_text(json.dumps(report, indent=2))
    return report
