/* Racing Line tab — upload a track map, render the racing line on it, and
   step through the three ways to take each corner. Plain canvas, no deps. */

"use strict";

(function () {
  const VARIANTS = {
    early: {
      color: "#ff8000", label: "Early apex", brake: "early braking",
      caption: "Turn in early and clip the inside before the corner's midpoint. " +
        "You point at the exit sooner, but the car gets pushed wide and you scrub " +
        "exit speed — costly when a straight follows.",
    },
    optimal: {
      color: "#e10600", label: "Optimal", brake: "balanced braking",
      caption: "The minimum-curvature line: one smooth arc using the full width of " +
        "the track, apex near the geometric middle. The fastest single pass through " +
        "an isolated corner.",
    },
    late: {
      color: "#27f4d2", label: "Late apex", brake: "late braking",
      caption: "Brake later and stay wide on entry, then turn down to a late apex and " +
        "unwind onto the exit. Slower entry, but you get on the power earlier — the " +
        "line you want onto a straight.",
    },
  };
  const ORDER = ["early", "optimal", "late"];

  const RL = {
    img: null, result: null, file: null,
    view: null, focus: null, variant: null, timer: null,
    toggles: { bounds: true, center: false, speed: true },
  };

  const $ = (s) => document.querySelector(s);
  let canvas, ctx;

  /* ------------------------------------------------------------ geometry */

  function setCanvasForImage() {
    const maxW = 1000;
    const w = RL.img.naturalWidth, h = RL.img.naturalHeight;
    const scale = Math.min(1, maxW / w);
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
  }

  function fullView() {
    RL.view = { x: 0, y: 0, w: RL.img.naturalWidth, h: RL.img.naturalHeight };
  }

  function cornerView(variant) {
    const pts = ORDER.flatMap((k) => variant.segment_index.map((i) => variant.lines[k][i]));
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    let w = x1 - x0, h = y1 - y0;
    const padX = w * 0.35 + 20, padY = h * 0.35 + 20;
    x0 -= padX; y0 -= padY; w += 2 * padX; h += 2 * padY;
    // match canvas aspect so nothing is squashed
    const ar = canvas.width / canvas.height;
    if (w / h > ar) { const nh = w / ar; y0 -= (nh - h) / 2; h = nh; }
    else { const nw = h * ar; x0 -= (nw - w) / 2; w = nw; }
    RL.view = { x: x0, y: y0, w, h };
  }

  const T = (p) => [
    (p[0] - RL.view.x) / RL.view.w * canvas.width,
    (p[1] - RL.view.y) / RL.view.h * canvas.height,
  ];

  function speedColor(t) {
    // 0 = slow (green) -> 0.5 (yellow) -> 1 = fast (red)
    const stops = [[0, 194, 107], [255, 209, 46], [225, 6, 0]];
    const seg = t < 0.5 ? 0 : 1;
    const f = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
    const a = stops[seg], b = stops[seg + 1];
    const c = a.map((v, i) => Math.round(v + (b[i] - v) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  /* -------------------------------------------------------------- drawing */

  function drawPoly(pts, color, width, closed) {
    ctx.beginPath();
    pts.forEach((p, i) => {
      const [x, y] = T(p);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    if (closed) ctx.closePath();
    ctx.strokeStyle = color; ctx.lineWidth = width;
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.stroke();
  }

  function drawImageRegion() {
    const { x, y, w, h } = RL.view;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(RL.img, x, y, w, h, 0, 0, canvas.width, canvas.height);
    // slight dark wash so coloured lines pop
    ctx.fillStyle = "rgba(10,10,16,0.28)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawRacingLine(dim) {
    const line = RL.result.racing_line, speed = RL.result.speed_kmh;
    const smin = Math.min(...speed), smax = Math.max(...speed) + 1e-6;
    const width = RL.view.w < RL.img.naturalWidth * 0.6 ? 6 : 3.5;
    for (let i = 0; i < line.length; i++) {
      const j = (i + 1) % line.length;
      const [x1, y1] = T(line[i]), [x2, y2] = T(line[j]);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
      ctx.strokeStyle = dim ? "rgba(120,120,135,0.35)"
        : RL.toggles.speed ? speedColor((speed[i] - smin) / (smax - smin)) : "#e10600";
      ctx.lineWidth = width; ctx.lineCap = "round";
      ctx.stroke();
    }
  }

  function drawApexMarkers() {
    RL.result.corners.forEach((c) => {
      const [x, y] = T(RL.result.racing_line[c.index]);
      ctx.beginPath(); ctx.arc(x, y, 6, 0, 7); ctx.fillStyle = "#ffd12e"; ctx.fill();
      ctx.fillStyle = "#0b0b11"; ctx.font = "bold 11px 'JetBrains Mono'";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(c.number, x, y);
    });
  }

  function renderFull() {
    RL.focus = null;
    fullView();
    drawImageRegion();
    if (RL.toggles.bounds) {
      drawPoly(RL.result.outer, "rgba(150,150,160,0.7)", 2, true);
      drawPoly(RL.result.inner, "rgba(150,150,160,0.7)", 2, true);
    }
    if (RL.toggles.center) drawPoly(RL.result.centerline, "rgba(120,150,255,0.5)", 1.5, true);
    drawRacingLine(false);
    drawApexMarkers();
    startHotLap();
  }

  /* Onboard hot-lap: a glowing dot laps the racing line on an overlay canvas
     (so the track underneath isn't redrawn every frame), paced by local speed. */
  function stopHotLap() {
    if (RL._lapRAF) { cancelAnimationFrame(RL._lapRAF); RL._lapRAF = null; }
    const ov = document.getElementById("rl-overlay");
    if (ov) ov.getContext("2d").clearRect(0, 0, ov.width, ov.height);
  }

  function startHotLap() {
    stopHotLap();
    if (!RL.result || RL.focus) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const base = canvas;
    let ov = document.getElementById("rl-overlay");
    if (!ov) {
      ov = document.createElement("canvas");
      ov.id = "rl-overlay";
      document.getElementById("rl-canvas-wrap").appendChild(ov);
    }
    ov.width = base.width; ov.height = base.height;
    ov.style.left = base.offsetLeft + "px";
    ov.style.top = base.offsetTop + "px";
    ov.style.width = base.clientWidth + "px";
    ov.style.height = base.clientHeight + "px";
    const octx = ov.getContext("2d");
    const line = RL.result.racing_line, speed = RL.result.speed_kmh, N = line.length;
    const smin = Math.min(...speed), smax = Math.max(...speed) + 1e-6;
    let pos = 0;
    const frame = () => {
      if (RL.focus || !document.getElementById("rl-overlay")) return;
      octx.clearRect(0, 0, ov.width, ov.height);
      const i = Math.floor(pos) % N, t = (speed[i] - smin) / (smax - smin);
      const [px, py] = T(line[i]);
      octx.save();
      octx.shadowBlur = 16;
      octx.shadowColor = `rgb(${Math.round(60 + 195 * t)},${Math.round(194 * (1 - t))},${Math.round(30 * (1 - t))})`;
      octx.fillStyle = "#fff";
      octx.beginPath(); octx.arc(px, py, 6, 0, 7); octx.fill();
      octx.restore();
      pos = (pos + 0.7 + 4 * t) % N;
      RL._lapRAF = requestAnimationFrame(frame);
    };
    frame();
  }

  function renderFocus() {
    stopHotLap();
    const variant = RL.result.corner_variants.find((v) => v.number === RL.focus);
    if (!variant) return;
    cornerView(variant);
    drawImageRegion();
    if (RL.toggles.bounds) {
      drawPoly(RL.result.outer, "rgba(150,150,160,0.6)", 2, true);
      drawPoly(RL.result.inner, "rgba(150,150,160,0.6)", 2, true);
    }
    const seg = variant.segment_index;
    // draw non-highlighted first (dim), highlighted last (bright)
    ORDER.forEach((k) => {
      if (k === RL.variant) return;
      const pts = seg.map((i) => variant.lines[k][i]);
      drawPoly(pts, hexA(VARIANTS[k].color, 0.28), 4, false);
    });
    const hi = seg.map((i) => variant.lines[RL.variant][i]);
    drawPoly(hi, VARIANTS[RL.variant].color, 6, false);

    // apex dot
    const apex = variant.lines[RL.variant][variant.corner_index];
    const [ax, ay] = T(apex);
    ctx.beginPath(); ctx.arc(ax, ay, 7, 0, 7);
    ctx.fillStyle = VARIANTS[RL.variant].color; ctx.fill();
    ctx.strokeStyle = "#0b0b11"; ctx.lineWidth = 2; ctx.stroke();
  }

  function hexA(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  function render() { RL.focus ? renderFocus() : renderFull(); }

  /* --------------------------------------------------------------- panels */

  function renderStats() {
    const r = RL.result;
    const note = r.track_length_assumed ? "assumed length" : "point-mass model";
    $("#rl-stats").innerHTML = `
      <div class="stat hero"><div class="num">${r.lap_time_str}</div><div class="lbl">Ideal lap</div><div class="rl-stat-note">${note}</div></div>
      <div class="stat"><div class="num">${r.n_corners}</div><div class="lbl">Corners</div></div>
      <div class="stat"><div class="num">${r.v_max_kmh.toFixed(0)}</div><div class="lbl">Top km/h</div></div>
      <div class="stat"><div class="num">${r.v_min_kmh.toFixed(0)}</div><div class="lbl">Min km/h</div></div>
      <div class="stat"><div class="num">${r.track_length_km}</div><div class="lbl">Length km</div></div>`;
    $("#rl-stats").classList.remove("hidden");
  }

  function renderCornerList() {
    const speed = RL.result.speed_kmh;
    $("#rl-corner-list").innerHTML = RL.result.corners.map((c) => `
      <div class="rl-corner-item" data-corner="${c.number}">
        <span class="rc-num">${c.number}</span>
        <span class="rc-meta">${c.radius_m.toFixed(0)} m radius</span>
        <span class="rc-spd">${speed[c.index].toFixed(0)} km/h</span>
      </div>`).join("");
    $("#rl-corner-list").querySelectorAll(".rl-corner-item").forEach((el) =>
      el.addEventListener("click", () => focusCorner(Number(el.dataset.corner))));
    $("#rl-corner-card").classList.remove("hidden");
  }

  function renderVariantTabs() {
    $("#rl-variant-tabs").innerHTML = ORDER.map((k) => `
      <div class="rl-vtab ${k === RL.variant ? "active" : ""}" data-variant="${k}">
        <div class="vt-name"><span class="dot" style="background:${VARIANTS[k].color}"></span>${VARIANTS[k].label}</div>
        <div class="vt-brake">${VARIANTS[k].brake}</div>
      </div>`).join("");
    $("#rl-variant-tabs").querySelectorAll(".rl-vtab").forEach((el) =>
      el.addEventListener("click", () => { stopCycle(); setVariant(el.dataset.variant); }));
    $("#rl-variant-caption").textContent = VARIANTS[RL.variant].caption;
  }

  function setVariant(k) {
    RL.variant = k;
    renderVariantTabs();
    render();
  }

  function focusCorner(num) {
    stopCycle();
    RL.focus = num;
    RL.variant = "optimal";
    $("#rl-focus-num").textContent = num;
    $("#rl-focus").classList.remove("hidden");
    document.querySelectorAll(".rl-corner-item").forEach((el) =>
      el.classList.toggle("active", Number(el.dataset.corner) === num));
    renderVariantTabs();
    render();
    $("#rl-focus").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function cycleCorner(delta) {
    if (!RL.result.corners.length) return;
    const n = RL.result.corners.length;
    const cur = RL.focus || 1;
    focusCorner(((cur - 1 + delta + n) % n) + 1);
  }

  function startCycle() {
    stopCycle();
    let i = 0;
    setVariant(ORDER[0]);
    $("#rl-cycle").textContent = "⏸ Stop";
    RL.timer = setInterval(() => {
      i = (i + 1) % ORDER.length;
      setVariant(ORDER[i]);
    }, 1600);
  }

  function stopCycle() {
    if (RL.timer) { clearInterval(RL.timer); RL.timer = null; }
    const btn = $("#rl-cycle");
    if (btn) btn.textContent = "▶ Play the three lines";
  }

  /* --------------------------------------------------------------- upload */

  function loadFile(file) {
    if (!file || !file.type.startsWith("image/")) return;
    RL.file = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        RL.img = img;
        $("#rl-controls").classList.remove("hidden");
        $("#rl-status").textContent = "Ready — set the length and hit Analyze.";
        $("#rl-dz-inner").innerHTML =
          `<div class="dz-title">${escapeHtml(file.name)}</div>` +
          `<div class="dz-sub">loaded — drop another to replace</div>`;
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function analyze() {
    if (!RL.file) return;
    const btn = $("#rl-run");
    btn.disabled = true;
    $("#rl-status").textContent = "";
    const empty = $("#rl-empty");
    empty.style.display = "";
    empty.innerHTML = Charts.lights("Analysing track…");
    const fd = new FormData();
    fd.append("image", RL.file);
    fd.append("length_km", $("#rl-length").value);
    try {
      const res = await fetch("/api/racingline", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Analysis failed");
      RL.result = data;
      $("#rl-empty").style.display = "none";
      $("#rl-toggles").classList.remove("hidden");
      setCanvasForImage();
      renderFull();
      renderStats();
      renderCornerList();
      $("#rl-focus").classList.add("hidden");
      $("#rl-status").textContent = `Done — ${data.n_corners} corners, ideal lap ${data.lap_time_str}.`;
      window.radio && window.radio("Track analysed",
        `${data.n_corners} corners · ideal lap ${data.lap_time_str}`);
    } catch (e) {
      empty.innerHTML = "The analysed track will appear here";
      $("#rl-status").textContent = e.message;
    } finally {
      btn.disabled = false;
    }
  }

  function reset() {
    stopCycle();
    stopHotLap();
    RL.img = RL.result = RL.file = null;
    $("#rl-controls").classList.add("hidden");
    $("#rl-corner-card").classList.add("hidden");
    $("#rl-stats").classList.add("hidden");
    $("#rl-focus").classList.add("hidden");
    $("#rl-toggles").classList.add("hidden");
    $("#rl-empty").style.display = "";
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    $("#rl-dz-inner").innerHTML =
      `<div class="dz-icon"></div><div class="dz-title">Drop a track map here</div>` +
      `<div class="dz-sub">or <span class="dz-browse">browse</span> — PNG / JPG, tarmac as a closed band</div>`;
  }

  /* ----------------------------------------------------------------- init */

  function init() {
    canvas = $("#rl-canvas");
    ctx = canvas.getContext("2d");

    $("#rl-legend").innerHTML =
      `<span><span class="sw grad"></span>racing line: slow → fast</span>` +
      `<span><span class="sw" style="background:#ffd12e"></span>apex</span>`;

    const dz = $("#rl-dropzone"), fileInput = $("#rl-file");
    dz.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => loadFile(e.target.files[0]));
    ["dragover", "dragenter"].forEach((ev) =>
      dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((ev) =>
      dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
    dz.addEventListener("drop", (e) => loadFile(e.dataTransfer.files[0]));

    $("#rl-run").addEventListener("click", analyze);
    $("#rl-reset").addEventListener("click", reset);
    $("#rl-prev").addEventListener("click", () => cycleCorner(-1));
    $("#rl-next").addEventListener("click", () => cycleCorner(1));
    $("#rl-cycle").addEventListener("click", () =>
      RL.timer ? stopCycle() : startCycle());

    $("#rl-t-bounds").addEventListener("change", (e) => { RL.toggles.bounds = e.target.checked; render(); });
    $("#rl-t-center").addEventListener("change", (e) => { RL.toggles.center = e.target.checked; render(); });
    $("#rl-t-speed").addEventListener("change", (e) => { RL.toggles.speed = e.target.checked; render(); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
