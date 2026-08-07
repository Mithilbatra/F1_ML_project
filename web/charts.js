/* Tiny dependency-free SVG chart builders shared by the fan-feature tabs.
   Each returns an SVG markup string to drop into innerHTML. */

"use strict";

const Charts = (() => {
  const NS = 'xmlns="http://www.w3.org/2000/svg"';

  function scale(v, lo, hi, a, b) {
    if (hi === lo) return (a + b) / 2;
    return a + (v - lo) / (hi - lo) * (b - a);
  }

  // accessibility wrapper: a labelled chart is an image with a title;
  // an unlabelled one is decorative (its numbers live in adjacent text)
  function a11y(label) {
    return label
      ? `role="img" aria-label="${String(label).replace(/"/g, "&quot;")}"`
      : `role="img" aria-hidden="true"`;
  }
  const titleEl = (label) => label
    ? `<title>${String(label).replace(/[<&]/g, (c) => ({ "<": "&lt;", "&": "&amp;" }[c]))}</title>`
    : "";

  function pathFrom(xs, ys, xlo, xhi, ylo, yhi, w, h, pad) {
    let d = "";
    for (let i = 0; i < xs.length; i++) {
      const px = scale(xs[i], xlo, xhi, pad.l, w - pad.r);
      const py = scale(ys[i], ylo, yhi, h - pad.b, pad.t);
      d += (i ? "L" : "M") + px.toFixed(1) + " " + py.toFixed(1) + " ";
    }
    return d.trim();
  }

  /* Multi-line chart over a shared x axis. */
  function lines({ x, series, w = 640, h = 200, ylabel = "", yMin = null,
                   yMax = null, pad = { t: 10, r: 12, b: 22, l: 42 }, hlines = [],
                   label = "" }) {
    const xlo = x[0], xhi = x[x.length - 1];
    let lo = yMin, hi = yMax;
    if (lo === null || hi === null) {
      const all = series.flatMap((s) => s.y);
      lo = lo === null ? Math.min(...all) : lo;
      hi = hi === null ? Math.max(...all) : hi;
    }
    const padY = (hi - lo) * 0.08 || 1;
    lo -= padY; hi += padY;

    let g = "";
    for (const yv of hlines) {
      const py = scale(yv, lo, hi, h - pad.b, pad.t);
      g += `<line x1="${pad.l}" y1="${py}" x2="${w - pad.r}" y2="${py}" stroke="var(--line)" stroke-dasharray="2 3"/>`;
    }
    // y ticks (min / mid / max)
    for (const yv of [lo + padY, (lo + hi) / 2, hi - padY]) {
      const py = scale(yv, lo, hi, h - pad.b, pad.t);
      g += `<text x="${pad.l - 6}" y="${py + 3}" text-anchor="end" class="ct-tick">${Math.round(yv)}</text>`;
    }
    for (const s of series) {
      g += `<path d="${pathFrom(x, s.y, xlo, xhi, lo, hi, w, h, pad)}" fill="none" stroke="${s.color}" stroke-width="${s.width || 2}" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""} stroke-linejoin="round"/>`;
    }
    if (ylabel) g += `<text x="6" y="${pad.t + 8}" class="ct-axis">${ylabel}</text>`;
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg" preserveAspectRatio="none" ${a11y(label)}>${titleEl(label)}${g}</svg>`;
  }

  /* Filled delta area: positive above zero shaded one colour, negative the other. */
  function delta({ x, y, w = 640, h = 140, posColor, negColor, label = "",
                   pad = { t: 12, r: 12, b: 22, l: 42 } }) {
    const xlo = x[0], xhi = x[x.length - 1];
    const m = Math.max(0.05, Math.max(...y.map(Math.abs)));
    const lo = -m, hi = m;
    const zero = scale(0, lo, hi, h - pad.b, pad.t);
    const line = pathFrom(x, y, xlo, xhi, lo, hi, w, h, pad);
    const x0 = scale(xlo, xlo, xhi, pad.l, w - pad.r);
    const x1 = scale(xhi, xlo, xhi, pad.l, w - pad.r);
    const area = `M${x0} ${zero} ${line.replace("M", "L")} L${x1} ${zero} Z`;
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg" preserveAspectRatio="none" ${a11y(label)}>
      ${titleEl(label)}<defs><linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${posColor}" stop-opacity="0.6"/>
        <stop offset="50%" stop-color="${posColor}" stop-opacity="0.05"/>
        <stop offset="50%" stop-color="${negColor}" stop-opacity="0.05"/>
        <stop offset="100%" stop-color="${negColor}" stop-opacity="0.6"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#dg)"/>
      <line x1="${pad.l}" y1="${zero}" x2="${w - pad.r}" y2="${zero}" stroke="var(--muted)" stroke-width="1"/>
      <path d="${line}" fill="none" stroke="var(--text)" stroke-width="1.6"/>
      <text x="${pad.l - 6}" y="${pad.t + 8}" text-anchor="end" class="ct-tick">+${m.toFixed(2)}s</text>
      <text x="${pad.l - 6}" y="${h - pad.b}" text-anchor="end" class="ct-tick">-${m.toFixed(2)}s</text>
    </svg>`;
  }

  /* Track outline coloured per segment by a category (1 or 2).
     Includes a hidden scrubber marker (#<markerId>) that callers can move
     with trackScale()'s coordinate mapping. */
  function track({ x, y, faster, colors, w = 360, h = 360, lineWidth = 5,
                   markerId = null, label = "" }) {
    const { sx, sy } = trackScale(x, y, w, h);
    let g = "";
    for (let i = 0; i < x.length - 1; i++) {
      const c = colors[faster[i] === 1 ? 0 : 1];
      g += `<line x1="${sx(x[i]).toFixed(1)}" y1="${sy(y[i]).toFixed(1)}" x2="${sx(x[i + 1]).toFixed(1)}" y2="${sy(y[i + 1]).toFixed(1)}" stroke="${c}" stroke-width="${lineWidth}" stroke-linecap="round"/>`;
    }
    if (markerId) {
      g += `<circle id="${markerId}" r="7" fill="#fff" stroke="#0b0b11" stroke-width="2.5" opacity="0"/>`;
    }
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-track" ${a11y(label)}>${titleEl(label)}${g}</svg>`;
  }

  /* The exact coordinate mapping track() uses — for positioning markers. */
  function trackScale(x, y, w = 360, h = 360) {
    const xlo = Math.min(...x), ylo = Math.min(...y);
    const span = Math.max(Math.max(...x) - xlo, Math.max(...y) - ylo);
    const pad = 16;
    return {
      sx: (v) => pad + (v - xlo) / span * (w - 2 * pad),
      sy: (v) => h - pad - (v - ylo) / span * (h - 2 * pad),
    };
  }

  /* Five-light F1 start gantry, used as a loading indicator.
     Lights come on one by one, hold, then go out — and it's lights out! */
  function lights(label = "Loading…") {
    const cells = [0, 1, 2, 3, 4].map((i) =>
      `<span class="fx-light" style="animation-delay:${i * 0.28}s"></span>`).join("");
    return `<div class="fx-lights" role="status" aria-label="${label}">
      <div class="fx-lights-row">${cells}</div>
      <div class="fx-lights-label">${label}</div>
    </div>`;
  }

  /* Animated count-up for stat numbers. */
  function countUp(el, target, { decimals = 0, duration = 750, suffix = "" } = {}) {
    const t0 = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const step = (now) => {
      const p = Math.min(1, (now - t0) / duration);
      el.textContent = (target * ease(p)).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* Horizontal bar list: rows of {label, value, color, sub}. */
  function bars({ rows, w = 640, rowH = 26, maxValue = null, unit = "",
                 fmt = (v) => v, label = "" }) {
    const max = maxValue ?? Math.max(...rows.map((r) => r.value), 1e-9);
    const labelW = 96, valW = 66, h = rows.length * rowH + 6;
    let g = "";
    rows.forEach((r, i) => {
      const y = i * rowH + 4;
      const bw = Math.max(1, (r.value / max) * (w - labelW - valW - 12));
      g += `<text x="0" y="${y + rowH / 2 + 3}" class="ct-blabel">${r.label}</text>`;
      g += `<rect x="${labelW}" y="${y + 4}" width="${bw}" height="${rowH - 10}" rx="2" fill="${r.color}"/>`;
      g += `<text x="${w - 4}" y="${y + rowH / 2 + 3}" text-anchor="end" class="ct-bval">${fmt(r.value)}${unit}</text>`;
      if (r.sub) g += `<text x="${labelW + bw + 6}" y="${y + rowH / 2 + 3}" class="ct-bsub">${r.sub}</text>`;
    });
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg" ${a11y(label)}>${titleEl(label)}${g}</svg>`;
  }

  /* Side-profile modern F1 car — a clean, single-silhouette illustration.
     Nose to the left. Wheel rims carry a .rim class so CSS can spin them.
     Pure vector, crisp at any size, no external assets. */
  function car(cls = "") {
    const RED = "#e10600", TRIM = "#f2f0ed", TYRE = "#131318", RIM = "#c7cad0",
          EDGE = "#43434f";
    // one continuous body silhouette (front-wing tip -> airbox -> rear deck)
    const body = "M30 138 C34 130 44 126 62 125 C110 122 165 120 210 116 "
      + "C246 113 278 112 300 112 L330 112 C336 100 350 94 358 96 "
      + "C372 97 380 102 388 106 C440 116 492 122 528 126 L540 126 L540 140 "
      + "L120 140 C74 140 46 139 30 138 Z";
    return `<svg ${NS} viewBox="0 0 600 176" class="car-svg ${cls}" aria-hidden="true">
      <defs>
        <linearGradient id="carBody" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#33333f"/>
          <stop offset="0.5" stop-color="#22222c"/>
          <stop offset="1" stop-color="#181820"/>
        </linearGradient>
      </defs>

      <ellipse cx="300" cy="160" rx="268" ry="7" fill="rgba(0,0,0,0.4)"/>

      <!-- rear wing (connected to the rear deck) -->
      <rect x="558" y="52" width="12" height="76" rx="4" fill="#20202a"/>
      <rect x="498" y="52" width="70" height="11" rx="4" fill="#2a2a34"/>
      <rect x="504" y="55" width="58" height="4" rx="2" fill="${RED}"/>
      <rect x="512" y="112" width="54" height="8" rx="3" fill="#20202a"/>
      <path d="M534 63 q7 24 0 49 h8 q7 -24 1 -49 z" fill="#20202a"/>

      <!-- body -->
      <path d="${body}" fill="url(#carBody)"/>
      <path d="${body}" fill="none" stroke="${EDGE}" stroke-width="1.6" stroke-linejoin="round"/>

      <!-- airbox intake shadow -->
      <path d="M344 104 C350 86 370 82 380 92 L372 104 Z" fill="#0d0d14"/>

      <!-- red livery sweep along the shoulder, tapering rearward -->
      <path d="M60 128 C150 121 240 116 300 116 C318 116 326 120 330 126
               C300 120 220 122 150 128 C112 131 82 134 60 136 Z" fill="${RED}"/>
      <!-- thin white pinstripe under the red -->
      <path d="M66 137 C150 129 240 123 316 123 L316 126 C240 126 150 132 66 139 Z"
            fill="${TRIM}" opacity="0.9"/>

      <!-- number roundel on the nose -->
      <circle cx="104" cy="131" r="9.5" fill="${TRIM}"/>
      <text x="104" y="135.5" text-anchor="middle" font-family="Titillium Web, sans-serif"
            font-size="12" font-style="italic" font-weight="900" fill="${RED}">5</text>

      <!-- cockpit opening + halo -->
      <path d="M312 112 C316 101 340 101 344 112 Z" fill="#0a0a10"/>
      <path d="M298 111 C308 90 352 90 362 109" fill="none" stroke="#3a3a46"
            stroke-width="6" stroke-linecap="round"/>
      <line x1="330" y1="92" x2="330" y2="110" stroke="#3a3a46" stroke-width="5"/>

      <!-- front wing -->
      <rect x="8" y="145" width="122" height="6" rx="3" fill="#2a2a34"/>
      <rect x="18" y="138" width="104" height="4" rx="2" fill="#20202a"/>
      <rect x="6" y="130" width="8" height="25" rx="2" fill="#20202a"/>

      ${wheel(170, 130, 33, TYRE, RIM, RED)}
      ${wheel(456, 128, 37, TYRE, RIM, RED)}
    </svg>`;
  }

  /* Clean 5-spoke wheel; the spoked disc is a .rim group for CSS spin. */
  function wheel(cx, cy, r, tyre, rim, hub) {
    const spokes = [];
    for (let k = 0; k < 5; k++) {
      const a = (k / 5) * Math.PI * 2;
      spokes.push(`<line x1="${cx}" y1="${cy}" x2="${(cx + Math.cos(a) * r * 0.42).toFixed(1)}" y2="${(cy + Math.sin(a) * r * 0.42).toFixed(1)}" stroke="${rim}" stroke-width="${r * 0.11}" stroke-linecap="round"/>`);
    }
    return `<g>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="${tyre}"/>
      <circle cx="${cx}" cy="${cy}" r="${r - 2}" fill="none" stroke="#2a2a33" stroke-width="2"/>
      <g class="rim" style="transform-box:fill-box;transform-origin:center">
        <circle cx="${cx}" cy="${cy}" r="${r * 0.5}" fill="#22222b"/>
        ${spokes.join("")}
        <circle cx="${cx}" cy="${cy}" r="${r * 0.16}" fill="${hub}"/>
      </g>
    </g>`;
  }

  return { lines, delta, track, trackScale, bars, lights, countUp, car };
})();
