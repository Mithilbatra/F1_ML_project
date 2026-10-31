"""API endpoints."""

import pandas as pd
import pytest

from f1_ml import modeling, predict, weekend
from f1_ml.server import create_app


def test_predict_uses_the_model_marked_in_use(monkeypatch):
    seen = {}

    def fake_predict_round(year, rnd, model_name="rf", df=None):
        seen["model"] = model_name
        raise ValueError("stop here")  # the endpoint answers 400

    monkeypatch.setattr(modeling, "best_model_name", lambda: "gbdt")
    monkeypatch.setattr(predict, "predict_round", fake_predict_round)
    assert create_app().test_client().get("/api/predict/2025/5").status_code == 400
    assert seen["model"] == "gbdt"


def test_predictions_are_computed_once(monkeypatch):
    calls = []
    cols = ["EventName", "FullName", "TeamName", "QualyPos", "GridPosition",
            "prob", "PredictedPodium", "RacePos", "IsPodium"]

    def fake_predict_round(year, rnd, model_name="rf", df=None):
        calls.append(rnd)
        return pd.DataFrame([dict.fromkeys(cols, 1) | {"EventName": "Test GP"}])

    monkeypatch.setattr(predict, "predict_round", fake_predict_round)
    client = create_app().test_client()
    for _ in range(3):
        assert client.get("/api/predict/2025/5").status_code == 200
    assert calls == [5]


def test_fantasy_rejects_a_budget_that_is_not_a_number():
    assert create_app().test_client().get("/api/fantasy?budget=nan").status_code == 400


def test_circuit_guide_never_loads_unknown_events(monkeypatch):
    monkeypatch.setattr(weekend, "circuit_guide", lambda event: pytest.fail("loaded"))
    r = create_app().test_client().get("/api/circuit-guide?event=Moon Grand Prix")
    assert r.get_json() == {"available": False}
