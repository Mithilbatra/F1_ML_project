"""The data → model refresh pipeline, in one place.

`refresh()` pulls the latest results for a season, rebuilds the feature table,
retrains, and refreshes the backtests. It's shared by the `f1ml refresh` command
and the in-server auto-refresh scheduler, and it's idempotent: if there's no new
data — or no network — it simply rebuilds and retrains from what's on disk.

Fetching a live, in-progress season is safe: `data.fetch_year` skips rounds that
haven't happened yet, so mid-2026 this only pulls the races that have run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def refresh(year: int | None = None, *, fetch: bool = True,
            backtest: bool = True, log=print) -> dict:
    """Run the full pipeline once and return a small report.

    year:     season to pull (default: the current calendar year).
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
        try:
            log(f"  Pulling {year} from FastF1…")
            written = datamod.fetch_year(year)
            fetched = len(written)
            log(f"  {fetched} session files fetched.")
            datamod.merge_year(year)
        except Exception as exc:  # offline, rate-limited, or nothing raced yet
            log(f"  Fetch skipped ({exc}); rebuilding from the data on disk.")

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
