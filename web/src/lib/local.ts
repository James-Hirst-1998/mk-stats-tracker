// Race logs loaded from files, for a copy of the dashboard with no races
// directory behind it.
//
// A hosted site cannot read anybody's disk, so a session is dropped in
// instead: the folder tools/track.py wrote, or just its .jsonl files. Nothing
// is uploaded. The text is kept in this browser's IndexedDB so a reload, or a
// link to one race, still finds it; if IndexedDB is unavailable the files last
// until the tab closes.

import { useSyncExternalStore } from "react";
import type { PlayersFile } from "./stats";

export interface LocalSession {
  dir: string;
  meta: { name?: string; started?: string; ended?: string; races: { file: string }[] };
  players: PlayersFile | null;
  /** File name to the log's text, as it was on disk. */
  races: Record<string, string>;
  /** When it was loaded, so a race cached from an older copy is not reused. */
  loaded: string;
}

export interface Picked {
  /** Where the file sat in what was picked, e.g. "20260915-cheeky/01-koopa-cape.jsonl". */
  path: string;
  file: File;
}

const DB = "mkw-races";
const STORE = "sessions";
/** Loaded dirs are prefixed so one can never be mistaken for a directory on disk. */
const PREFIX = "loaded-";

let sessions: LocalSession[] = [];
const listeners = new Set<() => void>();

function changed(next: LocalSession[]) {
  sessions = next;
  listeners.forEach((f) => f());
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "dir" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function run<T>(mode: IDBTransactionMode, work: (s: IDBObjectStore) => IDBRequest<T>) {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const req = work(db.transaction(STORE, mode).objectStore(STORE));
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      }),
  );
}

/** Settles once whatever an earlier visit loaded is back in memory. */
const ready: Promise<void> = run<LocalSession[]>("readonly", (s) => s.getAll())
  .then((got) => changed(sortNewest(got)))
  .catch(() => {});

function sortNewest(list: LocalSession[]) {
  return [...list].sort((a, b) =>
    String(b.meta.started ?? "").localeCompare(String(a.meta.started ?? "")),
  );
}

export function subscribe(f: () => void) {
  listeners.add(f);
  return () => {
    listeners.delete(f);
  };
}

export function useLocalSessions(): LocalSession[] {
  return useSyncExternalStore(subscribe, () => sessions);
}

export const isLocal = (dir: string) => dir.startsWith(PREFIX);

export async function localSession(dir: string): Promise<LocalSession | null> {
  await ready;
  return sessions.find((s) => s.dir === dir) ?? null;
}

async function keep(session: LocalSession) {
  changed(sortNewest([session, ...sessions.filter((s) => s.dir !== session.dir)]));
  await run("readwrite", (s) => s.put(session)).catch(() => {});
}

export async function forget(dir: string) {
  changed(sessions.filter((s) => s.dir !== dir));
  await run("readwrite", (s) => s.delete(dir)).catch(() => {});
}

/** Names typed at "Who is who", kept with the loaded files rather than on disk. */
export async function saveLocalPlayers(dir: string, players: PlayersFile) {
  const had = await localSession(dir);
  if (!had) throw new Error("that session is no longer loaded");
  await keep({ ...had, players: { ...had.players, ...players } });
}

function slugOf(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** The first line. A race log starts with its `race` header, so a file
 *  without one is not a race log. */
function headerOf(text: string) {
  const end = text.indexOf("\n");
  return parseJson(end < 0 ? text : text.slice(0, end)) as
    | { type?: string; recorded?: string }
    | null;
}

/** Read what was picked into sessions: one per folder holding race logs.
 *
 *  Picking the races/ directory itself loads every session in it. Loose files
 *  with no folder are one session. Returns the dirs loaded, and a line for
 *  each thing that was skipped and why. */
export async function loadFiles(picked: Picked[]) {
  await ready;
  const folders = new Map<string, Picked[]>();
  for (const p of picked) {
    const cut = p.path.lastIndexOf("/");
    const folder = cut < 0 ? "" : p.path.slice(0, cut);
    folders.set(folder, [...(folders.get(folder) ?? []), p]);
  }

  const loaded: string[] = [];
  const skipped: string[] = [];
  for (const [folder, files] of folders) {
    const races: Record<string, string> = {};
    let meta: Partial<LocalSession["meta"]> | null = null;
    let players: PlayersFile | null = null;

    for (const { file } of files) {
      if (file.name.endsWith(".jsonl")) {
        const text = await file.text();
        if (headerOf(text)?.type === "race") races[file.name] = text;
        else skipped.push(`${file.name}: not a race log`);
      } else if (file.name === "session.json") {
        meta = parseJson(await file.text()) as Partial<LocalSession["meta"]> | null;
      } else if (file.name === "players.json") {
        players = parseJson(await file.text()) as PlayersFile | null;
      }
    }

    const names = Object.keys(races);
    if (!names.length) {
      if (files.some((f) => f.file.name === "session.json"))
        skipped.push(`${folder || "those files"}: a session.json but no race logs`);
      continue;
    }

    // The index's order where it has one - it is the order they were raced -
    // then anything it does not list yet, by file name, which starts with the
    // race number.
    const index: { file?: string }[] = Array.isArray(meta?.races) ? meta.races : [];
    const listed = index
      .map((r) => r?.file)
      .filter((f): f is string => typeof f === "string" && f in races);
    const order = [...listed, ...names.filter((n) => !listed.includes(n)).sort()];
    const leaf = folder.split("/").pop() || "";
    const name = meta?.name || leaf || "loaded races";

    const session: LocalSession = {
      dir: PREFIX + (slugOf(leaf || name) || "races"),
      meta: {
        name,
        started: meta?.started ?? headerOf(races[order[0]])?.recorded,
        ended: meta?.ended,
        races: order.map((file) => ({ file })),
      },
      players,
      races,
      loaded: new Date().toISOString(),
    };
    await keep(session);
    loaded.push(session.dir);
  }

  if (!loaded.length && !skipped.length)
    skipped.push("No race logs in that. Pick a session folder from races/, or its .jsonl files.");
  return { loaded, skipped };
}

/** A real night shipped with the site, so somebody with no races of their own
 *  can see every screen. James chose which: four players, twelve races. Its
 *  players.json is left out, so it names characters rather than people. It
 *  goes through loadFiles like a dropped folder, so it is shown exactly as one. */
const EXAMPLE = "cheeky-12-sept-15th-26";

export async function loadExample(): Promise<string> {
  const dir = PREFIX + EXAMPLE;
  if (await localSession(dir)) return dir;
  const get = async (name: string): Promise<Picked> => {
    const res = await fetch(`/examples/${EXAMPLE}/${name}`);
    if (!res.ok) throw new Error(`${name}: ${res.status}`);
    return { path: `${EXAMPLE}/${name}`, file: new File([await res.text()], name) };
  };
  // The index says which race files there are, so only it is named here.
  const index = await get("session.json");
  const races = (parseJson(await index.file.text()) as { races?: { file: string }[] } | null)
    ?.races ?? [];
  const picked = [index, ...(await Promise.all(races.map((r) => get(r.file))))];
  const { loaded } = await loadFiles(picked);
  if (!loaded.length) throw new Error("the example did not load");
  return loaded[0];
}
