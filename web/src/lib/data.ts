// Getting the race logs out of the server and keeping them current.
//
// The server hands over files; everything else happens here and in stats.ts.
// A race file never changes once written, so it is fetched once and kept; the
// poll is only asking "is there a new one, and is a race running now".

import { useCallback, useEffect, useRef, useState } from "react";
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

const logs = new Map<string, RaceLog>();

async function loadRace(dir: string, file: string): Promise<RaceLog> {
  const key = `${dir}/${file}`;
  const had = logs.get(key);
  if (had) return had;
  const res = await fetch(`/api/race/${dir}/${encodeURIComponent(file)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${file}: ${res.status}`);
  const log = new RaceLog(file, await res.text());
  logs.set(key, log);
  return log;
}

export function useSessions(): SessionListing[] {
  const [list, setList] = useState<SessionListing[]>([]);
  useEffect(() => {
    let alive = true;
    const tick = () =>
      getJson<SessionListing[]>("/api/sessions")
        .then((got) => alive && setList(got))
        .catch(() => {});
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  return list;
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
        const got = await getJson<SessionFile>(`/api/session/${dir}`);
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
          setState((s) => ({ ...s, error: String(err), loading: false }));
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
    return () => {
      alive = false;
      clearInterval(id);
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
        const got = await getJson<SessionFile>(`/api/session/${dir}`);
        const files = (got.meta?.races ?? []).map((r) => r.file);
        const races = await Promise.all(files.map((f) => loadRace(dir, f)));
        if (!alive) return;
        setState({
          stats: sessionStats(dir, got.meta ?? {}, got.players ?? {}, races),
          log: races.find((r) => r.file === file) ?? null,
          error: null,
        });
      } catch (err) {
        if (alive) setState((s) => ({ ...s, error: String(err) }));
      }
    })();
    return () => {
      alive = false;
    };
  }, [dir, file]);

  return state;
}
