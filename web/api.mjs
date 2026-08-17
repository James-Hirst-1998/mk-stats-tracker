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
    "Cache-Control": "max-age=86400",
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
