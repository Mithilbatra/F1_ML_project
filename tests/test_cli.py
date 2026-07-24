"""Smoke tests: the CLI parses and dispatches without touching the network."""

import pytest

from f1_ml.cli import build_parser


def test_all_subcommands_parse():
    parser = build_parser()
    for argv in (
        ["info"],
        ["fetch", "--year", "2025"],
        ["merge", "--year", "2025"],
        ["features"],
        ["train", "--model", "rf", "--cutoff", "2025:18", "--test-last", "4"],
        ["train", "--tune"],
        ["evaluate", "--model", "gbdt"],
        ["predict", "--year", "2025", "--round", "23"],
        ["backtest", "--year", "2025"],
        ["standings", "--year", "2024"],
        ["weekend", "--top", "8"],
        ["fantasy", "--budget", "100"],
        ["h2h", "--year", "2024", "--round", "8", "--d1", "VER", "--d2", "LEC"],
        ["raceline", "--image", "track.png", "--length-km", "5.3"],
        ["serve", "--port", "5000"],
    ):
        args = parser.parse_args(argv)
        assert callable(args.func)


def test_rejects_unknown_model():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["train", "--model", "xgboost"])


def test_rejects_missing_required_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["predict", "--year", "2025"])  # no --round
