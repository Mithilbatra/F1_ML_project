import pandas as pd

from f1_ml.evaluate import evaluate_predictions, top3_hit_rate


def _context(rows):
    return pd.DataFrame(
        rows,
        columns=["Year", "RoundNumber", "EventName", "FullName", "TeamName",
                 "QualyPos", "GridPosition", "RacePos", "IsPodium", "prob"],
    )


def test_top3_hit_rate_perfect_and_zero():
    rows = []
    for i in range(6):
        podium = 1 if i < 3 else 0
        rows.append([2025, 1, "GP", f"D{i}", "T", i + 1, i + 1, i + 1, podium, 1 - i / 10])
    ctx = _context(rows)
    assert top3_hit_rate(ctx, "prob") == 1.0  # probs perfectly ordered

    ctx_bad = ctx.copy()
    ctx_bad["prob"] = ctx_bad["prob"].iloc[::-1].values  # inverted
    assert top3_hit_rate(ctx_bad, "prob") == 0.0


def test_top3_hit_rate_averages_across_races():
    rows = []
    # race 1: model nails all three
    for i in range(6):
        rows.append([2025, 1, "GP1", f"D{i}", "T", i + 1, i + 1, i + 1,
                     1 if i < 3 else 0, 1 - i / 10])
    # race 2: model gets none
    for i in range(6):
        rows.append([2025, 2, "GP2", f"D{i}", "T", i + 1, i + 1, i + 1,
                     1 if i < 3 else 0, i / 10])
    assert top3_hit_rate(_context(rows), "prob") == 0.5


def test_evaluate_predictions_bundle():
    rows = []
    for rnd in (1, 2):
        for i in range(6):
            rows.append([2025, rnd, f"GP{rnd}", f"D{i}", "T", i + 1, i + 1,
                         i + 1, 1 if i < 3 else 0, 0.9 - i / 10])
    metrics = evaluate_predictions(_context(rows))
    assert metrics["n_test_races"] == 2
    assert metrics["top3_hit_rate"] == 1.0
    assert metrics["baseline_top3_hit_rate"] == 1.0
    assert 0 <= metrics["pr_auc"] <= 1
    assert len(metrics["races"]) == 2
    assert metrics["races"][0]["hits"] == 3
