"""Superseded by the f1_ml package — kept as a thin wrapper.
(Experiment C: improved features, 2024 season time split.)

Equivalent command:  f1ml train --model rf --cutoff 2024:14
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["train", "--model", "rf", "--cutoff", "2024:14"])
