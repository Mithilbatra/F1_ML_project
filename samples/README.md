# Sample track maps

Ready-to-upload maps for the Racing Line tab, in `track_maps/`:

**Real circuits** (traced from FastF1 lap telemetry — geographically accurate):

| File | Circuit | Real length | Model lap | Real pole |
|---|---|---|---|---|
| `monaco.png` | Circuit de Monaco | 3.337 km | ~1:01 | ~1:10 |
| `silverstone.png` | Silverstone | 5.891 km | ~1:25 | ~1:25 |
| `spa.png` | Spa-Francorchamps | 7.004 km | ~1:40 | ~1:44 |
| `monza.png` | Monza | 5.793 km | ~1:13 | ~1:19 |
| `zandvoort.png` | Zandvoort | 4.259 km | ~1:14 | ~1:09 |
| `hungaroring.png` | Hungaroring | 4.381 km | ~1:17 | ~1:15 |
| `red_bull_ring.png` | Red Bull Ring | 4.318 km | ~1:04 | ~1:03 |
| `interlagos.png` | Interlagos | 4.309 km | ~1:09 | ~1:07 |
| `suzuka.png` | Suzuka (figure-8) | 5.807 km | ~1:32 | ~1:28 |

The model lap is an idealised point-mass estimate (speed-dependent grip); it
lands within a few seconds of real qualifying pole on most circuits. Monaco
reads optimistic — its many second-gear corners get smoothed to larger radii on
the map — and banked Zandvoort reads slightly slow (no banking in the model).

**Synthetic circuits** (for quick testing):

| File | Character | Suggested length |
|---|---|---|
| `01_national_oval.png` | fast oval | 4.0 km |
| `02_grand_prix.png` | balanced GP circuit | 5.3 km |
| `03_flowing_circuit.png` | fast, flowing | 5.8 km |
| `04_twisty_street.png` | tight & twisty | 4.3 km |
| `05_technical_track.png` | technical | 4.7 km |

Regenerate the synthetic ones with `python samples/generate_samples.py`, and the
real ones with `python samples/build_real_tracks.py` (needs the `vision` extra
and, on first run, a network connection for the telemetry).

## What makes a map work

The analyzer needs the **tarmac drawn as one solid closed ribbon** (a thick
single-colour line counts) on a plain, contrasting background:

- **closed loop** — the track joins back to itself
- **solid ribbon**, not a thin double-outline (a filled band, or a thick line)
- **high contrast** — dark track on light background (or vice-versa)
- **top-down / schematic** — not a perspective photo
- **nothing over the track** — crop out DRS zones, sector markers, titles

## Finding real F1 track maps

Good sources (top-down schematics):

- **Wikipedia / Wikimedia Commons** — search e.g. "Circuit de Monaco",
  "Silverstone Circuit"; the layout diagrams are usually clean SVG/PNG.
- **Official F1 track maps** (formula1.com circuit pages) — the grey track
  ribbons are close to the ideal format.
- **racingcircuits.info**, **Tracktupedia** — schematic layouts.

### Prepping one before upload

1. Get a **top-down** layout (SVG → export PNG if needed).
2. Make sure the track is a **solid ribbon**. If it's a thin outline, fill it
   (any image editor: select the track path, thicken/fill it) or pick a version
   where the track is already a filled band.
3. **Crop out** text, DRS/sector annotations, and start/finish labels that sit
   on the track.
4. Boost contrast so the track is clearly darker (or lighter) than the
   background.
5. Upload, and enter the real track length (km) for a meaningful lap time.
