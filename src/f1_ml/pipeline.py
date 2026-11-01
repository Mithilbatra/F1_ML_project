"""The data → model refresh pipeline, in one place.

`refresh()` pulls the latest results for the current season and every season on
disk, rebuilds the feature table, retrains, and refreshes the backtests. It's
shared by the `f1ml refresh` command
and the in-server auto-refresh scheduler, and it's idempotent: if there's no new
data — or no network — it simply rebuilds and retrains from what's on disk.

Fetching a live, in-progress season is safe: `data.fetch_year` skips sessions
that haven't run yet and ones already saved, so a refresh only pulls the newest
races (FastF1 allows 500 calls an hour).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def refresh(year: int | None = None, *, fetch: bool = True,
            backtest: bool = True, log=print) -> dict:
    """Run the full pipeline once and return a small report.

    year:     season to pull besides those on disk (default: the current calendar year).
    fetch:    set False to rebuild + retrain without touching the network.
    backtest: set False to skip the walk-forward backtests.
    log:      a callable for progress lines (print, or a logger method).
    """
    from . import data as datamod
    from .backtest import backtest_path, backtest_year
    from .features import build_and_save, feature_columns
    from .modeling import train_all

    year = year or datetime.now(timezone.utc).year
    fetched = 0

    if fetch:
        # finished seasons too: a fresh deploy starts from the data in git, which
        # can lack a season's last rounds (saved sessions cost no FastF1 calls)
        for y in sorted({*datamod.available_years(), year}):
            try:
                log(f"  Pulling {y} from FastF1…")
                fetched += len(datamod.fetch_year(y))
                datamod.merge_year(y)
            except Exception as exc:  # offline, rate-limited, or nothing raced yet
                log(f"  {y} fetch skipped ({exc}); using the data on disk.")
        log(f"  {fetched} session files fetched.")

    df = build_and_save()
    log(f"  Features rebuilt: {len(df)} rows, {len(feature_columns(df))} columns.")

    report = train_all(df)
    best = report["models"][report["best_model"]]["metrics"]
    log(f"  Retrained — best model {report['best_model']}, "
        f"top-3 hit rate {best['top3_hit_rate']:.1%}.")

    years = datamod.available_years()
    if backtest:
        # earlier seasons can't change while this one runs: skip any already done
        for y in years:
            if y == year or not backtest_path(y, report["best_model"]).exists():
                backtest_year(y, report["best_model"])
        log("  Backtests refreshed.")

    return {
        "year": year,
        "fetched": fetched,
        "rows": len(df),
        "years": years,
        "best_model": report["best_model"],
        "top3_hit_rate": best["top3_hit_rate"],
    }
