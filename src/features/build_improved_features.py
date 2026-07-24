"""Superseded by the f1_ml package — kept as a thin wrapper.

The improved feature set (plus fixes: per-driver rolling windows, no fake
P20 rows, corrected street-circuit list, qualifying gap-to-pole, team form)
now lives in src/f1_ml/features.py.

Equivalent command:  f1ml features
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["features"])
