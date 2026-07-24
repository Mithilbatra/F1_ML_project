"""Superseded by the f1_ml package — kept as a thin wrapper.

Equivalent command:  f1ml merge --year 2025
"""

from f1_ml.cli import main

if __name__ == "__main__":
    main(["merge", "--year", "2025"])
