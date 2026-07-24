"""Generate clean schematic track maps in the exact format the racing-line
analyzer expects: the tarmac drawn as a solid closed ribbon (one colour) on a
plain background, top-down, no text over the track.

Run:  python samples/generate_samples.py
Outputs PNGs into samples/track_maps/.
"""

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parent / "track_maps"
OUT.mkdir(exist_ok=True)


def draw(name, harmonics, *, seed, size=1000, width=64, base=320,
         track=(38, 38, 44), bg=(245, 245, 245)):
    """Draw a closed track ribbon from a smooth Fourier loop."""
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    r = np.full_like(theta, base)
    for k, amp in harmonics:
        r += amp * np.cos(k * theta + rng.uniform(0, 2 * np.pi))
    # keep the loop comfortably inside the frame
    r *= (size * 0.42) / (r.max() + width)
    cx = cy = size / 2
    pts = np.column_stack([cx + r * np.cos(theta), cy + r * np.sin(theta)]).astype(np.int32)

    img = np.full((size, size, 3), bg, np.uint8)
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], True, track, width, cv2.LINE_AA)
    path = OUT / f"{name}.png"
    cv2.imwrite(str(path), img)
    return path


# Each entry: (filename, harmonics [(harmonic, amplitude)], suggested length km)
TRACKS = {
    "01_national_oval":    ([(2, 150)], 4.0),
    "02_grand_prix":       ([(2, 110), (3, 70), (5, 40)], 5.3),
    "03_flowing_circuit":  ([(2, 90), (3, 80), (4, 45), (6, 30)], 5.8),
    "04_twisty_street":    ([(2, 70), (3, 75), (5, 55), (7, 35)], 4.3),
    "05_technical_track":  ([(3, 90), (4, 70), (5, 50), (8, 30)], 4.7),
}

if __name__ == "__main__":
    for i, (name, (harm, km)) in enumerate(TRACKS.items()):
        p = draw(name, harm, seed=1000 + i)
        print(f"saved {p}  (suggested length ~{km} km)")
    print(f"\nUpload any of these in the Racing Line tab, or:")
    print(f"  f1ml raceline --image samples/track_maps/02_grand_prix.png --length-km 5.3")
