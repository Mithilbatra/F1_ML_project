"""Analysis + forward-looking-forecast tests (local data, no network)."""

import pytest

from f1_ml.config import FEATURES_FILE, master_file

pytestmark = pytest.mark.skipif(
    not (master_file(2025).exists() and FEATURES_FILE.exists()),
    reason="needs master + feature data",
)

from f1_ml import analysis, weekend  # noqa: E402


def test_circuit_history_structure():
    h = analysis.circuit_history("Belgian Grand Prix")
    assert h["editions"]                       # at least one past edition
    for e in h["editions"]:
        assert e["year"] and "winner" in e
    # editions are newest-first
    years = [e["year"] for e in h["editions"]]
    assert years == sorted(years, reverse=True)
    assert all({"driver", "starts", "podiums"} <= set(r) for r in h["driver_record"])


def test_teammate_battles_are_consistent():
    battles = analysis.teammate_battles(2025)
    assert battles
    for b in battles:
        assert b["a"] != b["b"]
        # each head-to-head tally is non-negative
        assert all(v >= 0 for v in b["quali"] + b["race"])


def test_driver_profile():
    p = analysis.driver_profile(2025, "Lando Norris")
    assert p["position"] >= 1
    assert p["races"] > 0
    assert p["teammate"] is not None
    assert p["best_finish"] is not None


def test_driver_profile_unknown_raises():
    with pytest.raises(ValueError):
        analysis.driver_profile(2025, "Nobody McNobody")


def test_race_forecast_blends_circuit_history():
    fc = weekend.race_forecast("Belgian Grand Prix", top=10)
    assert fc["has_circuit_history"]
    probs = [r["prob"] for r in fc["projection"]]
    assert probs == sorted(probs, reverse=True)
    # every row carries both the form and circuit signals it was blended from
    for r in fc["projection"]:
        assert "form_prob" in r and "circuit_podium_rate" in r
        assert 0.0 <= r["prob"] <= 1.0
