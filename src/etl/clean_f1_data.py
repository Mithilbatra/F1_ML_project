"""Superseded by the f1_ml package — kept as a thin wrapper.
(This script previously duplicated process_qualy_race_results.py.)

Equivalent command:  f1ml merge --year 2025
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["merge", "--year", "2025"])
