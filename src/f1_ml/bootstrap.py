"""First-run self-heal.

A fresh clone ships the master result CSVs but not the generated feature table
or trained models (those are git-ignored). Rather than error with "no data",
the app rebuilds them from the committed CSVs on first launch — fully offline,
no FastF1 download needed. This is what makes `serve` "just work".
"""

from __future__ import annotations

import logging

from .config import FEATURES_FILE, METRICS_FILE, PROCESSED_DIR

log = logging.getLogger(__name__)


def status() -> dict:
    master = sorted(PROCESSED_DIR.glob("*_master_results.csv"))
    return {
        "has_master": bool(master),
        "has_features": FEATURES_FILE.exists(),
        "has_model": METRICS_FILE.exists(),
    }


def ensure_ready(verbose: bool = True) -> dict:
    """Build features and train a model if they're missing. Returns what it did."""
    did = []
    st = status()
    if not st["has_master"]:
        # nothing we can do offline; the fetch/merge commands need the network
        return {"ok": False, "reason": "no_master_data", "actions": did}

    if not st["has_features"]:
        if verbose:
            print("First run: building the feature table from the bundled data…")
        from .features import build_and_save

        build_and_save()
        did.append("features")

    if not st["has_model"]:
        if verbose:
            print("First run: training the podium model (a few seconds)…")
        from .features import load_features
        from .modeling import train_all

        train_all(load_features())
        did.append("model")

    return {"ok": True, "actions": did}
