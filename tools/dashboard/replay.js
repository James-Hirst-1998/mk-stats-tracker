/* Replay one race from its stored progress traces. Everything shown is
   derived from /api/replay; this file only animates it.

   The track drawing prefers /assets/tracks/<course-slug>.svg - a file whose
   first <path> is the circuit centreline, start line at the path start,
   direction of travel along it. Until those exist, a generic loop stands in
   and says so. */

const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const sessionDir = params.get("session");
const raceFile = params.get("race");

const fmt = (s) => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-")
             .replace(/^-+|-+$/g, "") || "x";
}

let d = null;             // /api/replay payload
let comp = {};            // slot -> cumulative progress per sample
let t = 0, playing = false, speed = 4, last = null, tick = 0;
let trk, L, dots = {}, labs = {};

function rebuildProgress() {
  // Traces are stored as raw progress, which wraps at the finish line;
  // count the wraps back so ordering and drawing are continuous.
  comp = {};
  for (const [slot, row] of Object.entries(d.traces)) {
    let lap = 0;
    const out = [row[0]];
    for (let i = 1; i < row.length; i++) {
      if (row[i] < row[i - 1] - 0.5) lap++;
      out.push(lap + row[i]);
    }
    comp[slot] = out;
  }
}

function at(slot, time) {
  const a = comp[slot];
  const x = time / d.sample_every;
  const i = Math.min(a.length - 2, Math.max(0, Math.floor(x)));
  const f = Math.min(1, Math.max(0, x - i));
  return a[i] + (a[i + 1] - a[i]) * f;
}

async function loadTrack() {
  const name = slug(d.course_name);
  try {
    const res = await fetch(`/assets/tracks/${name}.svg`);
    if (res.ok) {
      const text = await res.text();
      const doc = new DOMParser().parseFromString(text, "image/svg+xml");
      const path = doc.querySelector("path");
      const vb = doc.documentElement.getAttribute("viewBox");
      if (path && vb) {
        $("stage").setAttribute("viewBox", vb);
        $("trk").setAttribute("d", path.getAttribute("d"));
        $("tracknote").textContent = "";
        return;
      }
    }
  } catch (e) { /* no outline yet */ }
  $("tracknote").textContent = "placeholder outline, not the real circuit";
}

function setup() {
  trk = $("trk");
  $("trkline").setAttribute("d", trk.getAttribute("d"));
  L = trk.getTotalLength();
  const p0 = trk.getPointAtLength(0), p1 = trk.getPointAtLength(3);
  const dx = p1.x - p0.x, dy = p1.y - p0.y, n = Math.hypot(dx, dy) || 1;
  const sl = $("startline");
  sl.setAttribute("x1", p0.x - dy / n * 9); sl.setAttribute("y1", p0.y + dx / n * 9);
  sl.setAttribute("x2", p0.x + dy / n * 9); sl.setAttribute("y2", p0.y - dx / n * 9);

  const g = $("karts");
  g.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  for (const [slot, who] of Object.entries(d.field)) {
    const color = who.player != null ? PALETTE[who.player] : "#adb5bd";
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("r", who.player != null ? 5.5 : 4);
    c.setAttribute("fill", color);
    c.setAttribute("stroke", "#ffffff");
    c.setAttribute("stroke-width", "1.2");
    g.appendChild(c);
    dots[slot] = c;
    if (who.player != null || isWinner(slot)) {
      const tx = document.createElementNS(ns, "text");
      tx.setAttribute("font-size", "11");
      tx.setAttribute("font-weight", "600");
      tx.setAttribute("text-anchor", "middle");
      tx.setAttribute("fill", who.player != null ? "#1a1b1e" : "#868e96");
      tx.textContent = who.name;
      g.appendChild(tx);
      labs[slot] = tx;
    }
  }
  $("scrub").max = d.duration;
  $("jumps").innerHTML = jumpChips().map(([label, when]) =>
    `<button class="btn" style="font-size:12px" onclick="jumpTo(${when})">${label}</button>`).join("");
}

function isWinner(slot) {
  const last = comp[slot];
  return last && Math.max(...Object.values(comp).map(a => a[a.length - 1])) === last[last.length - 1];
}

function jumpChips() {
  const chips = [];
  for (const e of d.events)
    if (e.text.startsWith("Blue shell") && chips.length < 3)
      chips.push([`${e.text} ${fmt(e.t)}`, Math.max(0, e.t - 3)]);
  chips.push([`Final lap`, Math.max(0, d.duration - (d.avg_lap || 60))]);
  return chips;
}

window.jumpTo = (when) => { t = when; setPlay(true); };

function setPlay(p) {
  playing = p;
  $("play").textContent = p ? "❚❚" : "▶";
}

function draw() {
  for (const slot of Object.keys(d.field)) {
    const c = at(slot, t);
    const f = ((c % 1) + 1) % 1;
    const dist = f * L;
    const p = trk.getPointAtLength(dist);
    const q = trk.getPointAtLength((dist + 3) % L);
    const dx = q.x - p.x, dy = q.y - p.y, n = Math.hypot(dx, dy) || 1;
    const off = ((+slot * 5) % 13 - 6) * 0.7;
    const x = p.x - dy / n * off, y = p.y + dx / n * off;
    dots[slot].setAttribute("cx", x); dots[slot].setAttribute("cy", y);
    if (labs[slot]) { labs[slot].setAttribute("x", x); labs[slot].setAttribute("y", y - 9); }
  }
  if (++tick % 6 === 0 || !playing) {
    const order = Object.keys(d.field).map(s => [s, at(s, t)])
      .sort((a, b) => b[1] - a[1]);
    const lead = order[0][1];
    $("board").innerHTML = order.map(([s, c], k) => {
      const who = d.field[s];
      const color = who.player != null ? PALETTE[who.player] : "#adb5bd";
      const gap = (lead - c) * (d.avg_lap || 60);
      return `<div class="row${who.player != null ? " tracked" : ""}">
        <span class="pos">${k + 1}</span>
        <span class="chip" style="background:${color};margin:0"></span>
        <span>${who.name}</span>
        <span class="gap">${k === 0 ? "" : "+" + gap.toFixed(1)}</span></div>`;
    }).join("");
    let ev = null;
    for (const e of d.events) { if (e.t <= t) ev = e; else break; }
    $("ticker").innerHTML = ev
      ? `<span class="t">${fmt(ev.t)}</span>${ev.text}`
      : `<span class="t">0:00</span>Lights out`;
    $("lapclock").textContent =
      `Lap ${Math.min(d.laps, Math.max(1, Math.floor(lead)))} of ${d.laps} · ${fmt(t)}`;
    $("scrub").value = t;
  }
}

function frame(now) {
  if (playing) {
    if (last != null) t = Math.min(d.duration, t + (now - last) / 1000 * speed);
    if (t >= d.duration) setPlay(false);
  }
  last = now;
  draw();
  requestAnimationFrame(frame);
}

async function start() {
  if (!sessionDir || !raceFile) { $("subtitle").textContent = "no race given"; return; }
  const res = await fetch(`/api/replay/${sessionDir}/${raceFile}`);
  if (!res.ok) { $("subtitle").textContent = "replay data not found"; return; }
  d = await res.json();
  $("title").textContent = d.course_name;
  $("subtitle").textContent = `${d.laps} laps · ${fmt(d.duration)}`;
  $("back").href = `/?session=${sessionDir}`;
  rebuildProgress();
  await loadTrack();
  setup();
  $("play").onclick = () => setPlay(!playing);
  $("scrub").oninput = (e) => { t = +e.target.value; };
  $("speed").onchange = (e) => { speed = +e.target.value; };
  draw();
  requestAnimationFrame(frame);
}

start();
