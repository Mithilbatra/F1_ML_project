"""Superseded by the f1_ml package — kept as a thin wrapper.

Equivalent command:  f1ml evaluate
(or `f1ml train --model all` to retrain and compare models first)
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["evaluate"])
