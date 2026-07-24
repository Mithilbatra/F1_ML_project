"""Central paths and constants. Everything resolves from the project root,
so scripts work no matter which directory they are launched from."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_QUALY_DIR = RAW_DIR / "qualifying"
RAW_RACE_DIR = RAW_DIR / "race"
PROCESSED_DIR = DATA_DIR / "processed"

MODELS_DIR = PROJECT_ROOT / "models"
METRICS_FILE = MODELS_DIR / "metrics.json"

WEB_DIR = PROJECT_ROOT / "web"
# overridable so hosted deploys (e.g. Hugging Face, which runs as non-root) can
# point the cache at a writable location like /tmp
FASTF1_CACHE_DIR = Path(os.environ.get("F1ML_CACHE_DIR") or (PROJECT_ROOT / "fastf1_cache_dir"))

FEATURES_FILE = PROCESSED_DIR / "features.csv"

RANDOM_STATE = 42


def master_file(year: int) -> Path:
    return PROCESSED_DIR / f"{year}_master_results.csv"
