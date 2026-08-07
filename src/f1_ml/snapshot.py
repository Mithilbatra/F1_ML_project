"""Pre-render the app to a static site.

Calls the app's own API through Flask's test client and writes each response
to a JSON file mirroring its URL, then copies the frontend alongside. Served
with the bundled `static-shim.js`, the same UI reads these files when there's
no backend — so the core of the dashboard (standings, model, predictions, the
race-weekend hub) runs on plain static hosting like GitHub Pages.

Live-FastF1 features (telemetry duels, strategy, racing-line upload) need the
Python backend and degrade to a friendly notice on the static build.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .config import WEB_DIR

log = logging.getLogger(__name__)


def build(out_dir: Path) -> dict:
    from .data import available_years, load_master
    from .server import create_app

    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(WEB_DIR, out_dir)
    data_root = out_dir / "data" / "api"
    data_root.mkdir(parents=True, exist_ok=True)

    app = create_app()
    client = app.test_client()
    written, skipped = [], []

    def dump(api_path: str, out_name: str | None = None) -> dict | None:
        """GET an endpoint and write it to data/api/<path>.json."""
        try:
            r = client.get(api_path)
            if r.status_code != 200:
                skipped.append(f"{api_path} ({r.status_code})")
                return None
            rel = out_name or api_path.split("/api/", 1)[1].split("?")[0]
            fp = data_root / f"{rel}.json"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(r.data)
            written.append(rel)
            return r.get_json()
        except Exception as exc:  # a flaky telemetry pull shouldn't break the build
            skipped.append(f"{api_path} ({exc})")
            return None

    years = available_years()
    dump("/api/seasons")
    dump("/api/model")
    for year in years:
        dump(f"/api/summary/{year}")
        dump(f"/api/standings/{year}")
        dump(f"/api/races/{year}")
        dump(f"/api/backtest/{year}")
        master = load_master([year])
        rounds = sorted(master[master["RoundNumber"] > 0]["RoundNumber"].unique())
        for rnd in rounds:
            dump(f"/api/race/{year}/{int(rnd)}")
            dump(f"/api/predict/{year}/{int(rnd)}")
        # driver profiles for each driver this season
        for name in sorted(master["FullName"].dropna().unique()):
            if "Pre-Season" in str(name):
                continue
            from urllib.parse import quote
            dump(f"/api/driver?year={year}&name={quote(name)}",
                 out_name=f"driver/{year}/{name.replace('/', '_')}")

    # weekend hub (forecast + history + fantasy) and its circuit guide
    hub = dump("/api/hub")
    dump("/api/fantasy?budget=100", out_name="fantasy")
    if hub and hub.get("next_race"):
        from urllib.parse import quote
        dump(f"/api/circuit-guide?event={quote(hub['next_race']['event'])}",
             out_name="circuit-guide")

    # a flag file the frontend can read to know it's the static build
    (out_dir / "data" / "static.json").write_text(json.dumps({"static": True}))

    log.info("Snapshot: %d files written, %d skipped", len(written), len(skipped))
    return {"out_dir": str(out_dir), "written": len(written),
            "skipped": skipped, "years": years}
