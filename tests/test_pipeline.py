"""The refresh pipeline and the in-server auto-refresh scheduler."""

import threading

import pandas as pd

from f1_ml import backtest, data, features, modeling, pipeline, server


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


def test_refresh_only_redoes_backtests_that_can_change(monkeypatch, tmp_path):
    done = []
    (tmp_path / "2024.json").write_text("{}")  # 2024 already backtested
    monkeypatch.setattr(features, "build_and_save", lambda: pd.DataFrame({"x": [1]}))
    monkeypatch.setattr(modeling, "train_all", lambda df: {
        "best_model": "rf", "models": {"rf": {"metrics": {"top3_hit_rate": 0.5}}}})
    monkeypatch.setattr(data, "available_years", lambda: [2024, 2025, 2026])
    monkeypatch.setattr(backtest, "backtest_path", lambda y, m: tmp_path / f"{y}.json")
    monkeypatch.setattr(backtest, "backtest_year", lambda y, m: done.append(y))

    pipeline.refresh(2026, fetch=False, log=lambda *a: None)
    assert done == [2025, 2026]  # missing one + the season being refreshed


def test_refresh_fills_finished_seasons_too(monkeypatch):
    # a fresh deploy starts from git's data, which can lack a season's last rounds;
    # one season failing to fetch must not stop the others
    pulled = []

    def fetch_year(y):
        pulled.append(y)
        if y == 2024:
            raise OSError("offline")
        return []

    monkeypatch.setattr(data, "available_years", lambda: [2024, 2025])
    monkeypatch.setattr(data, "fetch_year", fetch_year)
    monkeypatch.setattr(data, "merge_year", lambda y: None)
    monkeypatch.setattr(features, "build_and_save", lambda: pd.DataFrame({"x": [1]}))
    monkeypatch.setattr(modeling, "train_all", lambda df: {
        "best_model": "rf", "models": {"rf": {"metrics": {"top3_hit_rate": 0.5}}}})

    pipeline.refresh(2026, backtest=False, log=lambda *a: None)
    assert pulled == [2024, 2025, 2026]


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
