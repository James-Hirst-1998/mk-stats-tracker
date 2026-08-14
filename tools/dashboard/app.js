/* The dashboard renders what /api/session says and computes nothing itself.
   State: which session, the slider ("after race N"), and whether rows are
   labelled by character or by player name. */

const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const POLL_MS = 2000;

let sessionDir = null;
let payload = null;       // last /api/session body, as a string for cheap diff
let data = null;          // parsed
let thru = null;          // slider value; null = follow the latest race
let mode = 0;             // 0 characters, 1 player names
let pointsChart = null;
const raceCharts = {};    // file -> Chart, so expanding twice doesn't leak
const raceDetails = {};   // file -> fetched detail
const openRaces = new Set();

const $ = (id) => document.getElementById(id);

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-")
             .replace(/^-+|-+$/g, "") || "x";
}

function charNameOf(i) {
  const p = data.session.players[i];
  if (p.character_name) return p.character_name;
  for (const r of data.session.races.slice().reverse()) {
    const row = r.rows[i];
    if (row && row.character != null)
      return data.session.characters[row.character] || p.name;
  }
  return p.name;
}

function nameOf(i) { return mode ? data.session.players[i].name : charNameOf(i); }

function faceOf(i, size) {
  const cls = size ? `face" style="width:${size}px;height:${size}px` : "face";
  const src = "/assets/characters/" + slug(charNameOf(i)) + ".png";
  const initials = nameOf(i).split(/\s+/).map(w => w[0]).join("").slice(0, 2);
  return `<div class="${cls}">` +
    `<img src="${src}" alt="" onerror="this.parentNode.style.background='${PALETTE[i]}';this.parentNode.textContent='${initials}'">` +
    `</div>`;
}

function mmss(s) {
  const whole = Math.round(s);
  return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
}

function counted() {
  const n = thru == null ? data.session.races.length : thru;
  return data.session.races.slice(0, n);
}

function totalsFor(races) {
  return data.session.players.map((p, i) => {
    const t = { pts: 0, led: 0, thrown: 0, landed: 0, taken: 0, blues: 0,
                boosts: 0, finishes: [] };
    for (const r of races) {
      const row = r.rows[i];
      if (!row) continue;
      t.pts += row.points; t.led += row.led; t.thrown += row.thrown;
      t.landed += row.landed; t.taken += row.taken; t.blues += row.blues;
      t.boosts += row.boosts;
      if (row.position) t.finishes.push(row.position);
    }
    t.avg = t.finishes.length
      ? t.finishes.reduce((a, b) => a + b, 0) / t.finishes.length : null;
    return t;
  });
}

function duelName(key) {
  if (typeof key === "number") return nameOf(key);
  return data.session.characters[key.slice(1)] || "?";
}

function nemesisLines(i) {
  const on = {}, by = {};
  for (const d of data.session.duels) {
    if (d.to === i && d.from !== i) on[d.from] = (on[d.from] || 0) + d.count;
    if (d.from === i && d.to !== i) by[d.to] = (by[d.to] || 0) + d.count;
  }
  const top = (m) => {
    const best = Math.max(0, ...Object.values(m));
    if (!best) return null;
    const names = Object.keys(m).filter(k => m[k] === best)
      .map(k => duelName(isNaN(+k) ? k : +k));
    const shown = names.slice(0, 2).join(" and ") +
      (names.length > 2 ? ` +${names.length - 2} more` : "");
    return { names: shown, n: best };
  };
  const enemy = top(on), victim = top(by);
  return (enemy ? `Enemy: ${enemy.names}, ${enemy.n} hit${enemy.n > 1 ? "s" : ""}` : "Enemy: nobody yet")
    + "<br>" + (victim ? `Victim: ${victim.names}, ${victim.n} hit${victim.n > 1 ? "s" : ""}` : "Victim: nobody yet");
}

/* ---- sections ---------------------------------------------------------- */

function renderHeader() {
  const s = data.session;
  $("title").textContent = s.name;
  const when = (s.started || "").slice(0, 10);
  $("subtitle").textContent =
    `${when} · ${s.races.length} race${s.races.length === 1 ? "" : "s"}` +
    (s.planned_races ? ` of ${s.planned_races}` : "");
  const live = data.live;
  $("livepill").style.display = live ? "" : "none";
  if (live) {
    const total = s.planned_races ? ` of ${s.planned_races}` : "";
    $("livetext").textContent =
      `Race ${live.race}${total} in progress` +
      (live.course_name ? ` — ${live.course_name}` : "");
  }
}

function renderCards() {
  const races = counted(), totals = totalsFor(races);
  const order = totals.map((t, i) => ({ t, i }))
    .sort((a, b) => b.t.pts - a.t.pts);
  $("cards").innerHTML = order.map(({ t, i }, k) => `
    <div class="card pcard">
      <div class="head">
        <span class="rank r${k + 1}">${k + 1}</span>
        ${faceOf(i)}
        <div>
          <div class="pname">${nameOf(i)}</div>
          <div class="psub">${t.avg ? "avg P" + t.avg.toFixed(1) : "no finishes yet"}</div>
        </div>
      </div>
      <div class="pts">${t.pts} <small>pts</small></div>
      <div class="nemesis">${nemesisLines(i)}</div>
    </div>`).join("");
}

function renderTeams() {
  const teams = data.session.teams || [];
  const totals = totalsFor(counted());
  $("teams").innerHTML = teams.map(team => {
    const pts = team.members.reduce((a, m) => a + totals[m].pts, 0);
    const chips = team.members.map(m =>
      `<span class="chip" style="background:${PALETTE[m]}"></span>`).join("");
    const names = team.members.map(m => nameOf(m)).join(" + ");
    return `<div class="team"><span>${chips}${names}</span><b>${pts} pts</b></div>`;
  }).join("");
}

function renderPoints() {
  const s = data.session;
  const races = counted();
  const labels = ["Start"].concat(races.map(r => r.course_name));
  const max = 15 * (s.planned_races || s.races.length);
  const datasets = s.players.map((p, i) => {
    let sum = 0;
    const pts = [0].concat(races.map(r => sum += (r.rows[i]?.points ?? 0)));
    return { data: pts, borderColor: PALETTE[i], borderWidth: 2,
             borderDash: [4, 4], pointRadius: 2.5,
             pointBackgroundColor: PALETTE[i], tension: 0 };
  });
  $("legend").innerHTML = s.players.map((p, i) =>
    `<span class="one"><span class="bar" style="background:${PALETTE[i]}"></span>${nameOf(i)}</span>`).join("");
  const endLabels = {
    id: "endLabels",
    afterDraw(c) {
      const ctx = c.ctx;
      // Nudge labels apart when two lines end close together.
      const spots = c.data.datasets.map((d, i) => {
        const meta = c.getDatasetMeta(i);
        const pt = meta.data[meta.data.length - 1];
        return pt ? { i, x: pt.x, y: pt.y, v: d.data[d.data.length - 1] } : null;
      }).filter(Boolean).sort((a, b) => a.y - b.y);
      for (let k = 1; k < spots.length; k++)
        if (spots[k].y - spots[k - 1].y < 13) spots[k].y = spots[k - 1].y + 13;
      ctx.save();
      ctx.font = "600 11px system-ui";
      for (const s of spots) {
        ctx.fillStyle = PALETTE[s.i];
        ctx.fillText(`${nameOf(s.i)} ${s.v}`, s.x + 7, s.y + 4);
      }
      ctx.restore();
    },
  };
  if (pointsChart) pointsChart.destroy();
  pointsChart = new Chart($("points"), {
    type: "line",
    data: { labels, datasets },
    plugins: [endLabels],
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 96 } },
      plugins: { legend: { display: false },
                 tooltip: { callbacks: { label: c =>
                   `${nameOf(c.datasetIndex)}: ${c.parsed.y} pts` } } },
      scales: {
        x: { grid: { display: false },
             ticks: { color: "#868e96", font: { size: 11 },
                      maxRotation: 30, autoSkip: true } },
        y: { min: 0, max, grid: { color: "#e9ecef" },
             ticks: { color: "#868e96", font: { size: 11 } },
             title: { display: true, text: `points, of a possible ${max}`,
                      color: "#868e96", font: { size: 11 } } },
      },
    },
  });
  const n = data.session.races.length;
  const el = $("thru");
  el.max = n;
  el.value = thru == null ? n : thru;
  $("thruval").textContent = `${el.value} of ${n}`;
}

function renderTotals() {
  const races = counted(), totals = totalsFor(races);
  $("totalstitle").textContent = `Totals across races 1–${races.length}`;
  const order = totals.map((t, i) => ({ t, i }))
    .sort((a, b) => b.t.pts - a.t.pts);
  $("totals").innerHTML = `<table>
    <tr><th>Player</th><th>Pts</th><th>Avg fin</th><th>Led</th><th>Thrown</th>
        <th>Landed</th><th>Taken</th><th>Blues</th><th>Boosts</th></tr>` +
    order.map(({ t, i }) => `<tr>
      <td><span class="chip" style="background:${PALETTE[i]}"></span><span class="who">${nameOf(i)}</span></td>
      <td><b>${t.pts}</b></td>
      <td>${t.avg ? t.avg.toFixed(1) : "–"}</td>
      <td>${mmss(t.led)}</td>
      <td>${t.thrown}</td><td>${t.landed}</td><td>${t.taken}</td>
      <td>${t.blues}</td><td>${t.boosts}</td></tr>`).join("") + "</table>";

  const all = totalsFor(data.session.races);
  $("shells").innerHTML = data.session.players.map((p, i) => {
    const n = all[i].blues;
    const shells = `<img src="/assets/items/blue-shell.png" alt="">`.repeat(n);
    return `<span class="one"><span class="who">${nameOf(i)}</span>${shells}<span class="muted">${n}</span></span>`;
  }).join("");
}

function renderAwards() {
  const a = data.session.awards || {};
  const out = [];
  const names = (list) => list.map(nameOf).join(" and ");
  if (a.blue_magnet && a.blue_magnet.players.length)
    out.push(["blue-shell", "Blue shell magnet", names(a.blue_magnet.players),
              `${a.blue_magnet.count} taken`]);
  if (a.sniper)
    out.push(["red-shell", "Sniper", names(a.sniper.players),
              `${a.sniper.landed} hits from ${a.sniper.thrown} thrown`]);
  if (a.first_blood)
    out.push(["bob-omb", "First blood",
              a.first_blood.player != null ? nameOf(a.first_blood.player) : a.first_blood.name,
              a.first_blood.count > 1 ? `${a.first_blood.count} races opened` : "opened the scoring"]);
  if (a.collapse)
    out.push(["banana", "The collapse", nameOf(a.collapse.player),
              `led ${Math.round(a.collapse.led)}s of ${a.collapse.course_name}, finished P${a.collapse.position}`]);
  $("awards").innerHTML = out.map(([icon, title, who, detail]) => `
    <div class="card award">
      <img src="/assets/items/${icon}.png" alt="" onerror="this.style.display='none'">
      <div><div class="t">${title}</div><div class="w">${who}</div>
           <div class="d">${detail}</div></div>
    </div>`).join("");
}

/* ---- the per-race breakdown ------------------------------------------- */

function renderRaces() {
  $("races").innerHTML = data.session.races.map(r => {
    // Characters mode shows the character that won *that race*, which for a
    // human who switched characters mid-session is not their usual one.
    const winName = r.winner
      ? (mode && r.winner.player != null ? nameOf(r.winner.player)
                                         : r.winner.character_name)
      : null;
    const win = r.winner
      ? `${winName}${r.winner.cpu ? " (CPU)" : ""} ${r.winner.time ? mmss(r.winner.time) : ""}`
      : "abandoned";
    return `<div class="race" id="race-${r.n}">
      <div class="racehead" onclick="toggleRace(${r.n}, '${r.file}')">
        <span class="n">${r.n}</span>
        <span class="course">${r.course_name}</span>
        <span class="win">winner ${win}</span>
        <span class="arrow">›</span>
      </div>
      <div class="racebody" id="racebody-${r.n}"></div>
    </div>`;
  }).join("");
  for (const n of openRaces) {
    const r = data.session.races.find(x => x.n === n);
    if (r) { $(`race-${n}`).classList.add("open"); fillRace(n, r.file); }
  }
}

window.toggleRace = function (n, file) {
  const el = $(`race-${n}`);
  const open = el.classList.toggle("open");
  if (open) { openRaces.add(n); fillRace(n, file); }
  else openRaces.delete(n);
};

async function fillRace(n, file) {
  if (!raceDetails[file]) {
    const res = await fetch(`/api/race/${sessionDir}/${file}`);
    raceDetails[file] = await res.json();
  }
  const d = raceDetails[file];
  const body = $(`racebody-${n}`);
  const rows = data.session.races.find(x => x.n === n).rows;
  const order = Object.keys(rows).map(Number)
    .sort((a, b) => (rows[a].position || 99) - (rows[b].position || 99));
  body.innerHTML = `
    <div class="legend">${d.players.map((p, i) => rows[i] ?
      `<span class="one"><span class="bar" style="background:${PALETTE[i]}"></span>${nameOf(i)}</span>` : "").join("")}
      <span class="one" style="color:#495057">&#10005; hit taken</span>
      <span class="one" style="color:#4a3aa7">&#9660; blue shell</span></div>
    <div class="chartbox"><canvas id="worm-${n}"></canvas></div>
    <table>
      <tr><th>Player</th><th>Finish</th><th>Led</th><th>Taken</th>
          <th>Landed</th><th>Thrown</th><th>Blues</th><th>Boosts</th></tr>
      ${order.map(i => { const r = rows[i]; return `<tr>
        <td><span class="chip" style="background:${PALETTE[i]}"></span><span class="who">${nameOf(i)}</span></td>
        <td>${r.position ? "P" + r.position : "–"}</td>
        <td>${r.led.toFixed(1)}s</td><td>${r.taken}</td><td>${r.landed}</td>
        <td>${r.thrown}</td><td>${r.blues}</td><td>${r.boosts}</td></tr>`; }).join("")}
    </table>
    <a class="replaylink" href="/replay?session=${sessionDir}&race=${file}">Watch the replay →</a>`;
  drawWorm(n, d);
}

function drawWorm(n, d) {
  const labels = d.series[Object.keys(d.series)[0]].map((_, i) => i * d.sample_every);
  const fmt = (s) => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");
  const datasets = [];
  for (const [i, series] of Object.entries(d.series))
    datasets.push({ data: series, stepped: true, borderColor: PALETTE[+i],
                    borderWidth: 2, pointRadius: 0, pi: +i, kind: "line" });
  const markers = { hits: {}, blues: {} };
  for (const m of d.markers) {
    const kind = m.blue ? "blues" : "hits";
    (markers[kind][m.player] = markers[kind][m.player] || {})[m.index] = m;
  }
  for (const [pi, byIndex] of Object.entries(markers.hits))
    datasets.push({ data: labels.map((_, k) => byIndex[k] ? byIndex[k].position : null),
                    showLine: false, pointStyle: "crossRot", pointRadius: 4.5,
                    pointBorderWidth: 2, pointBorderColor: PALETTE[+pi],
                    pi: +pi, kind: "hit", lookup: byIndex });
  for (const [pi, byIndex] of Object.entries(markers.blues))
    datasets.push({ data: labels.map((_, k) => byIndex[k] ? byIndex[k].position : null),
                    showLine: false, pointStyle: "triangle", pointRotation: 180,
                    pointRadius: 7, pointBackgroundColor: PALETTE[+pi],
                    pointBorderColor: "#4a3aa7", pointBorderWidth: 2,
                    pi: +pi, kind: "blue", lookup: byIndex });
  const lapLines = {
    id: "laps",
    afterDraw(c) {
      const { ctx } = c, x = c.scales.x, y = c.scales.y;
      ctx.save(); ctx.strokeStyle = "#e9ecef"; ctx.setLineDash([4, 4]);
      for (const l of d.lap_starts) {
        const px = x.getPixelForValue(l.t / d.sample_every);
        ctx.beginPath(); ctx.moveTo(px, y.top); ctx.lineTo(px, y.bottom); ctx.stroke();
        ctx.fillStyle = "#868e96"; ctx.font = "11px system-ui";
        ctx.fillText(`lap ${l.lap}`, px + 4, y.top + 10);
      }
      ctx.restore();
    },
  };
  if (raceCharts[n]) raceCharts[n].destroy();
  raceCharts[n] = new Chart($(`worm-${n}`), {
    type: "line",
    data: { labels, datasets },
    plugins: [lapLines],
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: { legend: { display: false },
        tooltip: { callbacks: {
          title: (c) => fmt(labels[c[0].dataIndex]),
          label: (c) => {
            const ds = c.dataset;
            if (ds.kind === "line") return `${nameOf(ds.pi)}: P${c.parsed.y}`;
            const m = ds.lookup[c.dataIndex];
            const by = m.by.length ? ` (${m.by.join(", ")})` : "";
            return `${nameOf(ds.pi)}: ${m.blue ? "Blue Shell" : m.cause}${by}${m.caught ? ", caught in the blast" : ""}`;
          } } } },
      scales: {
        x: { grid: { display: false },
             ticks: { color: "#868e96", font: { size: 11 }, maxTicksLimit: 7,
                      callback: (v) => fmt(labels[v]) } },
        y: { reverse: true, min: 1, max: 12,
             grid: { color: "#e9ecef" },
             ticks: { color: "#868e96", font: { size: 11 }, stepSize: 1,
                      callback: (v) => "P" + v } },
      },
    },
  });
}

/* ---- wiring ------------------------------------------------------------ */

function renderAll() {
  renderHeader(); renderCards(); renderTeams(); renderPoints();
  renderTotals(); renderAwards(); renderRaces();
}

async function poll() {
  try {
    const res = await fetch(`/api/session/${sessionDir}`);
    const text = await res.text();
    if (text !== payload) {
      const races = data ? data.session.races.length : -1;
      payload = text;
      data = JSON.parse(text);
      // A new race landed: clear per-race caches, follow it if the slider
      // was already at the end.
      if (data.session.races.length !== races) {
        for (const k of Object.keys(raceDetails)) delete raceDetails[k];
        if (thru != null && thru >= races) thru = null;
      }
      renderAll();
    }
  } catch (e) { /* server restarting; keep polling */ }
  setTimeout(poll, POLL_MS);
}

async function start() {
  const sessions = await (await fetch("/api/sessions")).json();
  const pick = $("sessionpick");
  pick.innerHTML = sessions.map(s =>
    `<option value="${s.dir}">${s.name} · ${(s.started || "").slice(0, 10)} · ${s.races}</option>`).join("");
  const wanted = new URLSearchParams(location.search).get("session");
  sessionDir = sessions.find(s => s.dir === wanted)?.dir || sessions[0]?.dir;
  if (!sessionDir) { $("subtitle").textContent = "no sessions found"; return; }
  pick.value = sessionDir;
  pick.onchange = () => { location.search = "?session=" + pick.value; };
  $("thru").oninput = (e) => {
    thru = +e.target.value === data.session.races.length ? null : +e.target.value;
    renderCards(); renderTeams(); renderPoints(); renderTotals();
  };
  $("mode-char").onclick = () => setMode(0);
  $("mode-name").onclick = () => setMode(1);
  poll();
}

function setMode(m) {
  mode = m;
  $("mode-char").classList.toggle("on", m === 0);
  $("mode-name").classList.toggle("on", m === 1);
  if (data) renderAll();
}

start();
