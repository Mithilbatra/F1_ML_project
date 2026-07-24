"""Launcher for the Pit Wall dashboard that works without the .venv shim.

Some sandboxed runners (e.g. IDE preview panels) refuse to start executables
that live inside the hidden .venv directory. This script can be run with any
Python 3.12 interpreter directly; it wires the project's src/ and the venv's
site-packages onto sys.path itself.

Normal usage remains:  f1ml serve
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".venv" / "lib" / "python3.12" / "site-packages"))
sys.path.insert(0, str(ROOT / "src"))

from f1_ml.server import create_app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 5173))
    app = create_app()
    print(f"F1 ML dashboard -> http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port)
