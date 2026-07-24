"""Superseded by the f1_ml package — kept as a thin wrapper.
(Experiment B: basic random forest, 2024 season time split. The old version
saved to a hardcoded path on another machine; the new pipeline saves to
models/ at the project root.)

Equivalent command:  f1ml train --model rf --cutoff 2024:16
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["train", "--model", "rf", "--cutoff", "2024:16"])
