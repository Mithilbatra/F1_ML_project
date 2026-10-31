"""The refresh pipeline and the in-server auto-refresh scheduler."""

import threading

from f1_ml import pipeline, server


def test_refresh_rebuilds_and_retrains_offline():
    # fetch=False keeps it off the network; it should still rebuild + retrain
    # from the bundled seasons and report which years it trained on.
    result = pipeline.refresh(fetch=False, backtest=False, log=lambda *a: None)
    assert result["rows"] > 0
    assert 2024 in result["years"] and 2025 in result["years"]
    assert 0.0 <= result["top3_hit_rate"] <= 1.0
    assert result["best_model"] in {"rf", "gbdt"}
    # the Model tab reads importance saved at training time, not recomputed per view
    model = server.create_app().test_client().get("/api/model").get_json()
    assert model["importance"][0]["feature"]


def test_scheduler_off_by_default(monkeypatch):
    monkeypatch.delenv("PITWALL_AUTO_REFRESH", raising=False)
    monkeypatch.setattr(server, "_auto_refresh_started", False)
    assert server._maybe_start_auto_refresh() is False
    assert "pitwall-auto-refresh" not in [t.name for t in threading.enumerate()]


def test_scheduler_starts_when_enabled(monkeypatch):
    # a huge delay means the thread starts but never actually fetches here
    monkeypatch.setenv("PITWALL_AUTO_REFRESH", "24")
    monkeypatch.setenv("PITWALL_AUTO_REFRESH_DELAY", "99999")
    monkeypatch.setattr(server, "_auto_refresh_started", False)
    try:
        assert server._maybe_start_auto_refresh() is True
        assert "pitwall-auto-refresh" in [t.name for t in threading.enumerate()]
        # already-started guard: a second call is a no-op
        assert server._maybe_start_auto_refresh() is False
    finally:
        server._auto_refresh_started = False
