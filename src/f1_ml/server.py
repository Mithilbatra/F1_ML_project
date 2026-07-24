"""Flask backend for the Pit Wall dashboard.

Serves the static frontend from web/ plus a JSON API over the same data the
CLI uses. The /api/command endpoint executes whitelisted `f1ml` subcommands
in a subprocess and streams stdout back, so the browser console has full
parity with the real terminal.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys

import pandas as pd
from flask import Flask, Response, jsonify, request

from .config import METRICS_FILE, PROJECT_ROOT, WEB_DIR

log = logging.getLogger(__name__)


def _child_env() -> dict:
    """Environment for console subprocesses.

    The server may be launched by a bare interpreter (see run_server.py) whose
    default import path knows neither f1_ml nor the venv packages. Propagating
    the parent's sys.path via PYTHONPATH guarantees the child resolves imports
    exactly as we do.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    paths = [p for p in sys.path if p] + ([existing] if existing else [])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env

# Subcommands the browser console may run. `serve` is excluded (recursion),
# everything else mirrors the real CLI.
ALLOWED_SUBCOMMANDS = {
    "info", "fetch", "merge", "features", "train",
    "evaluate", "predict", "backtest", "standings",
    "weekend", "fantasy", "h2h", "raceline",
}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9:._=-]+$")


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> None)."""
    return json.loads(df.to_json(orient="records"))


def _clean_master(year: int) -> pd.DataFrame:
    from .data import load_master
    from .features import DRIVER_MAPPING, TEAM_MAPPING

    df = load_master([year])
    df = df[~df["EventName"].str.contains("Pre-Season", case=False, na=False)].copy()
    df["FullName"] = df["FullName"].replace(DRIVER_MAPPING)
    df["TeamName"] = df["TeamName"].replace(TEAM_MAPPING)
    return df


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    # ------------------------------------------------------------- data api

    @app.get("/api/seasons")
    def seasons():
        from .data import available_years

        return jsonify({"years": available_years()})

    @app.get("/api/summary/<int:year>")
    def summary(year: int):
        from .data import compute_standings

        df = _clean_master(year)
        raced = df[df["RacePos"].notna()]
        standings = compute_standings(df, year)
        leader = standings["drivers"].iloc[0]
        top_team = standings["constructors"].iloc[0]

        last_round = int(raced["RoundNumber"].max())
        last_race = raced[raced["RoundNumber"] == last_round]
        podium = last_race[last_race["RacePos"] <= 3].sort_values("RacePos")

        return jsonify({
            "year": year,
            "races": int(raced["RoundNumber"].nunique()),
            "drivers": int(raced["FullName"].nunique()),
            "teams": int(raced["TeamName"].nunique()),
            "entries": int(len(raced)),
            "leader": {"name": leader["FullName"], "team": leader["Team"],
                       "points": float(leader["Points"]), "wins": int(leader["Wins"])},
            "top_team": {"name": top_team["TeamName"], "points": float(top_team["Points"])},
            "last_race": {
                "round": last_round,
                "event": last_race["EventName"].iloc[0],
                "podium": _records(podium[["RacePos", "FullName", "TeamName"]]),
            },
        })

    @app.get("/api/races/<int:year>")
    def races(year: int):
        df = _clean_master(year)
        raced = df[df["RacePos"].notna()]
        out = []
        for rnd, race in raced.groupby("RoundNumber"):
            podium = race[race["RacePos"] <= 3].sort_values("RacePos")
            pole = race[race["QualyPos"] == 1]
            out.append({
                "round": int(rnd),
                "event": race["EventName"].iloc[0],
                "winner": podium["FullName"].iloc[0] if len(podium) else None,
                "winner_team": podium["TeamName"].iloc[0] if len(podium) else None,
                "podium": podium["FullName"].tolist(),
                "pole": pole["FullName"].iloc[0] if len(pole) else None,
            })
        return jsonify({"year": year, "races": out})

    @app.get("/api/race/<int:year>/<int:rnd>")
    def race_detail(year: int, rnd: int):
        df = _clean_master(year)
        race = df[df["RoundNumber"] == rnd].copy()
        if race.empty:
            return jsonify({"error": f"No data for {year} round {rnd}"}), 404
        race = race.sort_values("RacePos", na_position="last")
        cols = ["RacePos", "FullName", "TeamName", "QualyPos", "GridPosition",
                "Status", "Points", "Laps"]
        return jsonify({
            "year": year, "round": rnd,
            "event": race["EventName"].iloc[0],
            "classification": _records(race[cols]),
        })

    @app.get("/api/standings/<int:year>")
    def standings(year: int):
        from .data import compute_standings

        result = compute_standings(_clean_master(year), year)
        return jsonify({
            "year": year,
            "drivers": _records(result["drivers"]),
            "constructors": _records(result["constructors"]),
        })

    # ------------------------------------------------------------ model api

    @app.get("/api/model")
    def model():
        if not METRICS_FILE.exists():
            return jsonify({"available": False,
                            "hint": "Run `f1ml train` in the console to train models."})
        report = json.loads(METRICS_FILE.read_text())
        importance = []
        try:
            from .features import load_features
            from .modeling import feature_importance, load_artifact

            artifact = load_artifact(report["best_model"])
            importance = feature_importance(artifact, load_features())
        except Exception:
            pass
        return jsonify({"available": True, "report": report,
                        "importance": importance[:12]})

    @app.get("/api/backtest/<int:year>")
    def backtest(year: int):
        from .backtest import backtest_path

        path = backtest_path(year, "rf")
        if not path.exists():
            return jsonify({"available": False,
                            "hint": f"Run `f1ml backtest --year {year}` in the console."})
        return jsonify({"available": True, "report": json.loads(path.read_text())})

    @app.get("/api/predict/<int:year>/<int:rnd>")
    def predict(year: int, rnd: int):
        from .predict import predict_round

        try:
            out = predict_round(year, rnd)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        cols = ["FullName", "TeamName", "QualyPos", "GridPosition",
                "prob", "PredictedPodium", "RacePos", "IsPodium"]
        return jsonify({
            "year": year, "round": rnd,
            "event": out["EventName"].iloc[0],
            "predictions": _records(out[cols]),
        })

    # -------------------------------------------------------- racing line

    @app.post("/api/racingline")
    def racingline():
        try:
            from . import racingline as rl
        except ImportError:
            return jsonify({"error": "Server is missing the 'vision' extra. "
                            "Install with: uv sync --extra vision"}), 501

        upload = request.files.get("image")
        if upload is None:
            return jsonify({"error": "No image uploaded."}), 400
        length_km = request.form.get("length_km", type=float)
        try:
            image = rl.decode_image(upload.read())
            result = rl.analyze(image, track_length_km=length_km)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    # -------------------------------------------------------- telemetry api

    @app.get("/api/tel/events/<int:year>")
    def tel_events(year: int):
        from . import telemetry as tel

        try:
            return jsonify({"year": year, "events": tel.event_schedule(year)})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/tel/session/<int:year>/<int:rnd>/<sc>")
    def tel_session(year: int, rnd: int, sc: str):
        from . import telemetry as tel

        try:
            session = tel.load_session(year, str(rnd), sc, telemetry=False)
            return jsonify({"drivers": tel.session_drivers(session),
                            "event": session.event["EventName"]})
        except Exception as exc:
            return jsonify({"error": f"Could not load {sc} for {year} round {rnd}: {exc}"}), 502

    @app.get("/api/tel/h2h/<int:year>/<int:rnd>/<sc>")
    def tel_h2h(year: int, rnd: int, sc: str):
        from . import telemetry as tel

        d1 = request.args.get("d1")
        d2 = request.args.get("d2")
        if not d1 or not d2:
            return jsonify({"error": "Pick two drivers."}), 400
        try:
            return jsonify(tel.head_to_head(year, str(rnd), sc, d1, d2))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/tel/strategy/<int:year>/<int:rnd>")
    def tel_strategy(year: int, rnd: int):
        from . import telemetry as tel

        try:
            return jsonify(tel.tyre_strategy(year, str(rnd), "R"))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/tel/pace/<int:year>/<int:rnd>")
    def tel_pace(year: int, rnd: int):
        from . import telemetry as tel

        try:
            return jsonify(tel.race_pace(year, str(rnd), "R"))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    # -------------------------------------------------- weekend / fantasy

    @app.get("/api/weekend")
    def weekend():
        from . import weekend as wk

        try:
            nxt = wk.next_race()
        except Exception as exc:
            nxt = None
            log.warning("next_race failed: %s", exc)
        try:
            forecast = wk.form_forecast()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify({"next_race": nxt, "forecast": forecast})

    @app.get("/api/fantasy")
    def fantasy():
        from . import fantasy as fan

        budget = request.args.get("budget", default=100.0, type=float)
        try:
            return jsonify(fan.optimise(budget))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    _hub_cache = {"t": 0.0, "data": None}

    @app.get("/api/hub")
    def hub():
        import time

        from . import fantasy as fan
        from . import weekend as wk
        from .analysis import circuit_history, teammate_battles

        # the hub trains a small model + optimises a team on every call;
        # cache it for 10 minutes so revisits are instant
        if _hub_cache["data"] is not None and time.time() - _hub_cache["t"] < 600:
            return jsonify(_hub_cache["data"])

        try:
            nxt = wk.next_race()
        except Exception:
            nxt = None
        event = nxt["event"] if nxt else None
        try:
            forecast = wk.race_forecast(event)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        history = None
        if event:
            try:
                history = circuit_history(event)
            except Exception:
                history = None
        try:
            team = fan.optimise(100.0)
        except Exception:
            team = None
        season = forecast["based_on_season"]
        try:
            battles = teammate_battles(season)
        except Exception:
            battles = []
        payload = {"next_race": nxt, "forecast": forecast,
                   "history": history, "fantasy": team, "battles": battles}
        _hub_cache.update(t=time.time(), data=payload)
        return jsonify(payload)

    @app.get("/api/circuit-guide")
    def circuit_guide():
        from . import weekend as wk

        event = request.args.get("event")
        if not event:
            return jsonify({"error": "event required"}), 400
        try:
            guide = wk.circuit_guide(event)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        if guide is None:
            return jsonify({"available": False})
        return jsonify({"available": True, "guide": guide})

    @app.get("/api/driver")
    def driver():
        from .analysis import driver_profile

        year = request.args.get("year", type=int)
        name = request.args.get("name")
        if not year or not name:
            return jsonify({"error": "year and name required"}), 400
        try:
            return jsonify(driver_profile(year, name))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/quali/<int:year>/<int:rnd>")
    def quali(year: int, rnd: int):
        from .analysis import qualifying_analysis

        try:
            return jsonify(qualifying_analysis(year, rnd))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/practice/<int:year>/<int:rnd>")
    def practice(year: int, rnd: int):
        from .analysis import practice_pace

        try:
            return jsonify(practice_pace(year, rnd))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    # ---------------------------------------------------------- console api

    @app.post("/api/command")
    def command():
        # on public deployments the console runner is disabled so strangers
        # can't spin up f1ml jobs on the host
        if os.environ.get("PITWALL_DISABLE_CONSOLE"):
            return jsonify({"error": "The console is disabled on this hosted "
                            "demo. Run it locally to use the terminal."}), 403
        payload = request.get_json(silent=True) or {}
        raw = str(payload.get("command", "")).strip()
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            return jsonify({"error": f"Could not parse command: {exc}"}), 400

        if tokens and tokens[0] == "f1ml":
            tokens = tokens[1:]
        if not tokens:
            return jsonify({"error": "Empty command. Try `f1ml info`."}), 400
        if tokens[0] not in ALLOWED_SUBCOMMANDS:
            return jsonify({
                "error": f"'{tokens[0]}' is not an available command here. "
                         f"Allowed: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}"
            }), 400
        bad = [t for t in tokens if not _TOKEN_RE.match(t)]
        if bad:
            return jsonify({"error": f"Rejected argument(s): {' '.join(bad)}"}), 400

        def stream():
            proc = subprocess.Popen(
                [sys.executable, "-m", "f1_ml.cli", *tokens],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT, text=True, bufsize=1, env=_child_env(),
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                yield line
            proc.wait()
            yield f"\n[process exited with code {proc.returncode}]\n"

        return Response(stream(), mimetype="text/plain",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    return app
