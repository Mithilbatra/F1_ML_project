"""Build accurate track maps for real circuits from FastF1 lap telemetry.

A fastest-lap's X/Y telemetry traces the real racing surface, so drawing it as
a ribbon gives a geographically faithful schematic in exactly the format the
racing-line analyzer wants.

The ribbon width is set in real metres (via the telemetry scale, which is in
1/10 m) and the canvas is large, so even a hairpin's in/out lanes stay
separated by open track — otherwise they merge and the analyzer cuts across
the corner instead of going around it.

Run:  python samples/build_real_tracks.py
"""

from pathlib import Path

import cv2
import fastf1
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples" / "track_maps"
OUT.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(ROOT / "fastf1_cache_dir"))

SIZE = 2200
TRACK_WIDTH_M = 9.0   # narrow enough to keep hairpin in/out lanes separated

# (filename, year, grand prix, real length km)
CIRCUITS = [
    ("monaco",         2024, "Monaco",          3.337),
    ("silverstone",    2024, "British",         5.891),
    ("spa",            2024, "Belgian",         7.004),
    ("monza",          2024, "Italian",         5.793),
    ("zandvoort",      2024, "Dutch",           4.259),
    ("hungaroring",    2024, "Hungarian",       4.381),
    ("red_bull_ring",  2024, "Austrian",        4.318),
    ("interlagos",     2024, "São Paulo",       4.309),
    ("suzuka",         2024, "Japanese",        5.807),  # figure-8 stress test
]


def build(name, year, gp, size=SIZE):
    session = fastf1.get_session(year, gp, "Q")
    session.load(telemetry=True, weather=False, messages=False)
    tel = session.laps.pick_fastest().get_telemetry()
    x = tel["X"].to_numpy(dtype=float)
    y = tel["Y"].to_numpy(dtype=float)

    # normalise into the frame (flip Y so north is up), keep aspect ratio
    x -= x.min(); y -= y.min()
    span = max(x.max(), y.max())            # telemetry units are 1/10 m
    scale = (size * 0.86) / span
    x = x * scale + (size - x.max() * scale) / 2
    y = (y.max() - y) * scale + (size - y.max() * scale) / 2

    width_px = max(3, int(TRACK_WIDTH_M * 10 * scale))  # metres -> 1/10 m -> px
    pts = np.column_stack([x, y]).astype(np.int32)
    img = np.full((size, size, 3), 245, np.uint8)
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], True, (38, 38, 44),
                  width_px, cv2.LINE_AA)
    path = OUT / f"{name}.png"
    cv2.imwrite(str(path), img)
    return path


if __name__ == "__main__":
    for name, year, gp, km in CIRCUITS:
        try:
            path = build(name, year, gp)
            print(f"saved {path.name}  (real length {km} km)")
        except Exception as exc:
            print(f"[{name}] failed: {exc}")
