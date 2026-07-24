/* Race-Weekend hub + Fantasy optimiser + driver-profile modal. */

"use strict";

(function () {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TEAM_COLORS = {
    "McLaren": "#ff8000", "Ferrari": "#e80020", "Red Bull Racing": "#3671c6",
    "Mercedes": "#27f4d2", "Aston Martin": "#229971", "Alpine": "#0093cc",
    "Williams": "#64c4ff", "Racing Bulls": "#6692ff", "Kick Sauber": "#52e252",
    "Haas F1 Team": "#b6babd",
  };
  const tc = (t) => TEAM_COLORS[t] || "#888";
  const dlink = (name, year) =>
    `<span class="driver-link" data-driver="${esc(name)}" data-year="${year}">${esc(name)}</span>`;

  async function getJSON(url) {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `${r.status}`);
    return d;
  }

  /* ---------------------------------------------------------------- hub */

  let wkTimer = null, wkLoaded = false;
  async function initWeekend() {
    if (wkLoaded) return; wkLoaded = true;
    $("#weekend-result").innerHTML =
      `<div class="card">${Charts.lights("Assembling the race weekend…")}</div>`;
    try {
      const d = await getJSON("/api/hub");
      renderHub(d);
    } catch (e) {
      $("#weekend-result").innerHTML = `<div class="card"><div class="placeholder">Could not load: ${esc(e.message)}</div></div>`;
    }
  }

  function renderHub(d) {
    const nr = d.next_race, season = d.forecast.based_on_season;
    const localFmt = (iso) => new Date(iso).toLocaleString(undefined,
      { weekday: "short", hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });

    let hero = `<div class="card"><div class="placeholder">No upcoming race found.</div></div>`;
    if (nr) {
      const sessions = nr.sessions.map((s) =>
        `<div class="wk-sess"><span class="ws-name">${esc(s.name)}</span><span>${localFmt(s.utc)}</span></div>`).join("");
      hero = `<div class="card">
        <div class="card-title">Next Grand Prix</div>
        <div class="wk-hero">
          <div><div style="font-size:24px;font-weight:900;font-style:italic">${esc(nr.event)}</div>
            <div style="color:var(--muted);font-size:13px">Round ${nr.round} · ${esc(nr.location)}, ${esc(nr.country)} · ${nr.year}</div></div>
          <div class="wk-count" id="wk-count"></div>
        </div>
        <div class="card-title" style="margin:16px 0 6px">Session schedule <span style="text-transform:none;letter-spacing:0;color:var(--muted);font-weight:400">(your local time)</span></div>
        <div class="wk-sessions">${sessions}</div>
      </div>`;
    }

    // forecast with form + circuit columns
    const fc = d.forecast;
    const fcHead = `<div class="fc-cols fc-head"><span></span><span>Driver</span><span style="text-align:right">Form</span><span style="text-align:right">Here</span><span style="text-align:right">Verdict</span></div>`;
    const fcRows = fc.projection.map((r, i) => `
      <div class="fc-cols">
        <span class="fc-mini">${i + 1}</span>
        <div class="driver-cell"><span class="team-bar" style="background:${tc(r.team)}"></span>${dlink(r.driver, season)}</div>
        <span class="fc-mini">${(r.form_prob * 100).toFixed(0)}%</span>
        <span class="fc-mini">${r.circuit_podium_rate ? (r.circuit_podium_rate * 100).toFixed(0) + "%" : "—"}</span>
        <span class="prob-val" style="color:var(--red)">${(r.prob * 100).toFixed(0)}%</span>
      </div>`).join("");
    const forecast = `<div class="card">
      <div class="card-title">Podium projection${fc.event ? " — " + esc(fc.event) : ""}</div>
      <div class="section-note" style="padding:0;margin-bottom:8px">Recent <strong>form</strong> blended with each driver's podium rate <strong>here</strong> (${fc.has_circuit_history ? "circuit history applied" : "no circuit history yet"}). Based on ${season}.</div>
      ${fcHead}${fcRows}
    </div>`;

    // circuit guide (racing line) — lazy
    const guide = `<div class="card"><div class="card-title">Circuit guide — racing line</div>
      <div class="guide-canvas-wrap"><canvas id="hub-guide-canvas" width="360" height="360"></canvas></div>
      <div class="guide-stats" id="hub-guide-stats"><span>Tracing the lap…</span></div></div>`;

    // circuit history editions
    let history = "";
    if (d.history && d.history.editions.length) {
      const eds = d.history.editions.map((e) => `
        <div class="edition"><span class="ed-year">${e.year}</span>
          <div><div class="driver-cell"><span class="team-bar" style="background:${tc(e.winner_team)}"></span>${e.winner ? dlink(e.winner, e.year) : "—"}</div>
            <div class="ed-pole">Pole: ${esc(e.pole || "—")}</div></div>
          <span class="status-chip">WIN</span></div>`).join("");
      history = `<div class="card"><div class="card-title">Recent winners here</div>${eds}</div>`;
    }

    // fantasy compact
    let fantasy = "";
    if (d.fantasy && !d.fantasy.error) {
      const picks = d.fantasy.drivers.map((x) =>
        `<span class="status-chip ${x.captain ? "hit" : ""}" style="margin:2px">${esc(x.name.split(" ").pop())}${x.captain ? " (C)" : ""}</span>`).join("");
      const cons = d.fantasy.constructors.map((c) => `<span class="status-chip" style="margin:2px">${esc(c.name)}</span>`).join("");
      fantasy = `<div class="card"><div class="card-title">Fantasy picks · $${d.fantasy.cost}M</div>
        <div style="margin-bottom:6px">${picks}</div><div>${cons}</div>
        <div class="section-note" style="padding:0;margin-top:8px">Projected ${d.fantasy.projected_points} pts — full board on the Fantasy tab.</div></div>`;
    }

    // teammate battles
    let battles = "";
    if (d.battles && d.battles.length) {
      const rows = d.battles.map((b) => {
        const [ra, rb] = b.race, tot = ra + rb || 1;
        return `<div class="battle"><span class="bt-team">${esc(b.team)}</span>
          <div class="battle-bar" title="${esc(b.a)} ${ra}-${rb} ${esc(b.b)} (race)">
            <div class="bb-a" style="width:${ra / tot * 100}%">${esc(b.a.split(" ").pop())} ${ra}</div>
            <div class="bb-b" style="width:${rb / tot * 100}%">${rb} ${esc(b.b.split(" ").pop())}</div>
          </div></div>`;
      }).join("");
      battles = `<div class="card"><div class="card-title">Teammate race head-to-head · ${season}</div>${rows}</div>`;
    }

    $("#weekend-result").innerHTML = hero +
      `<div class="hub-grid"><div>${forecast}${history}</div><div>${guide}${fantasy}${battles}</div></div>`;

    if (nr) {
      startCountdown(nr.race_utc);
      loadCircuitGuide(nr.event);
      const top = d.forecast.projection[0];
      if (top) window.radio && window.radio(`${nr.event}`,
        `${esc(top.driver)} the podium favourite · ${(top.prob * 100).toFixed(0)}%`,
        tc(top.team));
    }
  }

  async function loadCircuitGuide(event) {
    try {
      const d = await getJSON(`/api/circuit-guide?event=${encodeURIComponent(event)}`);
      if (!d.available) { $("#hub-guide-stats").innerHTML = "<span>No telemetry available for this circuit yet.</span>"; return; }
      drawGuide(d.guide);
    } catch (e) {
      const el = $("#hub-guide-stats");
      if (el) el.innerHTML = `<span>Circuit guide unavailable (${esc(e.message)}).</span>`;
    }
  }

  let hubLapRAF = null;
  function speedColor(t) {
    return `rgb(${Math.round(60 + 195 * t)},${Math.round(194 * (1 - t))},${Math.round(30 * (1 - t))})`;
  }

  function drawGuide(g) {
    const canvas = $("#hub-guide-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const line = g.racing_line, speed = g.speed_kmh, N = line.length;
    const xs = line.map((p) => p[0]), ys = line.map((p) => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const span = Math.max(x1 - x0, y1 - y0), pad = 18;
    const sx = (v) => pad + (v - x0) / span * (canvas.width - 2 * pad);
    const sy = (v) => pad + (v - y0) / span * (canvas.height - 2 * pad);
    const smin = Math.min(...speed), smax = Math.max(...speed) + 1e-6;
    const norm = (i) => (speed[i] - smin) / (smax - smin);

    function drawTrack() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 3; ctx.lineCap = "round";
      for (let i = 0; i < N; i++) {
        const j = (i + 1) % N;
        ctx.strokeStyle = speedColor(norm(i));
        ctx.beginPath(); ctx.moveTo(sx(line[i][0]), sy(line[i][1])); ctx.lineTo(sx(line[j][0]), sy(line[j][1])); ctx.stroke();
      }
    }

    // onboard hot-lap: a glowing dot laps the circuit, quick on straights,
    // slow through the corners
    let pos = 0;
    if (hubLapRAF) cancelAnimationFrame(hubLapRAF);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function frame() {
      if (!document.getElementById("hub-guide-canvas")) return;  // re-rendered
      drawTrack();
      const i = Math.floor(pos) % N, t = norm(i);
      const px = sx(line[i][0]), py = sy(line[i][1]);
      ctx.save();
      ctx.shadowBlur = 14; ctx.shadowColor = speedColor(t);
      ctx.fillStyle = "#fff";
      ctx.beginPath(); ctx.arc(px, py, 4.5, 0, 7); ctx.fill();
      ctx.restore();
      pos = (pos + 0.6 + 3.4 * t) % N;   // pace by local speed
      hubLapRAF = requestAnimationFrame(frame);
    }
    if (reduce) drawTrack(); else frame();

    $("#hub-guide-stats").innerHTML =
      `<span>Corners <strong>${g.n_corners}</strong></span>` +
      `<span>Ideal lap <strong>${g.lap_time_str}</strong></span>` +
      `<span>Top <strong>${g.v_max_kmh.toFixed(0)}</strong> km/h</span>` +
      `<span style="color:var(--muted)">from ${g.source_year} pole (${esc(g.pole_driver)})</span>`;
  }

  function startCountdown(raceUtc) {
    if (wkTimer) clearInterval(wkTimer);
    const target = new Date(raceUtc).getTime();
    const tick = () => {
      const el = $("#wk-count");
      if (!el) { clearInterval(wkTimer); return; }
      let s = Math.max(0, Math.floor((target - Date.now()) / 1000));
      const days = Math.floor(s / 86400); s -= days * 86400;
      const hrs = Math.floor(s / 3600); s -= hrs * 3600;
      const mins = Math.floor(s / 60); const secs = s - mins * 60;
      const u = (n, l) => `<div class="u"><div class="n">${String(n).padStart(2, "0")}</div><div class="l">${l}</div></div>`;
      el.innerHTML = u(days, "days") + u(hrs, "hrs") + u(mins, "min") + u(secs, "sec");
    };
    tick(); wkTimer = setInterval(tick, 1000);
  }

  /* ----------------------------------------------------- driver profile */

  async function openDriver(name, year) {
    const host = document.createElement("div");
    host.className = "modal-backdrop";
    host.innerHTML = `<div class="modal"><div class="modal-body"><div class="placeholder">Loading ${esc(name)}…</div></div></div>`;
    host.addEventListener("click", (e) => { if (e.target === host) host.remove(); });
    document.body.appendChild(host);
    try {
      const p = await getJSON(`/api/driver?year=${year}&name=${encodeURIComponent(name)}`);
      const tm = p.teammate;
      const tmHtml = tm ? `<div class="card-title" style="margin-top:6px">Teammate H2H vs ${esc(tm.name)}</div>
        <div class="battle"><span class="bt-team">Qualifying</span><div class="battle-bar">
          <div class="bb-a" style="width:${tm.quali[0] / (tm.quali[0] + tm.quali[1] || 1) * 100}%">${tm.quali[0]}</div>
          <div class="bb-b" style="width:${tm.quali[1] / (tm.quali[0] + tm.quali[1] || 1) * 100}%">${tm.quali[1]}</div></div></div>
        <div class="battle"><span class="bt-team">Race</span><div class="battle-bar">
          <div class="bb-a" style="width:${tm.race[0] / (tm.race[0] + tm.race[1] || 1) * 100}%">${tm.race[0]}</div>
          <div class="bb-b" style="width:${tm.race[1] / (tm.race[0] + tm.race[1] || 1) * 100}%">${tm.race[1]}</div></div></div>` : "";
      host.querySelector(".modal").innerHTML = `
        <span class="modal-close">&times;</span>
        <div class="modal-head" style="--dc:${tc(p.team)}">
          ${p.headshot ? `<img src="${esc(p.headshot)}" alt="" onerror="this.style.display='none'">` : ""}
          <div><div class="mh-name">${esc(p.driver)}</div><div class="mh-team">${esc(p.team)} · ${p.year}</div></div>
        </div>
        <div class="modal-body">
          <div class="mstat-grid">
            <div class="mstat"><div class="n">P${p.position}</div><div class="l">Champ</div></div>
            <div class="mstat"><div class="n">${p.points}</div><div class="l">Points</div></div>
            <div class="mstat"><div class="n">${p.wins}</div><div class="l">Wins</div></div>
            <div class="mstat"><div class="n">${p.podiums}</div><div class="l">Podiums</div></div>
            <div class="mstat"><div class="n">P${p.best_finish ?? "—"}</div><div class="l">Best</div></div>
            <div class="mstat"><div class="n">${p.avg_finish ?? "—"}</div><div class="l">Avg fin</div></div>
          </div>
          <div class="section-note" style="padding:0;margin-bottom:6px">Best result: P${p.best_finish} at ${esc(p.best_finish_event || "—")}</div>
          ${tmHtml}
        </div>`;
      host.querySelector(".modal-close").addEventListener("click", () => host.remove());
    } catch (e) {
      host.querySelector(".modal-body").innerHTML = `<div class="placeholder">${esc(e.message)}</div>`;
    }
  }

  // delegated: any [data-driver] element opens a profile
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-driver]");
    if (el) openDriver(el.dataset.driver, el.dataset.year || 2025);
  });

  /* -------------------------------------------------------------- fantasy */

  let fanInit = false;
  function initFantasy() {
    if (fanInit) return; fanInit = true;
    $("#fan-run").addEventListener("click", runFantasy);
    runFantasy();
  }
  async function runFantasy() {
    const budget = $("#fan-budget").value;
    const btn = $("#fan-run"); btn.disabled = true;
    $("#fan-status").textContent = "Optimising…";
    try {
      const d = await getJSON(`/api/fantasy?budget=${budget}`);
      if (d.error) throw new Error(d.error);
      renderFantasy(d);
      $("#fan-status").textContent = "";
      window.radio && window.radio("Team locked in",
        `${esc(d.captain)} on captain · ${d.projected_points} projected pts`, tc("McLaren"));
    } catch (e) { $("#fan-status").textContent = e.message; }
    finally { btn.disabled = false; }
  }
  function renderFantasy(d) {
    const pick = (x, isCap) => `<div class="fan-pick ${isCap ? "cap" : ""}" style="--dc:${tc(x.team || x.name)}">
      <div class="fp-name">${x.team ? dlink(x.name, d.season) : esc(x.name)}${isCap ? '<span class="fan-cap-badge">2× CAPTAIN</span>' : ""}</div>
      <div class="fp-meta">${x.team ? esc(x.team) + " · " : ""}$${x.price}M</div>
      <div class="fp-pts">${x.proj} <span style="font-size:11px;color:var(--muted)">proj pts</span></div></div>`;
    const team = `<div class="card">
      <div class="card-title">Optimal team — $${d.cost}M of $${d.budget}M · projected ${d.projected_points} pts</div>
      <div style="font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Drivers</div>
      <div class="fan-team">${d.drivers.map((x) => pick(x, x.captain)).join("")}</div>
      <div style="font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:14px 0 8px">Constructors</div>
      <div class="fan-team">${d.constructors.map((x) => pick(x, false)).join("")}</div></div>`;
    const valRows = d.all_drivers.slice(0, 12).map((x) => ({
      label: x.name.split(" ").pop().slice(0, 10), value: x.proj / x.price,
      color: tc(x.team), sub: `$${x.price}M · ${x.proj}pt`,
    }));
    const valueBoard = `<div class="card"><div class="card-title">Driver value board — projected points per $M</div>
      ${Charts.bars({ rows: valRows, w: 640, fmt: (v) => v.toFixed(2) })}
      <div class="section-note" style="padding:0;margin-top:8px">Prices approximated from championship standing; projections from recent finishing form.</div></div>`;
    $("#fan-result").innerHTML = team + valueBoard;
  }

  /* ----------------------------------------------------------------- init */

  function hook(view, fn) {
    document.querySelectorAll(`.tab[data-view="${view}"]`).forEach((t) =>
      t.addEventListener("click", () => { try { fn(); } catch (e) { console.error(e); } }));
  }
  function start() { hook("weekend", initWeekend); hook("fantasy", initFantasy); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
