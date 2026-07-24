"""Weekend form-forecast tests (no network — uses local feature data)."""

import pytest

pytest.importorskip("sklearn")
from f1_ml import weekend  # noqa: E402
from f1_ml.config import FEATURES_FILE  # noqa: E402
from f1_ml.features import load_features  # noqa: E402

pytestmark = pytest.mark.skipif(
    not FEATURES_FILE.exists(),
    reason="needs data/processed/features.csv (run `f1ml features`)",
)


def test_form_features_exclude_qualifying():
    feats = weekend._form_features(load_features())
    assert "QualyPos" not in feats
    assert "GridPosition" not in feats
    assert "QualyGapToPole" not in feats
    # form signals are kept
    assert "driver_avg_finish_last_3" in feats
    assert "season_points" in feats


def test_form_forecast_ranked_probabilities():
    fc = weekend.form_forecast(top=8)
    proj = fc["projection"]
    assert 1 <= len(proj) <= 8
    probs = [r["prob"] for r in proj]
    assert probs == sorted(probs, reverse=True)          # ranked
    assert all(0.0 <= p <= 1.0 for p in probs)           # valid probabilities
    assert all({"driver", "team", "prob", "season_points"} <= set(r) for r in proj)
