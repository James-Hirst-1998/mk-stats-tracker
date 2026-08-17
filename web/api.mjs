// Reading files off disk, and nothing else.
//
// Every number on the dashboard is computed in the browser from the race logs
// this hands over verbatim (web/src/lib), so this file has no idea what a race
// is. It is used twice: as Vite middleware in dev, and by server.mjs for a
// built copy. Same routes either way.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..");

export const RACES = process.env.MKW_RACES || path.join(REPO, "races");
export const ASSETS = path.join(REPO, "assets");

// A directory name arriving from the URL is never joined onto a path until it
// has been through this: no separators, no leading dot, and it has to be a
// session that actually exists.
function sessionDir(name) {
  if (!name || name.includes("/") || name.includes("\\") || name.startsWith("."))
    return null;
  const full = path.join(RACES, name);
  return fs.existsSync(path.join(full, "session.json")) ? full : null;
}

function raceFile(dir, name) {
  if (!name || name.includes("/") || name.includes("\\") || !name.endsWith(".jsonl"))
    return null;
  const full = path.join(dir, name);
  return fs.existsSync(full) ? full : null;
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null; // half-written by the tracker; the next poll gets it
  }
}

function sessions() {
  if (!fs.existsSync(RACES)) return [];
  const out = [];
  for (const name of fs.readdirSync(RACES)) {
    const dir = sessionDir(name);
    if (!dir) continue;
    const meta = readJson(path.join(dir, "session.json"));
    if (!meta) continue;
    out.push({
      dir: name,
      name: meta.name,
      started: meta.started,
      ended: meta.ended,
      races: (meta.races || []).length,
      live: fs.existsSync(path.join(dir, "live.json")),
    });
  }
  return out.sort((a, b) => String(b.started).localeCompare(String(a.started)));
}

function session(name) {
  const dir = sessionDir(name);
  if (!dir) return null;
  return {
    dir: name,
    meta: readJson(path.join(dir, "session.json")),
    players: readJson(path.join(dir, "players.json")),
    live: readJson(path.join(dir, "live.json")),
  };
}

const JSON_HEAD = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};

/** The whole body, or null if it is not JSON or is longer than 64 kB. */
function body(req) {
  return new Promise((resolve) => {
    let text = "";
    req.on("data", (chunk) => {
      text += chunk;
      if (text.length > 65536) {
        text = "";
        req.destroy();
        resolve(null);
      }
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(text));
      } catch {
        resolve(null);
      }
    });
    req.on("error", () => resolve(null));
  });
}

function writeJson(file, value) {
  // Written beside and renamed, so a poll landing mid-write reads the old
  // file rather than half of the new one.
  const tmp = file + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(value, null, 1) + "\n");
  fs.renameSync(tmp, file);
}

/** What the dashboard is allowed to put in players.json: names, and which
 *  character each one is. Everything else in the file is left as it was. */
function savePlayers(dir, sent) {
  const file = path.join(dir, "players.json");
  const had = readJson(file) || {};
  const players = [];
  for (const p of Array.isArray(sent?.players) ? sent.players : []) {
    const name = String(p?.name ?? "").trim().slice(0, 40);
    if (!name) continue;
    const one = { name };
    if (Number.isInteger(p?.character)) one.character = p.character;
    if (p?.human === true) one.human = true;
    players.push(one);
  }
  if (!players.length) return null;
  const next = { ...had, players };
  writeJson(file, next);
  return next;
}

/** Where a lap starts on each course, and which way round it goes. Set by
 *  hand at #/tracks, because a drawing does not say. */
function saveStarts(sent) {
  const out = {};
  for (const [code, value] of Object.entries(sent || {})) {
    if (!/^\d+$/.test(code)) continue;
    const x = Number(value?.x);
    const y = Number(value?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    out[code] = {
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      reverse: value?.reverse === true,
    };
  }
  fs.mkdirSync(path.join(ASSETS, "tracks"), { recursive: true });
  writeJson(path.join(ASSETS, "tracks", "starts.json"), out);
  return out;
}

/** Handle one request. Returns true if it was ours. */
export function handle(req, res) {
  const url = new URL(req.url, "http://localhost");
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] !== "api") return false;

  const send = (code, body, head = JSON_HEAD) => {
    res.writeHead(code, head);
    res.end(typeof body === "string" ? body : JSON.stringify(body));
    return true;
  };

  if (parts.length === 2 && parts[1] === "sessions") return send(200, sessions());

  // The only two things the dashboard writes, both of them things a person
  // knows and a race log does not: who the players are, and where a lap
  // starts on each course.
  // A write can fail for a reason the person can act on - a session recorded
  // under sudo leaves a directory this process cannot write to - so it comes
  // back as a message rather than as a stack trace. Left unhandled it would
  // be a rejected promise, which takes the whole server down with it.
  const put = (work) => {
    body(req)
      .then(work)
      .catch((err) => send(500, { error: String(err.message || err) }));
    return true;
  };

  if (req.method === "PUT" && parts.length === 4 && parts[1] === "session"
      && parts[3] === "players") {
    const dir = sessionDir(parts[2]);
    if (!dir) return send(404, { error: "no such session" });
    return put((sent) => {
      const saved = savePlayers(dir, sent);
      send(saved ? 200 : 400, saved || { error: "no players in that" });
    });
  }

  if (req.method === "PUT" && parts.length === 2 && parts[1] === "starts")
    return put((sent) => send(200, saveStarts(sent)));

  if (parts.length === 3 && parts[1] === "session") {
    const got = session(parts[2]);
    return got ? send(200, got) : send(404, { error: "no such session" });
  }

  if (parts.length === 4 && parts[1] === "race") {
    const dir = sessionDir(parts[2]);
    const file = dir && raceFile(dir, parts[3]);
    if (!file) return send(404, { error: "no such race" });
    // The log goes over as-is: parsing JSON Lines is the client's job, and a
    // race file is tens of kilobytes.
    return send(200, fs.readFileSync(file, "utf8"), {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    });
  }

  return send(404, { error: "unknown endpoint" });
}

const MIME = {
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".json": "application/json; charset=utf-8",
};

/** Character art and course outlines, served out of the repo's assets/ so the
 *  recorder and the dashboard share one copy rather than web/ holding its own. */
function sendAsset(req, res) {
  const url = new URL(req.url, "http://localhost").pathname;
  if (!url.startsWith("/assets/")) return false;
  const full = path.normalize(path.join(ASSETS, decodeURIComponent(url.slice(8))));
  if (!full.startsWith(ASSETS) || !fs.existsSync(full) || fs.statSync(full).isDirectory())
    return false;
  res.writeHead(200, {
    "Content-Type": MIME[path.extname(full)] || "application/octet-stream",
    // Art never changes. starts.json is edited from the app itself, so it
    // must not be cached or a save reads back as no change.
    "Cache-Control": path.extname(full) === ".json" ? "no-store" : "max-age=86400",
  });
  res.end(fs.readFileSync(full));
  return true;
}

/** Vite plugin: the same routes, plus /assets served out of the repo. */
export function racesApi() {
  return {
    name: "mkw-races-api",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (handle(req, res) || sendAsset(req, res)) return;
        next();
      });
    },
  };
}
