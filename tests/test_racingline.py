"""Racing-line analyzer tests. Skipped unless the 'vision' extra is installed."""

import io
import subprocess
import sys

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from f1_ml import racingline as rl  # noqa: E402


def make_track(size=800, width=64, harmonics=((2, 90), (3, 55)), seed=1, base=260):
    """Draw a deterministic closed track band (tarmac as a dark loop),
    scaled to sit comfortably inside the frame (never touching the border)."""
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, 2 * np.pi, 1400, endpoint=False)
    r = np.full_like(theta, base)
    for k, amp in harmonics:
        r += amp * np.cos(k * theta + rng.uniform(0, 2 * np.pi))
    r *= (size * 0.42) / (r.max() + width)
    c = size / 2
    pts = np.column_stack([c + r * np.cos(theta), c + r * np.sin(theta)]).astype(np.int32)
    img = np.full((size, size, 3), 255, np.uint8)
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], True, (40, 40, 40), width, cv2.LINE_AA)
    return img


@pytest.fixture(scope="module")
def result():
    return rl.analyze(make_track(), track_length_km=5.0)


def test_extract_track_needs_a_loop():
    blank = np.full((300, 300, 3), 255, np.uint8)
    with pytest.raises(ValueError):
        rl.extract_track(blank)


def test_analyze_shapes(result):
    assert len(result["racing_line"]) == rl.N_POINTS
    assert len(result["speed_kmh"]) == len(result["racing_line"])
    assert len(result["outer"]) == rl.N_POINTS
    assert len(result["centerline"]) == rl.N_POINTS


def test_racing_line_stays_inside_band(result):
    outer = np.array(result["outer"], np.float32).reshape(-1, 1, 2)
    inner = np.array(result["inner"], np.float32).reshape(-1, 1, 2)
    inside = 0
    for p in result["racing_line"]:
        pt = (float(p[0]), float(p[1]))
        if cv2.pointPolygonTest(outer, pt, False) >= 0 and \
           cv2.pointPolygonTest(inner, pt, False) < 0:
            inside += 1
    # allow a couple of points to sit on the smoothed boundary
    assert inside >= 0.95 * len(result["racing_line"])


def test_corners_and_lap_time(result):
    assert result["n_corners"] >= 1
    assert result["lap_time_s"] > 0 and np.isfinite(result["lap_time_s"])
    assert ":" in result["lap_time_str"]
    assert result["v_max_kmh"] >= result["v_min_kmh"] > 0


def test_every_corner_has_three_variants(result):
    assert len(result["corner_variants"]) == result["n_corners"]
    for v in result["corner_variants"]:
        assert set(v["lines"]) == {"early", "optimal", "late"}
        for line in v["lines"].values():
            assert len(line) == rl.N_POINTS


def test_apex_variants_differ_from_optimal(result):
    v = result["corner_variants"][0]
    seg = v["segment_index"]
    opt = np.array(v["lines"]["optimal"])[seg]
    for k in ("early", "late"):
        alt = np.array(v["lines"][k])[seg]
        assert np.linalg.norm(alt - opt, axis=1).max() > 5  # visibly distinct


def _loop_len(pts):
    a = np.asarray(pts)
    return float(np.sum(np.linalg.norm(np.roll(a, -1, 0) - a, axis=1)))


def test_racing_line_tracks_the_ribbon(result):
    """Regression: the line must follow the tarmac, not loop around the outside
    of the whole map (which happened when the background was mistaken for the
    track). Its length should be close to the centreline's."""
    ratio = _loop_len(result["racing_line"]) / _loop_len(result["centerline"])
    assert 0.75 < ratio < 1.25


def test_concave_star_track_is_followed():
    """A star-shaped ribbon with concavities tighter than its width — the case
    the outer/inner-pairing method got wrong."""
    star = make_track(harmonics=((3, 90), (5, 60)), seed=7, width=48)
    res = rl.analyze(star, track_length_km=4.5)
    ratio = _loop_len(res["racing_line"]) / _loop_len(res["centerline"])
    assert 0.75 < ratio < 1.25
    assert res["n_corners"] >= 3


def test_track_length_assumed_flag():
    r = rl.analyze(make_track(), track_length_km=None)
    assert r["track_length_assumed"] is True
    r2 = rl.analyze(make_track(), track_length_km=4.2)
    assert r2["track_length_assumed"] is False
    assert r2["track_length_km"] == 4.2


def test_format_lap_time():
    assert rl.format_lap_time(83.456) == "1:23.456"
    assert rl.format_lap_time(9.1) == "0:09.100"


def test_speed_dependent_grip_slows_tight_corners():
    """Downforce grip grows with speed, so a tight corner must be much slower
    than a fast one — a constant-grip model would not enforce this."""
    car = rl.DEFAULT_CAR
    v_tight = rl._corner_limited_speed(np.array([1 / 15.0]), car)[0]   # 15 m radius
    v_fast = rl._corner_limited_speed(np.array([1 / 300.0]), car)[0]   # 300 m radius
    assert v_tight < v_fast
    assert v_tight * 3.6 < 110      # a 15 m hairpin: well under 110 km/h
    assert v_fast >= car["v_max"] - 1  # a 300 m sweeper: near top speed


# ------------------------------------------------------------ circuit guide

def test_circuit_guide_takes_newest_season_with_this_exact_race(monkeypatch):
    import pandas as pd
    from types import SimpleNamespace

    from f1_ml import data, telemetry, weekend

    tried = []

    def fake_load_session(year, gp, sc, telemetry=True):
        tried.append(year)
        if year == 2026:
            raise ValueError("not raced here yet")
        name = "Belgian Grand Prix" if year == 2025 else gp  # 2025: a fuzzy mismatch
        return SimpleNamespace(event={"EventName": name},
                               results=pd.DataFrame({"Abbreviation": ["VER"]}))

    lap = pd.DataFrame({"Distance": [0.0, 4300.0], "X": [0, 1], "Y": [0, 1]})
    monkeypatch.setattr(data, "available_years", lambda: [2024, 2025, 2026])
    monkeypatch.setattr(telemetry, "load_session", fake_load_session)
    monkeypatch.setattr(telemetry, "fastest_lap_frame", lambda s, d: (None, lap))
    monkeypatch.setattr(rl, "analyze_from_xy", lambda x, y, track_length_km: {})

    guide = weekend.circuit_guide("Dutch Grand Prix")
    assert tried == [2026, 2025, 2024]
    assert guide["source_year"] == 2024


# ------------------------------------------------------------ upload limits

def test_decode_rejects_oversized_map():
    _, png = cv2.imencode(".png", np.zeros((10, rl.MAX_UPLOAD_SIDE + 1, 3), np.uint8))
    with pytest.raises(ValueError, match="longest side"):
        rl.decode_image(png.tobytes())


def test_decompression_bomb_refused_without_allocating(tmp_path):
    # A fresh process: OpenCV reads its pixel cap only once, when it loads.
    Image = pytest.importorskip("PIL.Image")
    bomb = tmp_path / "bomb.png"
    Image.new("1", (20000, 20000)).save(bomb)  # tiny file, ~1.2 GB once decoded
    # measure what the decode adds on top of the imports: the imports alone
    # differ a lot between platforms (~650 MB peak on Linux CI)
    code = ("import resource, sys\n"
            "from f1_ml import racingline as rl\n"
            "peak = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n"
            "before = peak()\n"
            "try:\n"
            "    rl.decode_image(open(sys.argv[1], 'rb').read())\n"
            "except ValueError:\n"
            "    print(peak() - before)\n")
    out = subprocess.run([sys.executable, "-c", code, str(bomb)],
                         capture_output=True, text=True, check=True)
    added_mb = int(out.stdout) / (1024 * 1024 if sys.platform == "darwin" else 1024)
    assert added_mb < 300  # decoding it would add 1200+ MB


def test_upload_over_limit_gets_json_413():
    from f1_ml.server import create_app

    big = (io.BytesIO(b"0" * (9 * 1024 * 1024)), "big.png")
    r = create_app().test_client().post("/api/racingline", data={"image": big})
    assert r.status_code == 413
    assert "too large" in r.get_json()["error"]
