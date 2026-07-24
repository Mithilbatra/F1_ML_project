/* Telemetry head-to-head + Strategy tabs. Talks to the /api/tel/* endpoints
   backed by FastF1. Session loads are slow the first time, hence the notices. */

"use strict";

(function () {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const SESSIONS = [["Q", "Qualifying"], ["R", "Race"], ["FP1", "Practice 1"],
                    ["FP2", "Practice 2"], ["FP3", "Practice 3"]];
  const fmtLap = (s) => s == null ? "—" : `${Math.floor(s / 60)}:${(s % 60).toFixed(3).padStart(6, "0")}`;

  async function getJSON(url) {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `${r.status}`);
    return d;
  }

  let years = [];
  const eventCache = {};

  async function seasons() {
    if (!years.length) years = (await getJSON("/api/seasons")).years;
    return years;
  }
  async function events(year) {
    if (!eventCache[year]) eventCache[year] = (await getJSON(`/api/tel/events/${year}`)).events;
    return eventCache[year];
  }
  const fillYears = (sel) => sel.innerHTML = years.map((y) =>
    `<option value="${y}">${y}</option>`).join("");
  const fillRounds = (sel, evs) => sel.innerHTML = evs.map((e) =>
    `<option value="${e.round}">R${e.round} — ${esc(e.event.replace(" Grand Prix", " GP"))}</option>`).join("");

  /* ------------------------------------------------------------ telemetry */

  let telInit = false;
  async function initTelemetry() {
    if (telInit) return; telInit = true;
    await seasons();
    fillYears($("#tel-year"));
    $("#tel-session").innerHTML = SESSIONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    $("#tel-year").value = years[years.length - 1];
    await refreshTelRounds();
    $("#tel-year").addEventListener("change", refreshTelRounds);
    $("#tel-round").addEventListener("change", refreshTelDrivers);
    $("#tel-session").addEventListener("change", refreshTelDrivers);
    $("#tel-run").addEventListener("click", runH2H);
  }
  async function refreshTelRounds() {
    const evs = await events(+$("#tel-year").value);
    fillRounds($("#tel-round"), evs);
    await refreshTelDrivers();
  }
  async function refreshTelDrivers() {
    const y = $("#tel-year").value, r = $("#tel-round").value, sc = $("#tel-session").value;
    $("#tel-status").textContent = "Loading drivers…";
    try {
      const d = await getJSON(`/api/tel/session/${y}/${r}/${sc}`);
      const opts = d.drivers.map((x) => `<option value="${x.abbr}">${x.abbr} — ${esc(x.name)}</option>`).join("");
      $("#tel-d1").innerHTML = opts; $("#tel-d2").innerHTML = opts;
      if (d.drivers[0]) $("#tel-d1").value = d.drivers[0].abbr;
      if (d.drivers[1]) $("#tel-d2").value = d.drivers[1].abbr;
      $("#tel-status").textContent = "";
    } catch (e) { $("#tel-status").textContent = "No data for this session."; }
  }

  async function runH2H() {
    const y = $("#tel-year").value, r = $("#tel-round").value, sc = $("#tel-session").value;
    const d1 = $("#tel-d1").value, d2 = $("#tel-d2").value;
    if (d1 === d2) { $("#tel-status").textContent = "Pick two different drivers."; return; }
    const btn = $("#tel-run"); btn.disabled = true;
    $("#tel-status").textContent = "";
    $("#tel-result").innerHTML =
      `<div class="card">${Charts.lights("Loading telemetry — first time can take ~20s")}</div>`;
    try {
      const h = await getJSON(`/api/tel/h2h/${y}/${r}/${sc}?d1=${d1}&d2=${d2}`);
      renderH2H(h);
      $("#tel-status").textContent = "";
      const fastest = h.d1.lap_time <= h.d2.lap_time ? h.d1 : h.d2;
      window.radio && window.radio(`${fastest.abbr} is fastest`,
        `${fmtLap(fastest.lap_time)} at ${h.event}`, fastest.color);
    } catch (e) {
      $("#tel-result").innerHTML = "";
      $("#tel-status").textContent = "Error: " + e.message;
    }
    finally { btn.disabled = false; }
  }

  function renderH2H(h) {
    const { d1, d2 } = h;
    const gap = (d2.lap_time != null && d1.lap_time != null)
      ? (d2.lap_time - d1.lap_time) : null;
    const leader = gap == null ? null : (gap >= 0 ? d1 : d2);

    // broadcast timing: the faster lap gets the purple "session best" mark
    const lapWinner = (d1.lap_time != null && d2.lap_time != null)
      ? (d1.lap_time <= d2.lap_time ? "d1" : "d2") : null;
    const card = (d, key) => `<div class="tel-driver" style="--dc:${d.color}">
      <div class="td-abbr">${esc(d.abbr)}</div>
      <div class="td-team">${esc(d.name)} · ${esc(d.team)}</div>
      <div class="td-lap ${lapWinner === key ? "tc-purple" : ""}">${fmtLap(d.lap_time)}</div>
      <div class="td-meta">${d.compound ? esc(d.compound) + " · " : ""}${d.top_speed ? d.top_speed.toFixed(0) + " km/h top" : ""}</div>
    </div>`;

    const head = `<div class="card"><div class="card-title">${esc(h.event)} · ${esc(h.session)} — fastest laps</div>
      <div class="tel-head">
        ${card(d1, "d1")}
        <div class="tel-gap"><div class="g-val">${gap == null ? "—" : (Math.abs(gap).toFixed(3) + "s")}</div>
          <div class="g-lbl">${leader ? esc(leader.abbr) + " faster" : "gap"}</div></div>
        ${card(d2, "d2")}
      </div></div>`;

    const trackCard = `<div class="card"><div class="card-title">Track dominance</div>
      <div class="tel-legend">
        <span><span class="sw" style="background:${d1.color}"></span>${esc(d1.abbr)} faster</span>
        <span><span class="sw" style="background:${d2.color}"></span>${esc(d2.abbr)} faster</span>
      </div>
      ${Charts.track({ x: h.track.x, y: h.track.y, faster: h.track.faster,
                       colors: [d1.color, d2.color], markerId: "tel-track-marker" })}
    </div>`;

    const wrap = (svg) => `<div class="chart-hover">${svg}<div class="xh-line"></div></div>`;
    const speedCard = `<div class="card"><div class="card-title">Speed (km/h) over the lap</div>
      <div class="tel-readout" id="tel-readout"><span class="ro-hint">Hover the charts to scrub the lap — the dot on the track map follows.</span></div>
      ${wrap(Charts.lines({ x: h.distance, w: 680, h: 200, ylabel: "km/h", series: [
        { y: h.traces.d1.speed, color: d1.color, width: 2 },
        { y: h.traces.d2.speed, color: d2.color, width: 2 }] }))}
      <div class="card-title" style="margin:14px 0 6px">Time delta — below the line, ${esc(d2.abbr)} is ahead</div>
      ${wrap(Charts.delta({ x: h.distance, y: h.delta, w: 680, h: 130, posColor: d1.color, negColor: d2.color }))}
      <div class="card-title" style="margin:14px 0 6px">Throttle &amp; brake</div>
      ${wrap(Charts.lines({ x: h.distance, w: 680, h: 150, ylabel: "%", yMin: 0, yMax: 105, series: [
        { y: h.traces.d1.throttle, color: d1.color, width: 1.6 },
        { y: h.traces.d2.throttle, color: d2.color, width: 1.6 },
        { y: h.traces.d1.brake, color: d1.color, width: 1.4, dash: "3 3" },
        { y: h.traces.d2.brake, color: d2.color, width: 1.4, dash: "3 3" }] }))}
      <div class="tel-legend" style="margin-top:6px"><span>solid = throttle</span><span>dashed = brake</span></div>
    </div>`;

    const sectors = `<div class="card"><div class="card-title">Sectors</div>
      ${[0, 1, 2].map((i) => {
        const a = d1.sectors[i], b = d2.sectors[i];
        const aBest = a != null && b != null && a <= b, bBest = a != null && b != null && b < a;
        return `<div class="sector-row">
          <span class="s-name">S${i + 1}</span>
          <span class="sector-cell ${aBest ? "tc-green" : ""}">${a == null ? "—" : a.toFixed(3)}</span>
          <span class="sector-cell ${bBest ? "tc-green" : ""}">${b == null ? "—" : b.toFixed(3)}</span>
        </div>`;
      }).join("")}
      <div class="tel-legend" style="margin-top:8px"><span>${esc(d1.abbr)}</span><span>${esc(d2.abbr)}</span> · green = faster sector</div>
    </div>`;

    $("#tel-result").innerHTML = head +
      `<div class="tel-grid"><div>${trackCard}${sectors}</div><div>${speedCard}</div></div>`;
    attachScrubber(h);
  }

  /* Crosshair scrubber: hovering any lap chart moves a cursor across all of
     them, shows live values, and drives a dot around the dominance map —
     broadcast-telemetry style. */
  function attachScrubber(h) {
    const wraps = [...document.querySelectorAll("#tel-result .chart-hover")];
    const marker = document.getElementById("tel-track-marker");
    const readout = $("#tel-readout");
    if (!wraps.length || !readout) return;
    const scale = Charts.trackScale(h.track.x, h.track.y);
    const n = h.distance.length;
    const PAD_L = 42 / 680, PAD_R = 12 / 680;  // chart plot-area insets
    const hint = readout.innerHTML;
    let raf = null;

    function update(frac) {
      let f = (frac - PAD_L) / (1 - PAD_L - PAD_R);
      f = Math.max(0, Math.min(1, f));
      const i = Math.round(f * (n - 1));
      const left = ((PAD_L + f * (1 - PAD_L - PAD_R)) * 100).toFixed(2) + "%";
      for (const w of wraps) {
        w.classList.add("active");
        w.querySelector(".xh-line").style.left = left;
      }
      const s1 = h.traces.d1.speed[i], s2 = h.traces.d2.speed[i];
      const dl = h.delta[i];
      const ahead = dl >= 0 ? h.d2.abbr : h.d1.abbr;
      readout.innerHTML =
        `<span class="ro-item">${(h.distance[i] / 1000).toFixed(2)} km</span>` +
        `<span class="ro-item" style="color:${h.d1.color}">${esc(h.d1.abbr)} <strong>${s1.toFixed(0)}</strong></span>` +
        `<span class="ro-item" style="color:${h.d2.color}">${esc(h.d2.abbr)} <strong>${s2.toFixed(0)}</strong> km/h</span>` +
        `<span class="ro-item">Δ <strong>${Math.abs(dl).toFixed(3)}s</strong> ${esc(ahead)} ahead</span>`;
      if (marker) {
        marker.setAttribute("cx", scale.sx(h.track.x[i]).toFixed(1));
        marker.setAttribute("cy", scale.sy(h.track.y[i]).toFixed(1));
        marker.setAttribute("fill", h.track.faster[i] === 1 ? h.d1.color : h.d2.color);
        marker.setAttribute("opacity", "1");
      }
    }

    for (const w of wraps) {
      w.addEventListener("mousemove", (e) => {
        const r = w.getBoundingClientRect();
        const frac = (e.clientX - r.left) / r.width;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => update(frac));
      });
      w.addEventListener("mouseleave", () => {
        wraps.forEach((x) => x.classList.remove("active"));
        if (marker) marker.setAttribute("opacity", "0");
        readout.innerHTML = hint;
      });
    }
  }

  /* ------------------------------------------------------------- strategy */

  let stratInit = false;
  async function initStrategy() {
    if (stratInit) return; stratInit = true;
    await seasons();
    fillYears($("#strat-year"));
    $("#strat-year").value = years[years.length - 1];
    await refreshStratRounds();
    $("#strat-year").addEventListener("change", refreshStratRounds);
    $("#strat-run").addEventListener("click", runStrategy);
  }
  async function refreshStratRounds() {
    const evs = await events(+$("#strat-year").value);
    fillRounds($("#strat-round"), evs);
  }

  async function runStrategy() {
    const y = $("#strat-year").value, r = $("#strat-round").value;
    const btn = $("#strat-run"); btn.disabled = true;
    $("#strat-status").textContent = "";
    $("#strat-result").innerHTML =
      `<div class="card">${Charts.lights("Loading race — first time can take ~30s")}</div>`;
    try {
      const [strat, pace] = await Promise.all([
        getJSON(`/api/tel/strategy/${y}/${r}`),
        getJSON(`/api/tel/pace/${y}/${r}`),
      ]);
      renderStrategy(strat, pace);
      $("#strat-status").textContent = "";
      if (pace.drivers && pace.drivers[0]) {
        window.radio && window.radio(`${pace.drivers[0].abbr} had the race pace`,
          `fastest median clean lap · ${esc(strat.event)}`, pace.drivers[0].color);
      }
    } catch (e) {
      $("#strat-result").innerHTML = "";
      $("#strat-status").textContent = "Error: " + e.message;
    }
    finally { btn.disabled = false; }
  }

  function renderStrategy(strat, pace) {
    const total = strat.total_laps;
    const rows = strat.drivers.map((d) => {
      const segs = d.stints.map((s) => {
        const w = (s.laps / total) * 100;
        return `<div class="strat-seg" style="width:${w}%;background:${s.color}" title="${esc(s.compound)} L${s.start}-${s.end}">${s.laps >= 4 ? s.compound[0] : ""}</div>`;
      }).join("");
      return `<div class="strat-driver"><span class="sd-abbr">${esc(d.abbr)}</span><div class="strat-bar">${segs}</div></div>`;
    }).join("");

    const stratCard = `<div class="card"><div class="card-title">${esc(strat.event)} — tyre strategy (${total} laps)</div>
      ${rows}
      <div class="strat-axis"><span></span><span>Lap 1 → ${total}</span></div>
      <div class="tel-legend" style="margin-top:10px">
        <span><span class="sw" style="background:#e10600"></span>Soft</span>
        <span><span class="sw" style="background:#ffd12e"></span>Medium</span>
        <span><span class="sw" style="background:#f0f0f0"></span>Hard</span>
        <span><span class="sw" style="background:#43b02a"></span>Inter</span>
        <span><span class="sw" style="background:#0067ad"></span>Wet</span>
      </div></div>`;

    const paceRows = pace.drivers.map((r) => ({
      label: r.abbr, value: r.gap, color: r.color,
      sub: `+${r.gap.toFixed(3)}s`,
    }));
    const maxGap = Math.max(...pace.drivers.map((r) => r.gap), 0.1);
    const paceCard = `<div class="card"><div class="card-title">Race pace — gap to fastest median clean lap</div>
      ${Charts.bars({ rows: paceRows, w: 640, maxValue: maxGap, fmt: () => "" })}
      <div class="section-note" style="padding:0;margin-top:8px">Median of each driver's clean laps (in/out &amp; safety-car laps removed). Lower is faster.</div>
    </div>`;

    $("#strat-result").innerHTML = stratCard + paceCard;
  }

  /* ----------------------------------------------------------------- init */

  function hook(view, fn) {
    document.querySelectorAll(`.tab[data-view="${view}"]`).forEach((t) =>
      t.addEventListener("click", () => fn().catch((e) =>
        console.error(view, e))));
  }
  function start() { hook("telemetry", initTelemetry); hook("strategy", initStrategy); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
