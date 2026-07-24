"""Racing-line analyzer.

Given a schematic track map (the tarmac drawn as a closed band), this:

1. segments the track and extracts the outer + inner edges,
2. builds a centreline with local track width,
3. solves for the minimum-curvature racing line (a bounded linear
   least-squares problem — a convex, globally-optimal geometric line),
4. finds the corners and, per corner, offers early- / late- / optimal-apex
   variants,
5. estimates an idealised lap time with a quasi-steady-state point-mass model.

The minimum-curvature line is the classic geometric racing line. It is not a
full minimum-lap-time trajectory (that needs a vehicle/aero model), but on a
clean map it is at most slightly sub-optimal and matches what a driver would
call "the line".

OpenCV and SciPy are optional; import this module only when the `vision`
extra is installed (`uv sync --extra vision`).
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover - guarded at call sites
    raise ImportError(
        "The racing-line analyzer needs the 'vision' extra. "
        "Install it with:  uv sync --extra vision"
    ) from exc

from scipy.ndimage import gaussian_filter1d
from scipy.optimize import lsq_linear
from scipy.signal import find_peaks
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize

# Idealised F1 car for the lap-time model. The key to realism is that grip is
# *speed-dependent*: at low speed only mechanical (tyre) grip is available, but
# downforce adds lateral grip that grows with v^2. A constant-grip model made
# slow corners (Monaco) far too fast. See estimate_lap_time.
G = 9.81
DEFAULT_CAR = {
    "mu": 1.55,            # mechanical grip -> ~1.55 g lateral at low speed
    "downforce_k": 4.2e-4,  # aero: lateral grip gains g * k * v^2
    "acc_accel": 1.05 * G,  # forward acceleration (traction/power limited)
    "brk_accel": 4.6 * G,   # braking
    "v_max": 91.0,          # top speed ~328 km/h
}

N_POINTS = 500          # resampled samples around the loop
WALL_MARGIN_FRAC = 0.12  # keep the line this fraction of half-width off the wall


# --------------------------------------------------------------- geometry

def _resample_closed(points: np.ndarray, n: int) -> np.ndarray:
    """Resample a closed polyline to n points evenly spaced by arc length."""
    pts = np.asarray(points, dtype=float)
    loop = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(loop, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    total = s[-1]
    targets = np.linspace(0, total, n, endpoint=False)
    x = np.interp(targets, s, loop[:, 0])
    y = np.interp(targets, s, loop[:, 1])
    return np.column_stack([x, y])


def _smooth_closed(arr: np.ndarray, sigma: float) -> np.ndarray:
    """Periodic Gaussian smoothing along axis 0."""
    return gaussian_filter1d(arr, sigma=sigma, axis=0, mode="wrap")


def _tangents_normals(centerline: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unit tangents and left-hand unit normals for a closed centreline."""
    nxt = np.roll(centerline, -1, axis=0)
    prv = np.roll(centerline, 1, axis=0)
    tangent = nxt - prv
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True) + 1e-9
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    return tangent, normal


def curvature(points: np.ndarray) -> np.ndarray:
    """Discrete curvature (1/unit) of a closed, uniformly-sampled polyline."""
    d1 = (np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)) / 2.0
    d2 = np.roll(points, -1, axis=0) - 2 * points + np.roll(points, 1, axis=0)
    cross = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    denom = np.power(np.linalg.norm(d1, axis=1), 3) + 1e-9
    return cross / denom


# --------------------------------------------------------- track extraction

def _binarize(gray: np.ndarray) -> np.ndarray:
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return mask


def extract_track(image: np.ndarray) -> dict:
    """Find the track band and return its outer and inner edge contours.

    Tries both foreground polarities and keeps whichever yields a large
    contour that contains a hole (i.e. a closed band, not a filled blob).
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    base = _binarize(gray)

    best = None
    for mask in (base, cv2.bitwise_not(base)):
        # close small gaps so an outline drawing becomes a solid band
        closed = cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2
        )
        contours, hierarchy = cv2.findContours(
            closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if hierarchy is None:
            continue
        hierarchy = hierarchy[0]
        h, w = gray.shape
        for i, cnt in enumerate(contours):
            if hierarchy[i][3] != -1:  # not a top-level (external) contour
                continue
            # An external contour hugging the image edge is the background, not
            # the track — that mistake makes the line loop around the outside.
            pts = cnt.reshape(-1, 2)
            if (pts[:, 0].min() <= 1 or pts[:, 1].min() <= 1
                    or pts[:, 0].max() >= w - 2 or pts[:, 1].max() >= h - 2):
                continue
            # child holes of this external contour
            holes = [j for j in range(len(contours)) if hierarchy[j][3] == i]
            if not holes:
                continue
            inner_idx = max(holes, key=lambda j: cv2.contourArea(contours[j]))
            outer_area = cv2.contourArea(cnt)
            inner_area = cv2.contourArea(contours[inner_idx])
            # a real track: sizeable band, hole not filling the whole thing
            if outer_area < 0.02 * gray.size or inner_area < 0.2 * outer_area:
                continue
            # the tarmac band itself must be a believable ribbon, not a huge fill
            band_frac = (outer_area - inner_area) / gray.size
            if band_frac > 0.6:
                continue
            score = outer_area
            if best is None or score > best["score"]:
                # keep every meaningful hole: a self-touching circuit (Monaco)
                # can pinch its infield into several holes, and leaving any of
                # them filled turns that part of the track into a solid blob.
                hole_cnts = [contours[j].reshape(-1, 2).astype(float) for j in holes
                             if cv2.contourArea(contours[j]) > 0.005 * gray.size]
                best = {
                    "score": score,
                    "outer": cnt.reshape(-1, 2).astype(float),
                    "inner": contours[inner_idx].reshape(-1, 2).astype(float),
                    "holes": hole_cnts,
                }
    if best is None:
        raise ValueError(
            "Could not find a closed track band in the image. Expected a track "
            "drawn as a loop with an inside and an outside (a filled band or a "
            "clear outline)."
        )
    # a clean filled band = fill the outer contour, punch out every infield hole
    mask = np.zeros(gray.shape, np.uint8)
    cv2.drawContours(mask, [best["outer"].astype(np.int32)], -1, 255, cv2.FILLED)
    for hole in best["holes"]:
        cv2.drawContours(mask, [hole.astype(np.int32)], -1, 0, cv2.FILLED)
    return {"outer": best["outer"], "inner": best["inner"],
            "holes": best["holes"], "mask": mask, "size": gray.shape}


# 8-neighbour offsets for skeleton spur-pruning
_NBR8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _skeleton_loop(mask: np.ndarray, ring_contour: np.ndarray) -> np.ndarray:
    """Order the ribbon's medial axis into a closed loop of (x, y).

    The skeleton runs down the middle of the tarmac even through hairpins, but
    where a circuit's roads nearly touch (Monaco) the skeleton develops
    junctions that a naive graph-walk trips over. Instead we order the skeleton
    pixels by projecting each onto the outer boundary contour — which stays a
    single simple loop around the whole circuit even when the infield hole gets
    pinched apart — so the ordering is junction-proof.
    """
    skel = skeletonize(mask > 0)
    ys, xs = np.nonzero(skel)
    pixels = set(zip(map(int, ys), map(int, xs)))
    if len(pixels) < 8:
        raise ValueError("Track skeleton too small to trace.")

    def neighbours(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in _NBR8 if (p[0] + dy, p[1] + dx) in pixels]

    # drop spur pixels (dead-end branches) so only the loop + any short bridges
    # between adjacent roads remain
    changed = True
    while changed:
        changed = False
        for p in list(pixels):
            if len(neighbours(p)) == 1:
                pixels.discard(p)
                changed = True
    if len(pixels) < 8:
        raise ValueError("Could not trace a closed centreline from the skeleton.")

    pts = np.array([(c, r) for r, c in pixels], dtype=float)  # (x, y)
    ring = _resample_closed(ring_contour, 3000)                # simple closed loop
    tree = cKDTree(ring)
    _, param = tree.query(pts)          # each skeleton pixel -> position along the ring
    order = np.argsort(param, kind="stable")
    return pts[order]


def build_centerline(mask: np.ndarray, ring_contour: np.ndarray,
                     n: int = N_POINTS) -> dict:
    """Centreline (medial axis) + per-point half-width from the track mask."""
    loop = _skeleton_loop(mask, ring_contour)
    centerline = _resample_closed(loop, n)
    centerline = _smooth_closed(centerline, sigma=2.0)
    centerline = _resample_closed(centerline, n)

    # local half-width = distance from the centreline to the nearest edge
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    h, w = mask.shape
    xs = np.clip(centerline[:, 0].round().astype(int), 0, w - 1)
    ys = np.clip(centerline[:, 1].round().astype(int), 0, h - 1)
    half_width = _smooth_closed(dt[ys, xs], sigma=2.0)
    half_width = np.maximum(half_width, 1.0)

    _, normal = _tangents_normals(centerline)
    return {"centerline": centerline, "half_width": half_width, "normal": normal}


# ------------------------------------------------------ racing-line solver

def min_curvature_line(
    centerline: np.ndarray,
    normal: np.ndarray,
    half_width: np.ndarray,
    margin_frac: float = WALL_MARGIN_FRAC,
) -> dict:
    """Solve for lateral offsets minimising total squared curvature.

    Racing line P_i = C_i + a_i * n_i. Minimising the second difference
    ||P_{i-1} - 2 P_i + P_{i+1}||^2 is convex and linear in the offsets a_i,
    so it is a bounded linear least-squares problem with a global optimum.
    """
    n = len(centerline)
    # residual r_i = a_{i-1} n_{i-1} - 2 a_i n_i + a_{i+1} n_{i+1} + d_i
    d = np.roll(centerline, 1, axis=0) - 2 * centerline + np.roll(centerline, -1, axis=0)

    # Build the (2n x n) design matrix column by column (each offset touches
    # three residual rows). Sparse would scale better; dense is fine at n~400.
    M = np.zeros((2 * n, n))
    for i in range(n):
        im1, ip1 = (i - 1) % n, (i + 1) % n
        M[2 * i, i] += -2 * normal[i, 0]
        M[2 * i + 1, i] += -2 * normal[i, 1]
        M[2 * im1, i] += normal[i, 0]
        M[2 * im1 + 1, i] += normal[i, 1]
        M[2 * ip1, i] += normal[i, 0]
        M[2 * ip1 + 1, i] += normal[i, 1]
    target = -d.reshape(-1)

    lim = half_width * (1.0 - margin_frac)
    res = lsq_linear(M, target, bounds=(-lim, lim), max_iter=200)
    alpha = res.x

    line = centerline + alpha[:, None] * normal
    return {"line": line, "alpha": alpha, "limit": lim}


# ---------------------------------------------------------- corner analysis

def detect_corners(line: np.ndarray, meters_per_px: float) -> list[dict]:
    """Locate corners as prominent curvature peaks around the loop."""
    kappa = curvature(line) / meters_per_px  # 1/m
    n = len(kappa)
    # tile to catch peaks across the wrap point, then map back
    tiled = np.concatenate([kappa, kappa, kappa])
    min_sep = max(8, n // 30)
    peaks, props = find_peaks(
        tiled, distance=min_sep, prominence=float(np.percentile(kappa, 75)) + 1e-6
    )
    seen, corners = set(), []
    for p in peaks:
        idx = p % n
        if n <= p < 2 * n and idx not in seen:
            seen.add(idx)
            radius = 1.0 / (kappa[idx] + 1e-9)
            corners.append({"index": int(idx), "radius_m": float(radius),
                            "curvature": float(kappa[idx])})
    corners.sort(key=lambda c: c["index"])
    for k, c in enumerate(corners, 1):
        c["number"] = k
    return corners


def apex_variants(
    centerline: np.ndarray,
    normal: np.ndarray,
    limit: np.ndarray,
    alpha: np.ndarray,
    corner_index: int,
    window: int = None,
) -> dict:
    """Early- / optimal- / late-apex lines through one corner.

    - optimal: the true minimum-curvature line (apex where physics puts it).
    - early apex: turn in early, kiss the inside before the geometric apex,
      then get pushed wide on exit (compromised exit speed).
    - late apex: stay wide, brake later, apex late, unwind onto the exit —
      the line you want out of a corner leading to a straight.

    Early/late are built as explicit out-in-out offset profiles with the
    inside-touch shifted along the corner, so the three read clearly as
    distinct lines rather than near-identical curves.
    """
    n = len(centerline)
    window = window or max(14, n // 12)
    inside = np.sign(alpha[corner_index]) or 1.0
    shift = max(4, window // 2)

    idx = np.arange(n)
    signed = ((idx - corner_index + n // 2) % n) - n // 2  # signed dist from apex
    within = np.abs(signed) <= window

    def out_in_out(apex_shift: float, inside_frac: float, outside_frac: float):
        """Raised-cosine offset: outside at the edges, inside at the apex."""
        d = (signed - apex_shift) / window
        d = np.clip(d, -1.0, 1.0)
        shape = np.cos(d * np.pi / 2) ** 2          # 1 at apex → 0 at edges
        edge = 1.0 - shape                           # 0 at apex → 1 at edges
        off = inside * (inside_frac * shape - outside_frac * edge) * limit
        return np.where(within, off, alpha)

    def build(offsets):
        return centerline + np.clip(offsets, -limit, limit)[:, None] * normal

    optimal = alpha.copy()
    early = out_in_out(-shift, inside_frac=0.92, outside_frac=0.75)
    late = out_in_out(+shift, inside_frac=0.92, outside_frac=0.75)

    lo = (corner_index - window) % n
    seg = (np.arange(lo, lo + 2 * window + 1)) % n
    return {
        "lines": {"optimal": build(optimal), "early": build(early), "late": build(late)},
        "segment_index": seg.tolist(),
        "window": window,
        "corner_index": corner_index,
    }


# ------------------------------------------------------------- lap time

def _corner_limited_speed(kappa: np.ndarray, car: dict) -> np.ndarray:
    """Grip-limited cornering speed with speed-dependent (aero) grip.

    Balance:  v^2 * kappa = a_lat_max(v) = g * (mu + k * v^2).
    Solving,  v^2 = g * mu / (kappa - g * k).
    When kappa <= g*k the corner is downforce-limited (the car could take it
    flat), so it's capped at v_max instead.
    """
    g, mu, k = G, car["mu"], car["downforce_k"]
    denom = kappa - g * k
    v = np.full_like(kappa, car["v_max"])
    ok = denom > 1e-9
    v[ok] = np.sqrt(g * mu / denom[ok])
    return np.minimum(v, car["v_max"])


def estimate_lap_time(
    line: np.ndarray, meters_per_px: float, car: dict = None
) -> dict:
    """Quasi-steady-state lap time for the racing line.

    Cornering speed is grip-limited with grip that grows with speed (mechanical
    tyre grip + downforce ~ v^2), which is what keeps slow corners slow. A
    forward pass caps acceleration out of corners and a backward pass caps
    braking into them. Idealised — no gears, no aero drag, no tyre wear — so
    treat it as a fast-but-plausible reference, not a simulation of one car.
    """
    car = car or DEFAULT_CAR
    pts = _resample_closed(line, len(line))
    ds = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1) * meters_per_px
    kappa = np.maximum(curvature(pts) / meters_per_px, 1e-6)
    n = len(pts)

    v = _corner_limited_speed(kappa, car)

    # forward (traction) then backward (braking); loop a few times for closure
    for _ in range(4):
        for i in range(n):
            j = (i - 1) % n
            v[i] = min(v[i], np.sqrt(v[j] ** 2 + 2 * car["acc_accel"] * ds[j]))
        for i in range(n - 1, -1, -1):
            j = (i + 1) % n
            v[i] = min(v[i], np.sqrt(v[j] ** 2 + 2 * car["brk_accel"] * ds[i]))

    v_avg = (v + np.roll(v, -1)) / 2.0
    lap_time = float(np.sum(ds / np.maximum(v_avg, 1e-3)))
    return {
        "lap_time_s": lap_time,
        "length_m": float(np.sum(ds)),
        "v_max_kmh": float(v.max() * 3.6),
        "v_min_kmh": float(v.min() * 3.6),
        "speed_kmh": (v * 3.6).tolist(),
    }


def format_lap_time(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:06.3f}"


# --------------------------------------------------------------- top level

def analyze(image: np.ndarray, track_length_km: float | None = None,
            car: dict = None) -> dict:
    """Full pipeline. Returns a JSON-friendly dict of everything the UI needs."""
    track = extract_track(image)
    cl = build_centerline(track["mask"], track["outer"])
    solved = min_curvature_line(cl["centerline"], cl["normal"], cl["half_width"])

    center_len_px = float(
        np.sum(np.linalg.norm(
            np.roll(cl["centerline"], -1, axis=0) - cl["centerline"], axis=1))
    )
    assumed = track_length_km is None
    length_km = track_length_km if track_length_km else 5.0
    meters_per_px = (length_km * 1000.0) / center_len_px

    corners = detect_corners(solved["line"], meters_per_px)
    timing = estimate_lap_time(solved["line"], meters_per_px, car)

    variants = []
    for c in corners:
        v = apex_variants(cl["centerline"], cl["normal"], solved["limit"],
                          solved["alpha"], c["index"])
        variants.append({
            "number": c["number"],
            "corner_index": c["index"],
            "radius_m": round(c["radius_m"], 1),
            "segment_index": v["segment_index"],
            "lines": {k: line.round(2).tolist() for k, line in v["lines"].items()},
        })

    def to_list(a):
        return a.round(2).tolist()

    return {
        "image_size": {"h": int(track["size"][0]), "w": int(track["size"][1])},
        "outer": to_list(_resample_closed(track["outer"], N_POINTS)),
        "inner": to_list(_resample_closed(track["inner"], N_POINTS)),
        "centerline": to_list(cl["centerline"]),
        "racing_line": to_list(solved["line"]),
        "corners": corners,
        "corner_variants": variants,
        "meters_per_px": meters_per_px,
        "track_length_km": round(length_km, 3),
        "track_length_assumed": assumed,
        "lap_time_s": round(timing["lap_time_s"], 3),
        "lap_time_str": format_lap_time(timing["lap_time_s"]),
        "v_max_kmh": round(timing["v_max_kmh"], 1),
        "v_min_kmh": round(timing["v_min_kmh"], 1),
        "speed_kmh": [round(x, 1) for x in timing["speed_kmh"]],
        "n_corners": len(corners),
    }


def track_image_from_xy(x, y, size: int = 2200, width_m: float = 9.0) -> np.ndarray:
    """Draw a closed track ribbon from telemetry X/Y (1/10 m) — the same format
    the analyzer expects, thin enough to keep hairpins open."""
    x = np.asarray(x, dtype=float).copy()
    y = np.asarray(y, dtype=float).copy()
    x -= x.min(); y -= y.min()
    span = max(x.max(), y.max())
    scale = (size * 0.84) / span
    x = x * scale + (size - x.max() * scale) / 2
    y = (y.max() - y) * scale + (size - y.max() * scale) / 2  # flip Y
    width_px = max(3, int(width_m * 10 * scale))
    pts = np.column_stack([x, y]).astype(np.int32)
    img = np.full((size, size, 3), 245, np.uint8)
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], True, (38, 38, 44), width_px, cv2.LINE_AA)
    return img


def analyze_from_xy(x, y, track_length_km: float | None = None) -> dict:
    """Racing-line analysis straight from a telemetry lap's X/Y trace."""
    return analyze(track_image_from_xy(x, y), track_length_km=track_length_km)


# ------------------------------------------------------------- rendering

def render(image: np.ndarray, result: dict) -> np.ndarray:
    """Draw boundaries + racing line (colour-coded by speed) onto the image."""
    canvas = image.copy()
    if canvas.ndim == 2:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

    def poly(pts, color, thick, closed=True):
        arr = np.asarray(pts, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(canvas, [arr], closed, color, thick, cv2.LINE_AA)

    poly(result["outer"], (90, 90, 90), 2)
    poly(result["inner"], (90, 90, 90), 2)

    # racing line coloured green (slow) -> red (fast)
    line = np.asarray(result["racing_line"], dtype=np.int32)
    speed = np.asarray(result["speed_kmh"])
    smin, smax = speed.min(), speed.max() + 1e-6
    for i in range(len(line)):
        t = (speed[i] - smin) / (smax - smin)
        color = (0, int(255 * (1 - t)), int(60 + 195 * t))  # BGR green->red
        j = (i + 1) % len(line)
        cv2.line(canvas, tuple(line[i]), tuple(line[j]), color, 3, cv2.LINE_AA)

    for c in result["corners"]:
        p = line[c["index"]]
        cv2.circle(canvas, tuple(p), 6, (0, 215, 255), -1, cv2.LINE_AA)
        cv2.putText(canvas, str(c["number"]), (p[0] + 8, p[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 215, 255), 2, cv2.LINE_AA)
    return canvas


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the uploaded image.")
    return img
