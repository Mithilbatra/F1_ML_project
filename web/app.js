/* Pit Wall front-end: plain JS, no build step. Talks to the Flask API and
   mirrors the f1ml CLI in the console view. */

"use strict";

const TEAM_COLORS = {
  "McLaren": "#ff8000",
  "Ferrari": "#e80020",
  "Red Bull Racing": "#3671c6",
  "Mercedes": "#27f4d2",
  "Aston Martin": "#229971",
  "Alpine": "#0093cc",
  "Williams": "#64c4ff",
  "Racing Bulls": "#6692ff",
  "Kick Sauber": "#52e252",
  "Haas F1 Team": "#b6babd",
};

const FEATURE_LABELS = {
  QualyPos: "Qualifying position",
  GridPosition: "Grid position",
  QualyGapToPole: "Qualifying gap to pole",
  IsStreetCircuit: "Street circuit",
  RacePos_Last_1: "Finish — last race",
  RacePos_Last_2: "Finish — 2 races ago",
  RacePos_Last_3: "Finish — 3 races ago",
  driver_avg_points_last_3: "Avg points, last 3",
  driver_avg_finish_last_3: "Avg finish, last 3",
  driver_avg_qualy_last_3: "Avg qualifying, last 3",
  season_points: "Season points to date",
  dnfs_season: "DNFs this season",
  team_avg_points_last_3: "Team form, last 3",
};

const state = {
  year: null,
  years: [],
  view: "dashboard",
  raceCache: {},
  selectedRound: null,
};

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const teamColor = (t) => TEAM_COLORS[t] || "#666";
const featLabel = (f) =>
  FEATURE_LABELS[f] || (f.startsWith("Team_") ? `Team: ${f.slice(5)}` : f);

async function getJSON(url) {
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}

/* ------------------------------------------------------------ navigation */

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) =>
    v.classList.toggle("hidden", v.id !== `view-${view}`));
  const loader = { dashboard: loadDashboard, races: loadRaces,
                   standings: loadStandings, model: loadModel }[view];
  if (loader) loader();
  if (view === "console") $("#console-in").focus();
}

function renderSeasonSwitch() {
  const el = $("#season-switch");
  el.innerHTML = state.years.map((y) =>
    `<button class="${y === state.year ? "active" : ""}" data-year="${y}">${y}</button>`).join("");
  el.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      state.year = Number(b.dataset.year);
      state.selectedRound = null;
      renderSeasonSwitch();
      populatePredictSelectors();
      switchView(state.view);
    }));
}

/* ------------------------------------------------------------- dashboard */

async function loadDashboard() {
  const y = state.year;
  let s;
  try { s = await getJSON(`/api/summary/${y}`); }
  catch (e) { $("#dash-stats").innerHTML = `<div class="placeholder">${esc(e.message)}</div>`; return; }

  $("#dash-title").textContent = `${y} season`;
  $("#dash-note").textContent =
    `${s.races} rounds · ${s.entries} race entries analysed`;

  $("#dash-stats").innerHTML = [
    [s.races, "Rounds"], [s.drivers, "Drivers"],
    [s.teams, "Teams"], [s.entries, "Entries"],
  ].map(([n, l]) => `<div class="stat"><div class="num" data-count="${n}">0</div><div class="lbl">${l}</div></div>`).join("");
  document.querySelectorAll("#dash-stats .num[data-count]").forEach((el) =>
    Charts.countUp(el, Number(el.dataset.count)));

  $("#dash-leader").innerHTML = `
    <div class="driver-cell" style="font-size:19px">
      <span class="team-bar" style="background:${teamColor(s.leader.team)};height:22px"></span>
      ${esc(s.leader.name)}
    </div>
    <div style="color:var(--muted);font-size:13px;margin:2px 0 12px">${esc(s.leader.team)}</div>
    <div style="display:flex;gap:26px">
      <div><div class="num" style="font-family:var(--mono);font-size:24px">${s.leader.points}</div>
           <div class="lbl" style="font-size:10.5px;letter-spacing:.18em;color:var(--muted)">POINTS</div></div>
      <div><div class="num" style="font-family:var(--mono);font-size:24px">${s.leader.wins}</div>
           <div class="lbl" style="font-size:10.5px;letter-spacing:.18em;color:var(--muted)">WINS</div></div>
    </div>
    <div style="margin-top:14px;color:var(--muted);font-size:12.5px">
      Leading constructor · <strong style="color:var(--text)">${esc(s.top_team.name)}</strong> (${s.top_team.points} pts)
    </div>
    <div id="dash-fight"></div>`;

  renderFightBar(y);

  $("#dash-lastrace-title").textContent =
    `Round ${s.last_race.round} · ${s.last_race.event}`;
  const steps = { 1: "first", 2: "second", 3: "third" };
  const order = [2, 1, 3];
  $("#dash-podium").innerHTML = order.map((want) => {
    const p = s.last_race.podium.find((d) => d.RacePos === want);
    if (!p) return "";
    return `<div class="podium-step ${steps[want]}">
      <div class="podium-name">${esc(p.FullName)}</div>
      <div class="podium-team">${esc(p.TeamName)}</div>
      <div class="podium-block" style="--team:${teamColor(p.TeamName)}">${want}</div>
    </div>`;
  }).join("");

  const races = await getJSON(`/api/races/${y}`);
  state.raceCache[y] = races.races;
  $("#dash-strip").innerHTML = races.races.map((r) => `
    <div class="race-chip" style="--team:${teamColor(r.winner_team)}" data-round="${r.round}">
      <div class="rc-round">R${String(r.round).padStart(2, "0")}</div>
      <div class="rc-event">${esc(r.event.replace(" Grand Prix", " GP"))}</div>
      <div class="rc-winner">${esc(r.winner || "—")}</div>
    </div>`).join("");
  $("#dash-strip").querySelectorAll(".race-chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      state.selectedRound = Number(chip.dataset.round);
      switchView("races");
    }));

  try {
    const m = await getJSON("/api/model");
    if (m.available) {
      const best = m.report.models[m.report.best_model].metrics;
      $("#dash-model").innerHTML = `
        <div>
          <div class="big">${(best.top3_hit_rate * 100).toFixed(1)}%</div>
          <div class="lbl" style="font-size:10.5px;letter-spacing:.18em;color:var(--muted)">MODEL TOP-3 HIT RATE</div>
        </div>
        <div class="desc">Held-out test races, ${m.report.best_model.toUpperCase()} model.
          Picking the top-3 qualifiers scores ${(best.baseline_top3_hit_rate * 100).toFixed(1)}% on the same races —
          see the Model tab for the full, honest comparison.</div>`;
    } else {
      $("#dash-model").innerHTML = `
        <div class="desc">No trained model yet — open the <strong>Console</strong> tab and run
        <code style="font-family:var(--mono)">f1ml train</code>.</div>`;
    }
  } catch { /* model banner is optional */ }
}

/* ----------------------------------------------------------------- races */

async function renderFightBar(year) {
  const host = document.getElementById("dash-fight");
  if (!host) return;
  try {
    const d = await getJSON(`/api/standings/${year}`);
    const [p1, p2] = d.drivers;
    if (!p1 || !p2) return;
    const gap = p1.Points - p2.Points;
    // widths reflect the two leaders' share of their combined points
    const total = p1.Points + p2.Points || 1;
    const w1 = Math.max(12, (p1.Points / total) * 100);
    host.innerHTML = `
      <div class="fight">
        <div class="fight-head">
          <span class="fh-name" style="color:${teamColor(p1.Team)}">${esc(p1.FullName.split(" ").pop())}</span>
          <span style="color:var(--muted)">TITLE FIGHT</span>
          <span class="fh-name" style="color:${teamColor(p2.Team)}">${esc(p2.FullName.split(" ").pop())}</span>
        </div>
        <div class="fight-track">
          <div class="fight-seg a" style="width:${w1}%;background:${teamColor(p1.Team)}">${p1.Points}</div>
          <div class="fight-seg b" style="width:${100 - w1}%">${p2.Points}</div>
        </div>
        <div class="fight-gap">${gap === 0 ? "Level on points" : `<strong>${esc(p1.FullName.split(" ").pop())}</strong> leads by <strong>${gap}</strong> pts`}</div>
      </div>`;
  } catch { /* fight bar is optional */ }
}

async function loadRaces() {
  const y = state.year;
  if (!state.raceCache[y]) {
    const data = await getJSON(`/api/races/${y}`);
    state.raceCache[y] = data.races;
  }
  const races = state.raceCache[y];
  $("#race-list").innerHTML = `
    <thead><tr><th>Rd</th><th>Grand Prix</th><th>Winner</th></tr></thead>
    <tbody>${races.map((r) => `
      <tr class="clickable ${r.round === state.selectedRound ? "selected" : ""}" data-round="${r.round}">
        <td class="num">${r.round}</td>
        <td style="font-weight:600">${esc(r.event)}</td>
        <td><div class="driver-cell" style="font-weight:400">
          <span class="team-bar" style="background:${teamColor(r.winner_team)}"></span>${esc(r.winner || "—")}
        </div></td>
      </tr>`).join("")}</tbody>`;
  $("#race-list").querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => {
      state.selectedRound = Number(tr.dataset.round);
      loadRaces();
    }));

  if (state.selectedRound == null && races.length) state.selectedRound = races[races.length - 1].round;
  if (state.selectedRound != null) loadRaceDetail(y, state.selectedRound);
}

async function loadRaceDetail(year, rnd) {
  const el = $("#race-detail");
  el.innerHTML = `<div class="placeholder">Loading…</div>`;
  let d;
  try { d = await getJSON(`/api/race/${year}/${rnd}`); }
  catch (e) { el.innerHTML = `<div class="placeholder">${esc(e.message)}</div>`; return; }

  const rows = d.classification.map((r) => {
    const finished = r.RacePos != null;
    const delta = finished && r.GridPosition ? Math.round(r.GridPosition - r.RacePos) : null;
    const deltaHtml = delta == null ? "" :
      delta > 0 ? `<span class="delta up">▲${delta}</span>` :
      delta < 0 ? `<span class="delta down">▼${-delta}</span>` :
      `<span class="delta flat">–</span>`;
    const dnf = r.Status && !/Finished|Lapped/.test(r.Status);
    return `<tr>
      <td>${finished ? `<span class="pos-box ${r.RacePos <= 3 ? "p" + r.RacePos : ""}">${r.RacePos}</span>` : `<span class="pos-box">—</span>`}</td>
      <td><div class="driver-cell">
        <span class="team-bar" style="background:${teamColor(r.TeamName)}"></span>
        <div>${esc(r.FullName)}<div class="team-name">${esc(r.TeamName)}</div></div>
      </div></td>
      <td class="num">${r.QualyPos ?? "—"}</td>
      <td class="num">${r.GridPosition ?? "—"}</td>
      <td>${deltaHtml}</td>
      <td>${dnf ? `<span class="status-chip dnf">${esc(r.Status)}</span>` : ""}</td>
      <td class="num">${r.Points ? r.Points : ""}</td>
    </tr>`;
  }).join("");

  el.innerHTML = `
    <h2>${esc(d.event)}</h2>
    <div class="race-sub">${d.year} · Round ${d.round}</div>
    <table class="table">
      <thead><tr><th>Pos</th><th>Driver</th><th class="num">Qual</th><th class="num">Grid</th><th></th><th></th><th class="num">Pts</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/* ------------------------------------------------------------- standings */

async function loadStandings() {
  const d = await getJSON(`/api/standings/${state.year}`);
  const maxD = Math.max(...d.drivers.map((r) => r.Points), 1);
  $("#standings-drivers").innerHTML = `
    <thead><tr><th>Pos</th><th>Driver</th><th class="num">Pts</th><th></th><th class="num">Wins</th><th class="num">Pod</th></tr></thead>
    <tbody>${d.drivers.map((r) => `
      <tr>
        <td class="num">${r.Pos}</td>
        <td><div class="driver-cell">
          <span class="team-bar" style="background:${teamColor(r.Team)}"></span>
          <div><span class="driver-link" data-driver="${esc(r.FullName)}" data-year="${state.year}">${esc(r.FullName)}</span><div class="team-name">${esc(r.Team)}</div></div>
        </div></td>
        <td class="num" style="font-weight:600">${r.Points}</td>
        <td><div class="points-bar-track"><div class="points-bar" style="width:${(r.Points / maxD) * 100}%"></div></div></td>
        <td class="num">${r.Wins}</td>
        <td class="num">${r.Podiums}</td>
      </tr>`).join("")}</tbody>`;

  const maxT = Math.max(...d.constructors.map((r) => r.Points), 1);
  $("#standings-teams").innerHTML = `
    <thead><tr><th>Pos</th><th>Constructor</th><th class="num">Pts</th><th></th><th class="num">Wins</th></tr></thead>
    <tbody>${d.constructors.map((r) => `
      <tr>
        <td class="num">${r.Pos}</td>
        <td><div class="driver-cell">
          <span class="team-bar" style="background:${teamColor(r.TeamName)}"></span>${esc(r.TeamName)}
        </div></td>
        <td class="num" style="font-weight:600">${r.Points}</td>
        <td><div class="points-bar-track"><div class="points-bar" style="width:${(r.Points / maxT) * 100}%;background:${teamColor(r.TeamName)}"></div></div></td>
        <td class="num">${r.Wins}</td>
      </tr>`).join("")}</tbody>`;
}

/* ----------------------------------------------------------------- model */

async function loadModel() {
  const el = $("#model-body");
  el.innerHTML = `<div class="card"><div class="placeholder">Loading…</div></div>`;
  const m = await getJSON("/api/model");
  if (!m.available) {
    el.innerHTML = `<div class="card"><div class="placeholder">
      No trained model yet.<br><br>
      <button class="btn-red" id="model-train-btn">Train in console</button>
    </div></div>`;
    $("#model-train-btn").addEventListener("click", () => {
      switchView("console");
      runCommand("f1ml train --model all");
    });
    return;
  }

  const report = m.report;
  const bestName = report.best_model;
  const best = report.models[bestName].metrics;

  const duel = (label, model, base) => `
    <div class="duel">
      <div class="duel-row">
        <span class="d-lbl">${label} — model</span>
        <div class="duel-track"><div class="duel-fill model" style="width:${model * 100}%"></div></div>
        <span class="d-val">${(model * 100).toFixed(1)}%</span>
      </div>
      <div class="duel-row">
        <span class="d-lbl">grid top-3</span>
        <div class="duel-track"><div class="duel-fill base" style="width:${base * 100}%"></div></div>
        <span class="d-val">${(base * 100).toFixed(1)}%</span>
      </div>
    </div>`;

  const tiles = `
    <div class="metric-tiles">
      <div class="tile accent"><div class="t-val">${(best.top3_hit_rate * 100).toFixed(1)}% <span class="vs">vs ${(best.baseline_top3_hit_rate * 100).toFixed(1)}%</span></div><div class="t-lbl">Top-3 hits vs grid</div></div>
      <div class="tile"><div class="t-val">${best.pr_auc.toFixed(3)}</div><div class="t-lbl">PR-AUC</div></div>
      <div class="tile"><div class="t-val">${best.roc_auc.toFixed(3)}</div><div class="t-lbl">ROC-AUC</div></div>
      <div class="tile"><div class="t-val">${best.recall_podium.toFixed(2)}</div><div class="t-lbl">Podium recall</div></div>
      <div class="tile"><div class="t-val">${best.precision_podium.toFixed(2)}</div><div class="t-lbl">Podium precision</div></div>
      <div class="tile"><div class="t-val">${best.brier.toFixed(3)}</div><div class="t-lbl">Brier score</div></div>
    </div>`;

  const comparison = `
    <div class="card">
      <div class="card-title">Model comparison — held-out races (${best.n_test_races} races after cutoff ${report.models[bestName].cutoff.join(" R")})</div>
      <table class="table">
        <thead><tr><th>Model</th><th class="num">Top-3 hits</th><th class="num">PR-AUC</th><th class="num">ROC-AUC</th><th class="num">F1</th><th class="num">Brier</th><th></th></tr></thead>
        <tbody>${Object.entries(report.models).map(([name, r]) => `
          <tr>
            <td style="font-weight:700">${name === "rf" ? "Random Forest" : "Gradient Boosting"}</td>
            <td class="num">${(r.metrics.top3_hit_rate * 100).toFixed(1)}%</td>
            <td class="num">${r.metrics.pr_auc.toFixed(3)}</td>
            <td class="num">${r.metrics.roc_auc.toFixed(3)}</td>
            <td class="num">${r.metrics.f1_podium.toFixed(3)}</td>
            <td class="num">${r.metrics.brier.toFixed(3)}</td>
            <td>${name === bestName ? '<span class="status-chip hit">In use</span>' : ""}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;

  const picksRows = best.races.map((r) => `
    <tr>
      <td class="num">R${r.round}</td>
      <td style="font-weight:600">${esc(r.event)}</td>
      <td>${r.picks.map((p) =>
        `<span class="status-chip ${r.actual.includes(p) ? "hit" : "miss"}" style="margin-right:5px">${esc(p)}</span>`).join("")}</td>
      <td class="num">${r.hits}/3</td>
    </tr>`).join("");

  const picks = `
    <div class="card">
      <div class="card-title">Race-by-race picks — ${bestName.toUpperCase()} on held-out races</div>
      <table class="table">
        <thead><tr><th>Rd</th><th>Grand Prix</th><th>Model podium picks</th><th class="num">Hits</th></tr></thead>
        <tbody>${picksRows}</tbody>
      </table>
    </div>`;

  const maxImp = Math.max(...m.importance.map((f) => f.importance), 1e-9);
  const importance = `
    <div class="card">
      <div class="card-title">What drives a podium — feature importance</div>
      ${m.importance.map((f) => `
        <div class="fi-row">
          <span class="fi-name">${esc(featLabel(f.feature))}</span>
          <div class="fi-track"><div class="fi-fill" style="width:${(f.importance / maxImp) * 100}%"></div></div>
          <span class="fi-val">${f.importance.toFixed(3)}</span>
        </div>`).join("")}
    </div>`;

  el.innerHTML = tiles +
    `<div class="card"><div class="card-title">Model vs the obvious baseline</div>
      ${duel("top-3 hit rate", best.top3_hit_rate, best.baseline_top3_hit_rate)}
      <div class="desc" style="color:var(--muted);font-size:13px">
        In modern F1, qualifying position is brutally predictive — beating "pick the top-3 qualifiers"
        is the real test, and plain accuracy numbers hide it. The model's edge is calibrated
        podium probabilities for the whole field, not just three names.
      </div>
    </div>` +
    comparison + picks + importance +
    `<div class="card" id="backtest-card"><div class="card-title">Walk-forward backtest — ${state.year}</div>
     <div class="placeholder">Loading…</div></div>`;

  loadBacktest();
}

async function loadBacktest() {
  const card = $("#backtest-card");
  if (!card) return;
  const bt = await getJSON(`/api/backtest/${state.year}`);
  if (!bt.available) {
    card.innerHTML = `
      <div class="card-title">Walk-forward backtest — ${state.year}</div>
      <div class="placeholder">${esc(bt.hint)}<br><br>
        <button class="btn-red" id="bt-run">Run backtest in console</button></div>`;
    $("#bt-run").addEventListener("click", () => {
      switchView("console");
      runCommand(`f1ml backtest --year ${state.year}`);
    });
    return;
  }
  const r = bt.report;
  const cells = r.races.map((race) => {
    const pip = (n, cls) => [0, 1, 2].map((i) =>
      `<span class="bt-pip ${i < n ? cls : ""}"></span>`).join("");
    return `<div class="bt-cell" title="${esc(race.event)} — model ${race.model_hits}/3, grid ${race.baseline_hits}/3">
      <div class="bt-pips">
        <div class="bt-pip-row">${pip(race.model_hits, "hit-model")}</div>
        <div class="bt-pip-row">${pip(race.baseline_hits, "hit-base")}</div>
      </div>
      <div class="bt-round">${race.round}</div>
    </div>`;
  }).join("");
  card.innerHTML = `
    <div class="card-title">Walk-forward backtest — ${r.year} (retrained before every race)</div>
    <div class="verdict">
      <span class="v-item">Model season hit rate · <strong>${(r.model_hit_rate * 100).toFixed(1)}%</strong></span>
      <span class="v-item">Grid baseline · <strong>${(r.baseline_hit_rate * 100).toFixed(1)}%</strong></span>
      <span class="v-item">${r.n_races} races</span>
    </div>
    <div class="bt-grid">${cells}</div>
    <div class="legend">
      <span><span class="sw" style="background:var(--red)"></span>model podium hits</span>
      <span><span class="sw" style="background:#55556a"></span>grid top-3 hits</span>
      <span>hover a column for the race</span>
    </div>`;
}

/* --------------------------------------------------------------- predict */

function populatePredictSelectors() {
  const yearSel = $("#predict-year");
  yearSel.innerHTML = state.years.map((y) =>
    `<option value="${y}" ${y === state.year ? "selected" : ""}>${y}</option>`).join("");
  fillPredictRounds();
}

async function fillPredictRounds() {
  const y = Number($("#predict-year").value);
  if (!state.raceCache[y]) {
    const data = await getJSON(`/api/races/${y}`);
    state.raceCache[y] = data.races;
  }
  const races = state.raceCache[y].filter((r) => r.round >= 3);
  $("#predict-round").innerHTML = races.map((r) =>
    `<option value="${r.round}">R${r.round} — ${esc(r.event)}</option>`).join("");
  $("#predict-round").value = races.length ? races[races.length - 1].round : "";
}

async function runPrediction() {
  const y = Number($("#predict-year").value);
  const rnd = Number($("#predict-round").value);
  const btn = $("#predict-run");
  btn.disabled = true;
  $("#predict-status").textContent = "";
  $("#predict-result").innerHTML =
    `<div class="card">${Charts.lights("Training on every race before this one…")}</div>`;
  try {
    const d = await getJSON(`/api/predict/${y}/${rnd}`);
    const rows = d.predictions.map((p, i) => {
      const actual = p.RacePos != null
        ? (p.IsPodium ? `<span class="status-chip hit">P${p.RacePos}</span>`
                      : `<span class="status-chip miss">P${p.RacePos}</span>`)
        : "";
      return `<div class="prob-row">
        <span class="num" style="font-family:var(--mono);font-size:12.5px;color:var(--muted)">${i + 1}</span>
        <div class="driver-cell">
          <span class="team-bar" style="background:${teamColor(p.TeamName)}"></span>
          <div>${esc(p.FullName)}<div class="team-name">${esc(p.TeamName)} · Q${p.QualyPos}</div></div>
        </div>
        <div class="prob-track"><div class="prob-fill" style="width:${p.prob * 100}%"></div></div>
        <span class="prob-val">${(p.prob * 100).toFixed(1)}%</span>
        <span class="prob-actual">${actual}</span>
      </div>`;
    }).join("");

    const picks = d.predictions.slice(0, 3).map((p) => p.FullName);
    const actual = d.predictions.filter((p) => p.IsPodium)
      .sort((a, b) => a.RacePos - b.RacePos).map((p) => p.FullName);
    const hits = picks.filter((p) => actual.includes(p)).length;

    $("#predict-result").innerHTML = `
      <div class="card">
        <div class="card-title">${esc(d.event)} — podium probabilities</div>
        <div class="verdict">
          <span class="v-item">Model podium · <strong>${picks.map(esc).join(", ")}</strong></span>
          ${actual.length ? `<span class="v-item">Actual · <strong>${actual.map(esc).join(", ")}</strong></span>
          <span class="v-item">Hits · <strong>${hits}/3</strong></span>` : ""}
        </div>
        ${rows}
      </div>`;
    $("#predict-status").textContent = "";
    window.radio(`Model's call: ${picks[0].split(" ").pop()}`,
      `${esc(d.event)}${actual.length ? ` · ${hits}/3 correct` : ""}`,
      teamColor(d.predictions[0].TeamName));
  } catch (e) {
    $("#predict-result").innerHTML = "";
    $("#predict-status").textContent = e.message;
  } finally {
    btn.disabled = false;
  }
}

/* --------------------------------------------------------------- console */

const QUICK_COMMANDS = [
  "f1ml info",
  "f1ml weekend",
  "f1ml fantasy --budget 100",
  "f1ml predict --year 2025 --round 23",
  "f1ml h2h --year 2024 --round 8 --d1 VER --d2 LEC",
  "f1ml backtest --year 2025",
  "f1ml standings --year 2025",
];

const HELP_TEXT = `Available commands (same as the real terminal):

  f1ml info                              dataset & model status
  f1ml fetch --year 2025                 download a season from FastF1
  f1ml merge --year 2025                 raw CSVs -> master results
  f1ml features                          build the model feature table
  f1ml train [--model rf|gbdt|all] [--tune] [--cutoff 2025:18]
  f1ml evaluate [--model rf|gbdt]        saved model metrics
  f1ml predict --year 2025 --round 23    podium picks for one race
  f1ml backtest --year 2025              walk-forward season backtest
  f1ml standings --year 2025             championship standings
  f1ml weekend [--top 10]                next race + form projection
  f1ml fantasy [--budget 100]            optimise a fantasy team
  f1ml h2h --year 2024 --round 8 --d1 VER --d2 LEC   telemetry duel
  f1ml raceline --image track.png        racing line from a track map

  help                                   this text
  clear                                  wipe the console
`;

let history = [];
let historyIdx = -1;
let running = false;

function consolePrint(text, cls) {
  const out = $("#console-out");
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text;
  out.appendChild(span);
  out.scrollTop = out.scrollHeight;
}

async function runCommand(raw) {
  const cmd = raw.trim();
  if (!cmd) return;
  consolePrint(`pit-wall:~$ ${cmd}\n`, "cmd-echo");
  history.push(cmd);
  historyIdx = history.length;

  if (cmd === "clear") { $("#console-out").innerHTML = ""; return; }
  if (cmd === "help") { consolePrint(HELP_TEXT, "cmd-sys"); return; }
  if (running) { consolePrint("A command is already running — wait for it to finish.\n", "cmd-err"); return; }

  running = true;
  try {
    const res = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      consolePrint(`${err.error || res.statusText}\n`, "cmd-err");
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      consolePrint(decoder.decode(value, { stream: true }));
    }
  } catch (e) {
    consolePrint(`Connection error: ${e.message}\n`, "cmd-err");
  } finally {
    running = false;
  }
}

function initConsole() {
  $("#console-chips").innerHTML = QUICK_COMMANDS.map((c) =>
    `<button class="chip">${esc(c)}</button>`).join("");
  $("#console-chips").querySelectorAll(".chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      $("#console-in").value = chip.textContent;
      $("#console-in").focus();
    }));

  const input = $("#console-in");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const v = input.value;
      input.value = "";
      runCommand(v);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (historyIdx > 0) { historyIdx--; input.value = history[historyIdx] ?? ""; }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx < history.length - 1) { historyIdx++; input.value = history[historyIdx] ?? ""; }
      else { historyIdx = history.length; input.value = ""; }
    }
  });

  consolePrint("Pit Wall console — type `help` for the command list, or use a quick command above.\n\n", "cmd-sys");
}

/* ------------------------------------------------------------------ init */

// team-radio toast — a broadcast-style message for completed actions
window.radio = function (title, sub, color) {
  const stack = document.getElementById("radio-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = "radio-toast";
  if (color) el.style.setProperty("--rt", color);
  el.innerHTML =
    `<div class="radio-wave"><i></i><i></i><i></i><i></i><i></i></div>
     <div class="radio-body">
       <div class="radio-tag">▶ TEAM RADIO</div>
       <div class="radio-title">${esc(title)}</div>
       ${sub ? `<div class="radio-sub">${esc(sub)}</div>` : ""}
     </div>`;
  const close = () => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 320);
  };
  el.addEventListener("click", close);
  stack.appendChild(el);
  setTimeout(close, 4600);
  // keep at most 3 on screen
  while (stack.children.length > 3) stack.firstChild.remove();
};

function initCarFX() {
  // drop the SVG car into every [data-car] slot (hero + lap progress)
  document.querySelectorAll("[data-car]").forEach((el) => {
    el.innerHTML = Charts.car();
  });

  // the mini car laps the header as you scroll the page
  const fill = $("#lap-fill");
  const carEl = $("#lap-car");
  if (!fill || !carEl) return;
  let ticking = false;
  const update = () => {
    ticking = false;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const p = max > 0 ? Math.min(1, window.scrollY / max) : 0;
    fill.style.width = (p * 100).toFixed(2) + "%";
    carEl.style.left = `calc(${(p * 100).toFixed(2)}% - ${(p * 44).toFixed(0)}px)`;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  update();
}

async function init() {
  initCarFX();
  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchView(t.dataset.view)));
  $("#predict-year").addEventListener("change", fillPredictRounds);
  $("#predict-run").addEventListener("click", runPrediction);
  initConsole();

  try {
    const s = await getJSON("/api/seasons");
    state.years = s.years;
    state.year = s.years[s.years.length - 1] ?? null;
  } catch {
    state.years = [];
  }
  renderSeasonSwitch();
  populatePredictSelectors();
  loadDashboard();
}

init();
