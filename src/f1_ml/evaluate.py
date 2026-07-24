"""Honest evaluation.

Podium prediction is a heavily imbalanced problem (3 podium spots in a ~20
car field), so plain accuracy is near-meaningless: always answering "no
podium" already scores ~85%. We therefore report:

- precision / recall / F1 for the podium class
- ROC-AUC, PR-AUC (average precision) and Brier score on probabilities
- top-3-per-race hit rate: for each race take the model's three most likely
  drivers and count how many actually made the podium
- the same hit rate for the obvious baseline (picking the top 3 qualifiers),
  because any model that can't beat the grid isn't adding information
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

CONTEXT_COLS = ["Year", "RoundNumber", "EventName", "FullName", "TeamName",
                "QualyPos", "GridPosition", "RacePos", "IsPodium"]


def top3_hit_rate(context: pd.DataFrame, score_col: str) -> float:
    """Mean fraction of each race's actual podium found in the top-3 by score."""
    hits = []
    for _, race in context.groupby(["Year", "RoundNumber"]):
        top3 = race.nlargest(3, score_col)
        hits.append(top3["IsPodium"].sum() / 3)
    return float(pd.Series(hits).mean())


def race_by_race(context: pd.DataFrame, score_col: str = "prob") -> list[dict]:
    """Per-race breakdown of picks vs. the real podium."""
    rows = []
    for (year, rnd), race in context.groupby(["Year", "RoundNumber"]):
        picks = race.nlargest(3, score_col)
        actual = race[race["IsPodium"] == 1].sort_values("RacePos")
        rows.append({
            "year": int(year),
            "round": int(rnd),
            "event": race["EventName"].iloc[0],
            "picks": picks["FullName"].tolist(),
            "pick_probs": [round(p, 3) for p in picks[score_col]],
            "actual": actual["FullName"].tolist(),
            "hits": int(picks["IsPodium"].sum()),
        })
    return rows


def evaluate_predictions(context: pd.DataFrame) -> dict:
    """Metric bundle for a context frame carrying `prob` and `IsPodium`."""
    y_true = context["IsPodium"]
    y_prob = context["prob"]
    y_pred = (y_prob >= 0.5).astype(int)

    # baseline: pick the front row of the grid (lower QualyPos = better)
    baseline = top3_hit_rate(context.assign(_neg_q=-context["QualyPos"]), "_neg_q")

    return {
        "n_test_rows": int(len(context)),
        "n_test_races": int(context.groupby(["Year", "RoundNumber"]).ngroups),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_podium": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall_podium": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_podium": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "top3_hit_rate": round(top3_hit_rate(context, "prob"), 4),
        "baseline_top3_hit_rate": round(baseline, 4),
        "races": race_by_race(context),
    }
