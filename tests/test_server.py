"""API endpoints."""

from f1_ml import modeling, predict
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
