"""Command-line interface. Every pipeline step is a subcommand:

    f1ml info                          dataset overview
    f1ml fetch --year 2025             download raw data via FastF1
    f1ml merge --year 2025             raw CSVs -> master results file
    f1ml features                      master files -> model-ready features
    f1ml train [--model all] [--tune]  train + evaluate on held-out races
    f1ml evaluate [--model rf]         re-print metrics for a saved model
    f1ml predict --year 2025 --round 23  podium picks for one race
    f1ml standings --year 2025         championship standings
    f1ml serve                         launch the web dashboard
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd


def _print_header(title: str) -> None:
    print(f"\n{'=' * 58}\n  {title}\n{'=' * 58}")


def _fmt_metrics(m: dict) -> str:
    lines = [
        f"  Test races          : {m['n_test_races']}  ({m['n_test_rows']} entries)",
        f"  Top-3 hit rate      : {m['top3_hit_rate']:.1%}   (grid baseline: {m['baseline_top3_hit_rate']:.1%})",
        f"  PR-AUC              : {m['pr_auc']:.3f}",
        f"  ROC-AUC             : {m['roc_auc']:.3f}",
        f"  Podium precision    : {m['precision_podium']:.3f}",
        f"  Podium recall       : {m['recall_podium']:.3f}",
        f"  Podium F1           : {m['f1_podium']:.3f}",
        f"  Brier score         : {m['brier']:.4f}",
        f"  Accuracy            : {m['accuracy']:.3f}  (naive all-negative would score ~0.85)",
    ]
    return "\n".join(lines)


def _print_races(races: list[dict]) -> None:
    print("\n  Race-by-race picks (model top 3 vs actual podium):")
    for r in races:
        marks = []
        for name in r["picks"]:
            marks.append(f"{name} {'[HIT]' if name in r['actual'] else '[miss]'}")
        print(f"   R{r['round']:>2} {r['event'][:28]:<28} {r['hits']}/3  " + " | ".join(marks))


# ------------------------------------------------------------- subcommands

def cmd_info(args) -> None:
    from .data import available_years, load_master

    years = available_years()
    if not years:
        print("No data yet. Run `f1ml fetch --year 2025` then `f1ml merge --year 2025`.")
        return
    _print_header("F1 ML — dataset overview")
    for year in years:
        df = load_master([year])
        real = df[df["RoundNumber"] > 0]
        print(
            f"  {year}: {real['RoundNumber'].nunique():>2} rounds, "
            f"{real['FullName'].nunique():>2} drivers, {len(real):>3} entries"
        )
    from .config import FEATURES_FILE, METRICS_FILE

    print(f"\n  features file : {'built' if FEATURES_FILE.exists() else 'missing (run `f1ml features`)'}")
    print(f"  trained model : {'yes' if METRICS_FILE.exists() else 'no (run `f1ml train`)'}")


def cmd_fetch(args) -> None:
    from .data import fetch_year

    _print_header(f"Fetching {args.session} data for {args.year} (FastF1)")
    written = fetch_year(args.year, args.session)
    print(f"  Saved {len(written)} files.")


def cmd_merge(args) -> None:
    from .data import merge_year

    _print_header(f"Merging qualifying + race results for {args.year}")
    master = merge_year(args.year)
    print(f"  {len(master)} rows -> data/processed/{args.year}_master_results.csv")


def cmd_features(args) -> None:
    from .config import FEATURES_FILE
    from .features import build_and_save, feature_columns

    _print_header("Building features")
    df = build_and_save(args.years)
    print(f"  {len(df)} rows, {len(feature_columns(df))} model features")
    print(f"  -> {FEATURES_FILE}")


def cmd_train(args) -> None:
    from .features import load_features
    from .modeling import train_all, train_and_evaluate

    cutoff = _parse_cutoff(args.cutoff)
    df = load_features()
    if args.model == "all":
        _print_header("Training rf + gbdt" + (" (tuned)" if args.tune else ""))
        report = train_all(df, cutoff, args.test_last, args.tune)
        for name, res in report["models"].items():
            print(f"\n  --- {name} ---")
            print(_fmt_metrics(res["metrics"]))
        print(f"\n  Best model by top-3 hit rate: {report['best_model']}")
        print("  Full comparison written to models/metrics.json")
    else:
        _print_header(f"Training {args.model}" + (" (tuned)" if args.tune else ""))
        res = train_and_evaluate(df, args.model, cutoff, args.test_last, args.tune)
        print(f"  Train rows: {res['train_rows']}  Cutoff: {res['cutoff'][0]} round {res['cutoff'][1]}")
        if res["best_params"]:
            print(f"  Best params: {res['best_params']}")
        print(_fmt_metrics(res["metrics"]))
        _print_races(res["metrics"]["races"])
        print(f"\n  Saved to {res['artifact_path']}")


def cmd_evaluate(args) -> None:
    from .config import METRICS_FILE

    if not METRICS_FILE.exists():
        print("No metrics yet — run `f1ml train` first.")
        sys.exit(1)
    report = json.loads(METRICS_FILE.read_text())
    _print_header("Saved model comparison")
    for name, res in report["models"].items():
        star = " *best*" if name == report["best_model"] else ""
        print(f"\n  --- {name}{star} ---")
        print(_fmt_metrics(res["metrics"]))
    name = args.model or report["best_model"]
    _print_races(report["models"][name]["metrics"]["races"])


def cmd_predict(args) -> None:
    from .predict import predict_round

    _print_header(f"Podium prediction — {args.year} round {args.round}")
    out = predict_round(args.year, args.round, args.model)
    event = out["EventName"].iloc[0]
    print(f"  {event}\n")
    view = out[["FullName", "TeamName", "QualyPos", "prob", "RacePos"]].copy()
    view["prob"] = (view["prob"] * 100).map("{:.1f}%".format)
    view.columns = ["Driver", "Team", "Qualy", "Podium prob", "Actual finish"]
    print(view.head(10).to_string(index=False))

    picks = out.head(3)["FullName"].tolist()
    actual = out[out["RacePos"] <= 3].sort_values("RacePos")["FullName"].tolist()
    print(f"\n  Model podium : {', '.join(picks)}")
    if actual:
        hits = len(set(picks) & set(actual))
        print(f"  Actual podium: {', '.join(actual)}   ({hits}/3 correct)")


def cmd_backtest(args) -> None:
    from .backtest import backtest_year

    _print_header(f"Walk-forward backtest — {args.year} ({args.model})")
    print("  Retraining before every race; this takes ~30s...\n")
    report = backtest_year(args.year, args.model)
    for r in report["races"]:
        bar = "#" * r["model_hits"] + "." * (3 - r["model_hits"])
        print(f"   R{r['round']:>2} {r['event'][:30]:<30} model {r['model_hits']}/3 [{bar}]  grid {r['baseline_hits']}/3")
    print(f"\n  Season top-3 hit rate: model {report['model_hit_rate']:.1%}  "
          f"vs grid baseline {report['baseline_hit_rate']:.1%} over {report['n_races']} races")


def cmd_standings(args) -> None:
    from .data import compute_standings, load_master

    _print_header(f"{args.year} championship standings")
    standings = compute_standings(load_master([args.year]), args.year)
    print("\n  DRIVERS")
    print(standings["drivers"].to_string(index=False))
    print("\n  CONSTRUCTORS")
    print(standings["constructors"].to_string(index=False))


def cmd_raceline(args) -> None:
    try:
        from . import racingline as rl
    except ImportError:
        print("The racing-line analyzer needs the 'vision' extra:\n"
              "  uv sync --extra vision")
        sys.exit(1)

    _print_header("Racing-line analysis")
    image = rl.load_image(args.image)
    result = rl.analyze(image, track_length_km=args.length_km)

    note = " (assumed — pass --length-km)" if result["track_length_assumed"] else ""
    print(f"  Track length      : {result['track_length_km']} km{note}")
    print(f"  Corners detected  : {result['n_corners']}")
    print(f"  Idealised lap time: {result['lap_time_str']}  "
          f"(point-mass estimate)")
    print(f"  Top speed         : {result['v_max_kmh']:.0f} km/h")
    print(f"  Slowest corner    : {result['v_min_kmh']:.0f} km/h\n")

    print("  Corner  Radius(m)  Apex speed")
    speed = result["speed_kmh"]
    for c in result["corners"]:
        print(f"    {c['number']:>2}    {c['radius_m']:>8.0f}   {speed[c['index']]:>6.0f} km/h")

    out = args.out or (args.image.rsplit(".", 1)[0] + "_racingline.png")
    rl.cv2.imwrite(out, rl.render(image, result))
    print(f"\n  Annotated map saved to {out}")
    print("  Racing line coloured green (slow) → red (fast); apexes numbered.")


def cmd_weekend(args) -> None:
    from . import weekend as wk

    _print_header("Race weekend")
    nxt = wk.next_race()
    if nxt:
        print(f"  Next: {nxt['event']} (Round {nxt['round']}, {nxt['location']}, {nxt['country']})")
        print(f"  Race: {nxt['race_utc']}")
        for s in nxt["sessions"]:
            print(f"    {s['name']:<16} {s['utc']}")
    else:
        print("  No upcoming race found in the schedule.")

    fc = wk.form_forecast(top=args.top)
    print(f"\n  Podium projection (form-only, based on {fc['based_on_season']}):")
    for i, r in enumerate(fc["projection"], 1):
        print(f"   {i:>2}. {r['driver']:<22} {r['team']:<16} {r['prob'] * 100:4.0f}%  "
              f"(avg finish {r['avg_finish']}, {r['season_points']} pts)")


def cmd_fantasy(args) -> None:
    from . import fantasy as fan

    _print_header(f"Fantasy optimiser — ${args.budget}M budget")
    team = fan.optimise(args.budget)
    if "error" in team:
        print("  " + team["error"])
        return
    print(f"  Cost ${team['cost']}M / ${team['budget']}M · projected {team['projected_points']} pts\n")
    print("  DRIVERS")
    for d in team["drivers"]:
        cap = "  (CAPTAIN 2x)" if d["captain"] else ""
        print(f"    {d['name']:<22} {d['team']:<16} ${d['price']:>5}M  {d['proj']:>5} pts{cap}")
    print("  CONSTRUCTORS")
    for c in team["constructors"]:
        print(f"    {c['name']:<22} {'':<16} ${c['price']:>5}M  {c['proj']:>5} pts")


def cmd_h2h(args) -> None:
    from . import telemetry as tel

    _print_header(f"Telemetry — {args.d1} vs {args.d2}")
    h = tel.head_to_head(args.year, str(args.round), args.session, args.d1, args.d2)
    print(f"  {h['event']} · {h['session']}\n")
    for d in (h["d1"], h["d2"]):
        lap = d["lap_time"]
        lap_str = f"{int(lap // 60)}:{lap % 60:06.3f}" if lap else "—"
        print(f"    {d['abbr']:<4} {d['team']:<16} {lap_str}  "
              f"S1 {d['sectors'][0]}  S2 {d['sectors'][1]}  S3 {d['sectors'][2]}")
    faster = h["track"]["faster"]
    print(f"\n  Track dominance: {h['d1']['abbr']} faster at {faster.count(1)}/{len(faster)} points, "
          f"{h['d2']['abbr']} at {faster.count(2)}/{len(faster)}")


def cmd_setup(args) -> None:
    from . import bootstrap

    _print_header("Setup")
    result = bootstrap.ensure_ready()
    if not result["ok"]:
        print("  No bundled data found. Run `f1ml fetch --year 2025` then "
              "`f1ml merge --year 2025` (needs internet).")
        sys.exit(1)
    if result["actions"]:
        print(f"  Built: {', '.join(result['actions'])}. Ready.")
    else:
        print("  Everything already in place. Ready.")


def cmd_serve(args) -> None:
    from . import bootstrap
    from .server import create_app

    # make a fresh clone "just work": build features + train if missing
    ready = bootstrap.ensure_ready()
    if not ready["ok"]:
        print("Warning: no data found — the dashboard will have limited content.\n"
              "Run `f1ml fetch --year 2025` and `f1ml merge --year 2025` first.")

    app = create_app()
    print(f"\nPit Wall dashboard -> http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
    app.run(host=args.host, port=args.port, debug=args.debug)


# ------------------------------------------------------------------ parser

def _parse_cutoff(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    try:
        year, rnd = raw.split(":")
        return int(year), int(rnd)
    except ValueError:
        raise SystemExit(f"Bad --cutoff '{raw}'; expected YEAR:ROUND, e.g. 2025:18")


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="f1ml", description="F1 podium prediction pipeline"
    )
    parser.add_argument("--version", action="version",
                        version=f"f1ml {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="dataset and model status").set_defaults(func=cmd_info)

    sub.add_parser(
        "setup", help="first-run build: features + model from bundled data"
    ).set_defaults(func=cmd_setup)

    p = sub.add_parser("fetch", help="download a season from FastF1")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--session", choices=["both", "race", "qualifying"], default="both")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("merge", help="merge raw CSVs into a master file")
    p.add_argument("--year", type=int, required=True)
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("features", help="build the model-ready feature table")
    p.add_argument("--years", type=int, nargs="*", default=None)
    p.set_defaults(func=cmd_features)

    p = sub.add_parser("train", help="train and evaluate on held-out races")
    p.add_argument("--model", choices=["rf", "gbdt", "all"], default="all")
    p.add_argument("--cutoff", help="train through YEAR:ROUND (e.g. 2025:18)")
    p.add_argument("--test-last", type=int, default=6,
                   help="hold out the last N races (default 6)")
    p.add_argument("--tune", action="store_true", help="grid search (slower)")
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("evaluate", help="show saved model metrics")
    p.add_argument("--model", choices=["rf", "gbdt"], default=None)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("predict", help="podium picks for one race")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--model", choices=["rf", "gbdt"], default="rf")
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("backtest", help="walk-forward backtest over a season")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--model", choices=["rf", "gbdt"], default="rf")
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("standings", help="championship standings for a season")
    p.add_argument("--year", type=int, required=True)
    p.set_defaults(func=cmd_standings)

    p = sub.add_parser("raceline", help="racing line from a track map image")
    p.add_argument("--image", required=True, help="path to a schematic track map")
    p.add_argument("--length-km", type=float, default=None,
                   help="real track length in km (for the lap-time estimate)")
    p.add_argument("--out", default=None, help="output PNG path")
    p.set_defaults(func=cmd_raceline)

    p = sub.add_parser("weekend", help="next race + form-based podium projection")
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(func=cmd_weekend)

    p = sub.add_parser("fantasy", help="optimise an F1 Fantasy team")
    p.add_argument("--budget", type=float, default=100.0)
    p.set_defaults(func=cmd_fantasy)

    p = sub.add_parser("h2h", help="telemetry head-to-head between two drivers")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--session", default="Q")
    p.add_argument("--d1", required=True, help="driver 1 abbreviation, e.g. VER")
    p.add_argument("--d2", required=True, help="driver 2 abbreviation, e.g. LEC")
    p.set_defaults(func=cmd_h2h)

    p = sub.add_parser("serve", help="run the web dashboard")
    import os
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5173)))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                   help="bind address (use 0.0.0.0 inside Docker)")
    p.add_argument("--debug", action="store_true")
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pd.set_option("display.width", 120)
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
