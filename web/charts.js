/* Tiny dependency-free SVG chart builders shared by the fan-feature tabs.
   Each returns an SVG markup string to drop into innerHTML. */

"use strict";

const Charts = (() => {
  const NS = 'xmlns="http://www.w3.org/2000/svg"';

  function scale(v, lo, hi, a, b) {
    if (hi === lo) return (a + b) / 2;
    return a + (v - lo) / (hi - lo) * (b - a);
  }

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
                   yMax = null, pad = { t: 10, r: 12, b: 22, l: 42 }, hlines = [] }) {
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
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg" preserveAspectRatio="none">${g}</svg>`;
  }

  /* Filled delta area: positive above zero shaded one colour, negative the other. */
  function delta({ x, y, w = 640, h = 140, posColor, negColor,
                   pad = { t: 12, r: 12, b: 22, l: 42 } }) {
    const xlo = x[0], xhi = x[x.length - 1];
    const m = Math.max(0.05, Math.max(...y.map(Math.abs)));
    const lo = -m, hi = m;
    const zero = scale(0, lo, hi, h - pad.b, pad.t);
    const line = pathFrom(x, y, xlo, xhi, lo, hi, w, h, pad);
    const x0 = scale(xlo, xlo, xhi, pad.l, w - pad.r);
    const x1 = scale(xhi, xlo, xhi, pad.l, w - pad.r);
    const area = `M${x0} ${zero} ${line.replace("M", "L")} L${x1} ${zero} Z`;
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg" preserveAspectRatio="none">
      <defs><linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
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
                   markerId = null }) {
    const { sx, sy } = trackScale(x, y, w, h);
    let g = "";
    for (let i = 0; i < x.length - 1; i++) {
      const c = colors[faster[i] === 1 ? 0 : 1];
      g += `<line x1="${sx(x[i]).toFixed(1)}" y1="${sy(y[i]).toFixed(1)}" x2="${sx(x[i + 1]).toFixed(1)}" y2="${sy(y[i + 1]).toFixed(1)}" stroke="${c}" stroke-width="${lineWidth}" stroke-linecap="round"/>`;
    }
    if (markerId) {
      g += `<circle id="${markerId}" r="7" fill="#fff" stroke="#0b0b11" stroke-width="2.5" opacity="0"/>`;
    }
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-track">${g}</svg>`;
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
                 fmt = (v) => v }) {
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
    return `<svg ${NS} viewBox="0 0 ${w} ${h}" class="ct-svg">${g}</svg>`;
  }

  /* Side-profile modern F1 car, hand-drawn. Reused by the dashboard hero and
     the scroll-progress marker; wheel rims carry a .rim class so CSS can spin
     them. Pure vector — crisp at any size, no external assets. */
  function car(cls = "") {
    return `<svg ${NS} viewBox="0 0 540 150" class="car-svg ${cls}" aria-hidden="true">
      <ellipse cx="268" cy="128" rx="240" ry="9" fill="rgba(0,0,0,0.5)"/>

      <!-- rear wing -->
      <path d="M436 52 L514 52 L514 61 L436 61 Z" fill="#0f0f17"/>
      <path d="M438 55 L512 55 L512 58 L438 58 Z" fill="#e10600"/>
      <rect x="506" y="45" width="9" height="60" rx="3" fill="#15151e"/>
      <path d="M468 61 L474 90 L480 90 L476 61 Z" fill="#15151e"/>
      <path d="M472 96 L512 96 L512 102 L472 102 Z" fill="#0f0f17"/>

      <!-- floor -->
      <path d="M60 106 L455 106 L460 114 L66 114 Z" fill="#0b0b11"/>

      <!-- nose + monocoque -->
      <path d="M24 100 C80 94 130 88 180 85 L268 82 L268 106 L34 106 Z" fill="#e10600"/>
      <path d="M24 100 C80 96 130 91 180 88 L188 106 L34 106 Z" fill="#a50500"/>

      <!-- sidepod + engine cover -->
      <path d="M268 82 L352 84 C408 88 436 94 448 100 L448 106 L268 106 Z" fill="#e10600"/>
      <path d="M300 84 L352 86 C400 89 430 95 446 100 L448 106 L300 106 Z" fill="#8f0400"/>

      <!-- cockpit + halo -->
      <path d="M300 82 C304 70 328 70 332 82 Z" fill="#15151e"/>
      <path d="M282 80 C294 60 336 58 350 76" fill="none" stroke="#2e2e3a" stroke-width="5" stroke-linecap="round"/>
      <path d="M316 60 L316 82" stroke="#2e2e3a" stroke-width="4"/>

      <!-- airbox + engine hump -->
      <path d="M332 78 C340 62 362 62 372 72 C404 78 428 88 440 96 L440 104 L332 104 Z" fill="#e10600"/>
      <path d="M340 74 C348 64 360 64 368 72 L372 78 L340 78 Z" fill="#15151e"/>

      <!-- livery accents -->
      <path d="M180 88 L268 85 L268 89 L180 92 Z" fill="#f2f0ed"/>
      <path d="M352 86 C400 90 428 95 444 100 L440 104 C424 98 396 93 350 90 Z" fill="#f2f0ed"/>
      <text x="252" y="102" font-family="Titillium Web, sans-serif" font-size="22"
            font-style="italic" font-weight="900" fill="#f2f0ed">5</text>

      <!-- front wing -->
      <path d="M8 108 L128 108 L128 113 L8 113 Z" fill="#0f0f17"/>
      <path d="M14 101 L118 104 L118 107 L14 104 Z" fill="#15151e"/>
      <rect x="6" y="94" width="7" height="21" rx="2" fill="#15151e"/>

      <!-- wheels -->
      <g>
        <circle cx="152" cy="97" r="28" fill="#141419"/>
        <circle cx="152" cy="97" r="28" fill="none" stroke="#000" stroke-width="3"/>
        <g class="rim">
          <circle cx="152" cy="97" r="13" fill="#23232c"/>
          <g stroke="#9ea2ab" stroke-width="3" stroke-linecap="round">
            <line x1="152" y1="86" x2="152" y2="108"/>
            <line x1="141" y1="97" x2="163" y2="97"/>
            <line x1="144" y1="89" x2="160" y2="105"/>
            <line x1="160" y1="89" x2="144" y2="105"/>
          </g>
          <circle cx="152" cy="97" r="4.5" fill="#e10600"/>
        </g>
      </g>
      <g>
        <circle cx="408" cy="96" r="29" fill="#141419"/>
        <circle cx="408" cy="96" r="29" fill="none" stroke="#000" stroke-width="3"/>
        <g class="rim">
          <circle cx="408" cy="96" r="13.5" fill="#23232c"/>
          <g stroke="#9ea2ab" stroke-width="3" stroke-linecap="round">
            <line x1="408" y1="85" x2="408" y2="107"/>
            <line x1="397" y1="96" x2="419" y2="96"/>
            <line x1="400" y1="88" x2="416" y2="104"/>
            <line x1="416" y1="88" x2="400" y2="104"/>
          </g>
          <circle cx="408" cy="96" r="4.5" fill="#e10600"/>
        </g>
      </g>
    </svg>`;
  }

  return { lines, delta, track, trackScale, bars, lights, countUp, car };
})();
