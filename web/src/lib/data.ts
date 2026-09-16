// Getting the race logs out of the server and keeping them current.
//
// The server hands over files; everything else happens here and in stats.ts.
// A race file never changes once written, so it is fetched once and kept; the
// poll is only asking "is there a new one, and is a race running now".
//
// A hosted copy has no server, so sessions can also come from files loaded in
// the browser (local.ts). Those are looked up first and never polled.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  isLocal,
  localSession,
  subscribe,
  useLocalSessions,
} from "./local";
import { RaceLog } from "./racelog";
import { sessionStats, type PlayersFile, type SessionStats } from "./stats";

export const POLL_MS = 2000;

export interface SessionListing {
  dir: string;
  name: string;
  started: string;
  ended?: string;
  races: number;
  live: boolean;
  /** Loaded from files in this browser rather than read off disk. */
  local?: boolean;
}

export interface Live {
  race: number;
  course: number | null;
  started: string;
}

interface SessionFile {
  dir: string;
  meta: { name?: string; started?: string; races?: { file: string }[] };
  players: PlayersFile | null;
  live: Live | null;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json() as Promise<T>;
}

/** Whether a races server is there at all, asked once. A static host answers
 *  /api with a 404 or with index.html, and neither is JSON. */
const hasApi: Promise<boolean> = fetch("/api/sessions", { cache: "no-store" })
  .then((r) => r.ok && Boolean(r.headers.get("content-type")?.includes("json")))
  .catch(() => false);

export function useHasApi(): boolean | null {
  const [api, setApi] = useState<boolean | null>(null);
  useEffect(() => {
    hasApi.then(setApi);
  }, []);
  return api;
}

async function getSession(dir: string): Promise<SessionFile> {
  const local = await localSession(dir);
  if (local) return { dir, meta: local.meta, players: local.players, live: null };
  if (isLocal(dir) || !(await hasApi))
    throw new Error(
      "That session is not loaded in this browser. Load its folder again from the stats page.",
    );
  return getJson<SessionFile>(`/api/session/${dir}`);
}

const logs = new Map<string, RaceLog>();

async function loadRace(dir: string, file: string): Promise<RaceLog> {
  const local = await localSession(dir);
  // A folder loaded again replaces the copy, so the load time is in the key.
  const key = `${dir}/${file}/${local?.loaded ?? ""}`;
  const had = logs.get(key);
  if (had) return had;
  let text: string;
  if (local) {
    if (!(file in local.races)) throw new Error(`${file}: not in the loaded files`);
    text = local.races[file];
  } else {
    const res = await fetch(`/api/race/${dir}/${encodeURIComponent(file)}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${file}: ${res.status}`);
    text = await res.text();
  }
  const log = new RaceLog(file, text);
  logs.set(key, log);
  return log;
}

const message = (err: unknown) => (err instanceof Error ? err.message : String(err));

/** Every session: the ones loaded in this browser first, then the ones on
 *  disk. `ready` is false until the server has been asked, so an empty list
 *  can be told apart from one that has not arrived. */
export function useSessions(): { list: SessionListing[]; ready: boolean } {
  const local = useLocalSessions();
  const [disk, setDisk] = useState<SessionListing[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    let id: ReturnType<typeof setInterval> | undefined;
    const tick = () =>
      getJson<SessionListing[]>("/api/sessions")
        .then((got) => alive && setDisk(got))
        .catch(() => {});
    hasApi.then(async (api) => {
      if (api) await tick();
      if (!alive) return;
      setReady(true);
      if (api) id = setInterval(tick, POLL_MS);
    });
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const loaded: SessionListing[] = local.map((s) => ({
    dir: s.dir,
    name: s.meta.name ?? s.dir,
    started: s.meta.started ?? "",
    ended: s.meta.ended,
    races: s.meta.races.length,
    live: false,
    local: true,
  }));
  return { list: [...loaded, ...disk], ready };
}

export interface Loaded {
  stats: SessionStats | null;
  live: Live | null;
  error: string | null;
  loading: boolean;
}

/** The session, kept up to date while races are being recorded. */
export function useSession(dir: string | null): Loaded {
  const [state, setState] = useState<Loaded>({
    stats: null,
    live: null,
    error: null,
    loading: Boolean(dir),
  });
  // What the last poll saw, so an unchanged session costs one small request
  // and no recomputation.
  const seen = useRef<string>("");

  const refresh = useCallback(
    async (alive: () => boolean) => {
      if (!dir) return;
      try {
        const got = await getSession(dir);
        const files = (got.meta?.races ?? []).map((r) => r.file);
        const fingerprint = JSON.stringify([
          files,
          got.players,
          got.live,
          got.meta?.name,
        ]);
        if (fingerprint === seen.current) return;
        const races = await Promise.all(files.map((f) => loadRace(dir, f)));
        if (!alive()) return;
        seen.current = fingerprint;
        setState({
          stats: sessionStats(dir, got.meta ?? {}, got.players ?? {}, races),
          live: got.live,
          error: null,
          loading: false,
        });
      } catch (err) {
        if (alive())
          setState((s) => ({ ...s, error: message(err), loading: false }));
      }
    },
    [dir],
  );

  useEffect(() => {
    seen.current = "";
    setState({ stats: null, live: null, error: null, loading: Boolean(dir) });
    if (!dir) return;
    let alive = true;
    const check = () => alive;
    refresh(check);
    const id = setInterval(() => refresh(check), POLL_MS);
    // Names saved against a loaded session show at once, not on the next poll.
    const off = subscribe(() => refresh(check));
    return () => {
      alive = false;
      clearInterval(id);
      off();
    };
  }, [dir, refresh]);

  return state;
}

/** One race on its own, for the replay screen. */
export function useRace(dir: string | null, file: string | null) {
  const [state, setState] = useState<{
    stats: SessionStats | null;
    log: RaceLog | null;
    error: string | null;
  }>({ stats: null, log: null, error: null });

  useEffect(() => {
    if (!dir || !file) return;
    let alive = true;
    (async () => {
      try {
        const got = await getSession(dir);
        const files = (got.meta?.races ?? []).map((r) => r.file);
        const races = await Promise.all(files.map((f) => loadRace(dir, f)));
        if (!alive) return;
        setState({
          stats: sessionStats(dir, got.meta ?? {}, got.players ?? {}, races),
          log: races.find((r) => r.file === file) ?? null,
          error: null,
        });
      } catch (err) {
        if (alive) setState((s) => ({ ...s, error: message(err) }));
      }
    })();
    return () => {
      alive = false;
    };
  }, [dir, file]);

  return state;
}
