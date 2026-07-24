"""Model training with strict time-ordered splits.

Races are ordered chronologically as (Year, RoundNumber) pairs; the test set
is always the tail of that ordering, so the model never sees the future.
Artifacts are saved as a dict bundling the estimator with the exact feature
list and split metadata — no more re-deriving feature columns by hand when
evaluating or predicting.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

from .config import METRICS_FILE, MODELS_DIR, RANDOM_STATE
from .evaluate import CONTEXT_COLS, evaluate_predictions
from .features import feature_columns

MODEL_NAMES = ("rf", "gbdt")


def make_model(name: str):
    if name == "rf":
        return RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    if name == "gbdt":
        return HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=4,
            learning_rate=0.08,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )
    raise ValueError(f"Unknown model '{name}'. Choose from {MODEL_NAMES}.")


def tuned_model(name: str, X, y):
    """Optional small grid search with time-series CV."""
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

    grids = {
        "rf": {
            "n_estimators": [200, 400],
            "max_depth": [6, 12, None],
            "min_samples_leaf": [1, 2, 4],
        },
        "gbdt": {
            "max_iter": [150, 300],
            "max_depth": [3, 4, 6],
            "learning_rate": [0.05, 0.08, 0.15],
        },
    }
    search = GridSearchCV(
        make_model(name), grids[name],
        cv=TimeSeriesSplit(n_splits=3), scoring="average_precision", n_jobs=-1,
    )
    search.fit(X, y)
    return search.best_estimator_, search.best_params_


# ------------------------------------------------------------------ splits

def race_order(df: pd.DataFrame) -> list[tuple[int, int]]:
    """All (year, round) pairs in chronological order."""
    pairs = df[["Year", "RoundNumber"]].drop_duplicates().sort_values(
        ["Year", "RoundNumber"]
    )
    return [tuple(map(int, p)) for p in pairs.to_numpy()]


def split_by_cutoff(
    df: pd.DataFrame,
    cutoff: tuple[int, int] | None = None,
    test_last: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[int, int]]:
    """Train on races up to and including `cutoff`, test on everything after.

    Without an explicit cutoff, the last `test_last` races are held out.
    """
    order = race_order(df)
    if cutoff is None:
        if len(order) <= test_last:
            raise ValueError(f"Only {len(order)} races available; cannot hold out {test_last}.")
        cutoff = order[-(test_last + 1)]
    key = df["Year"] * 100 + df["RoundNumber"]
    cut = cutoff[0] * 100 + cutoff[1]
    return df[key <= cut], df[key > cut], cutoff


# ---------------------------------------------------------------- training

def train_and_evaluate(
    df: pd.DataFrame,
    model_name: str = "rf",
    cutoff: tuple[int, int] | None = None,
    test_last: int = 6,
    tune: bool = False,
    target: str = "IsPodium",
) -> dict:
    """Train one model, evaluate on the held-out tail, save the artifact."""
    features = feature_columns(df)
    train_df, test_df, cutoff = split_by_cutoff(df, cutoff, test_last)
    if test_df.empty:
        raise ValueError(f"No races after cutoff {cutoff}; nothing to test on.")

    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]

    best_params = None
    if tune:
        model, best_params = tuned_model(model_name, X_train, y_train)
    else:
        model = make_model(model_name)
        model.fit(X_train, y_train)

    context = test_df[CONTEXT_COLS].copy()
    context["prob"] = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_predictions(context)

    artifact = {
        "model": model,
        "model_name": model_name,
        "features": features,
        "target": target,
        "cutoff": list(cutoff),
        "train_rows": int(len(train_df)),
        "best_params": best_params,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    MODELS_DIR.mkdir(exist_ok=True)
    path = MODELS_DIR / f"podium_{model_name}.pkl"
    joblib.dump(artifact, path)

    return {
        "artifact_path": str(path),
        "model_name": model_name,
        "cutoff": list(cutoff),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "best_params": best_params,
        "metrics": metrics,
    }


def train_all(
    df: pd.DataFrame,
    cutoff: tuple[int, int] | None = None,
    test_last: int = 6,
    tune: bool = False,
) -> dict:
    """Train every model variant, persist a comparison in metrics.json."""
    results = {
        name: train_and_evaluate(df, name, cutoff, test_last, tune)
        for name in MODEL_NAMES
    }
    best = max(results, key=lambda n: results[n]["metrics"]["top3_hit_rate"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "best_model": best,
        "models": results,
    }
    METRICS_FILE.parent.mkdir(exist_ok=True)
    METRICS_FILE.write_text(json.dumps(report, indent=2))
    return report


def load_artifact(model_name: str = None) -> dict:
    """Load a saved model artifact (defaults to the best from metrics.json)."""
    if model_name is None:
        if METRICS_FILE.exists():
            model_name = json.loads(METRICS_FILE.read_text())["best_model"]
        else:
            model_name = "rf"
    path = MODELS_DIR / f"podium_{model_name}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `f1ml train` first.")
    return joblib.load(path)


def feature_importance(artifact: dict, df: pd.DataFrame) -> list[dict]:
    """Impurity importances for RF; permutation importances otherwise."""
    model, features = artifact["model"], artifact["features"]
    if hasattr(model, "feature_importances_"):
        pairs = zip(features, model.feature_importances_)
    else:
        from sklearn.inspection import permutation_importance

        _, test_df, _ = split_by_cutoff(df, tuple(artifact["cutoff"]))
        result = permutation_importance(
            model, test_df[features], test_df[artifact["target"]],
            n_repeats=5, random_state=RANDOM_STATE, scoring="average_precision",
        )
        pairs = zip(features, result.importances_mean)
    ranked = sorted(pairs, key=lambda p: p[1], reverse=True)
    return [{"feature": f, "importance": round(float(v), 5)} for f, v in ranked]
