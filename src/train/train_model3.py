"""Superseded by the f1_ml package — kept as a thin wrapper.
(Experiment D: tuned model, trained into the 2025 season.)

Equivalent command:  f1ml train --model rf --cutoff 2025:19 --tune
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["train", "--model", "rf", "--cutoff", "2025:19", "--tune"])
