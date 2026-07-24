"""Fantasy optimiser tests. Use the project's own feature data (no network)."""

import pytest

pytest.importorskip("sklearn")
from f1_ml import fantasy  # noqa: E402
from f1_ml.config import FEATURES_FILE  # noqa: E402

pytestmark = pytest.mark.skipif(
    not FEATURES_FILE.exists(),
    reason="needs data/processed/features.csv (run `f1ml features`)",
)


def test_points_for_finish_monotonic():
    assert fantasy._points_for_finish(1) > fantasy._points_for_finish(5)
    assert fantasy._points_for_finish(5) > fantasy._points_for_finish(15)
    assert fantasy._points_for_finish(1) == 35
    assert fantasy._points_for_finish(25) == fantasy._points_for_finish(20)  # clamped


def test_optimise_returns_legal_team():
    team = fantasy.optimise(budget=100.0)
    assert "error" not in team
    assert len(team["drivers"]) == fantasy.N_DRIVERS
    assert len(team["constructors"]) == fantasy.N_CONSTRUCTORS
    assert team["cost"] <= 100.0
    # exactly one captain, and it is one of the chosen drivers
    caps = [d for d in team["drivers"] if d["captain"]]
    assert len(caps) == 1
    assert team["captain"] in {d["name"] for d in team["drivers"]}


def test_optimise_respects_budget():
    tight = fantasy.optimise(budget=85.0)
    assert "error" not in tight
    assert tight["cost"] <= 85.0


def test_bigger_budget_scores_at_least_as_well():
    lo = fantasy.optimise(budget=90.0)["projected_points"]
    hi = fantasy.optimise(budget=105.0)["projected_points"]
    assert hi >= lo


def test_captain_doubles_points():
    team = fantasy.optimise(budget=100.0)
    cap = next(d for d in team["drivers"] if d["captain"])
    base = sum(d["proj"] for d in team["drivers"]) + sum(c["proj"] for c in team["constructors"])
    assert team["projected_points"] == pytest.approx(base + cap["proj"], abs=0.05)
