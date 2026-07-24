"""Superseded by the f1_ml package — kept as a thin wrapper.

Equivalent command:  f1ml fetch --year 2025 --session race
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["fetch", "--year", "2025", "--session", "race"])
