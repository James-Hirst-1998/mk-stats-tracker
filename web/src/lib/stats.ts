// Everything the dashboard shows, computed from stored race logs.
//
// Same files in, same numbers out: no randomness, no clock, no model. A number
// on screen that cannot be derived here cannot be shown, which keeps one
// source for every figure and keeps the components to rendering.
//
// The unit of identity is the *player*: a person who keeps the same character
// for a night. `players.json` in a session directory says who is tracked:
//
//     {"planned_races": 32,
//      "players": [{"name": "James", "human": true},
//                  {"name": "Shikhar", "character": 22}]}
//
// An entry matches by character id, or - `"human": true` - whichever racer the
// game says is human that race, which survives a character change between
// races. Without the file the tracked players are the humans found in the
// races, named by their characters. CPUs always count as attackers, victims
// and opponents; they just don't get a row of their own.

import { CHARACTERS, ITEMS, VS_POINTS, courseName } from "../data/names";
import type { RaceEvent, RaceLog } from "./racelog";
import { duration, hitBy, landed, summary } from "./report";

/** Items whose use is a boost. Trick, wheelie and drift boosts are not in the
 *  logs at all, so "boosts" on the dashboard means exactly these. */
export const BOOST_ITEMS = new Set(
  Object.entries(ITEMS)
    .filter(([, name]) =>
      ["Mushroom", "Triple Mushrooms", "Golden Mushroom", "Star", "Bullet Bill"].includes(
        name,
      ),
    )
    .map(([id]) => Number(id)),
);

/** World-object type of the Blue Shell. */
export const BLUE_OBJECT = 5;

/** Seconds between samples of the position worm and the replay traces. */
export const SAMPLE_EVERY = 2.0;

export interface PlayerSpec {
  name: string;
  character?: number;
  human?: boolean;
}

export interface TeamSpec {
  name: string;
  members: number[];
}

export interface PlayersFile {
  planned_races?: number;
  players?: PlayerSpec[];
  teams?: TeamSpec[];
}

export interface Player extends PlayerSpec {
  index: number;
  characterName: string | null;
}

export interface Row {
  slot: number;
  character: number | null;
  characterName: string;
  position: number | null;
  points: number;
  finished: boolean;
  time: number | null;
  bestLap: number | null;
  /** Seconds in first, countdown-corrected. */
  led: number;
  /** The same seconds counted from the position events, as a cross-check. */
  ledFromEvents: number;
  thrown: number;
  landed: number;
  taken: number;
  caught: number;
  blues: number;
  boosts: number;
  out: number;
}

export interface Winner {
  slot: number;
  character: number | null;
  characterName: string;
  cpu: boolean;
  time: number | null;
  player: number | null;
}

export interface FirstBlood {
  player: number | null;
  name: string;
  t: number;
}

export interface RaceStats {
  n: number;
  file: string;
  course: number | null;
  courseName: string;
  laps: number | null;
  recorded: string | null;
  duration: number;
  winner: Winner | null;
  firstBlood: FirstBlood | null;
  rows: Map<number, Row>;
  log: RaceLog;
}

export interface Duel {
  from: string;
  to: string;
  count: number;
}

export interface SessionStats {
  dir: string;
  name: string;
  started: string | null;
  plannedRaces: number | null;
  players: Player[];
  teams: TeamSpec[];
  races: RaceStats[];
  duels: Duel[];
  awards: Awards;
}

/** The rows of every dashboard table. */
export function trackedPlayers(logs: RaceLog[], config: PlayersFile): Player[] {
  const specs = config.players?.length ? config.players : humansIn(logs);
  return specs.map((p, index) => ({
    ...p,
    index,
    characterName: p.character == null ? null : (CHARACTERS[p.character] ?? null),
  }));
}

function humansIn(logs: RaceLog[]): PlayerSpec[] {
  const seen: PlayerSpec[] = [];
  for (const log of logs)
    for (const r of log.racers)
      if (!r.cpu && !seen.some((p) => p.character === r.character))
        seen.push({
          name: CHARACTERS[r.character] ?? `racer ${r.slot}`,
          character: r.character,
        });
  return seen;
}

/** Which slot this player raced in, or null if they sat it out. */
export function slotOf(player: PlayerSpec, log: RaceLog): number | null {
  for (const r of log.racers) {
    if (player.human) {
      if (!r.cpu) return r.slot;
    } else if (r.character === player.character) return r.slot;
  }
  return null;
}

/** {player index: slot}, for one race. */
export function slotsOf(players: Player[], log: RaceLog): Map<number, number> {
  const out = new Map<number, number>();
  players.forEach((p, i) => {
    const s = slotOf(p, log);
    if (s != null) out.set(i, s);
  });
  return out;
}

/** Deterministic short name for what a hit was. */
export function causeOf(e: RaceEvent): string {
  return hitBy(e);
}

function hits(log: RaceLog): RaceEvent[] {
  return log.events.filter((e) => e.type === "hit" && !e.after);
}

export function rowsFor(log: RaceLog, players: Player[]): Map<number, Row> {
  const stats = summary(log);
  const slots = slotsOf(players, log);
  const rows = new Map<number, Row>();
  const landedHits = hits(log);
  for (const [i, slot] of slots) {
    const r = stats.get(slot);
    if (!r) continue;
    const uses = log.events.filter(
      (e) => e.type === "use" && !e.after && e.slot === slot,
    );
    rows.set(i, {
      slot,
      character: r.character,
      characterName: log.field.name(slot),
      position: r.position,
      points: r.position == null ? 0 : (VS_POINTS[r.position] ?? 0),
      finished: r.finished,
      time: r.time,
      bestLap: r.bestLap,
      led: round(r.leading, 1),
      ledFromEvents: round(r.leadingFromEvents, 1),
      thrown: uses.length,
      landed: landed(r),
      taken: r.hitsTaken,
      caught: r.caught,
      blues: landedHits.filter((e) => e.slot === slot && e.object === BLUE_OBJECT)
        .length,
      boosts: uses.filter((e) => BOOST_ITEMS.has(e.item as number)).length,
      out: round(r.out, 1),
    });
  }
  return rows;
}

/** Who hit whom across any set of races, so the slider moves these too. */
export function duelTotals(races: RaceStats[], players: Player[]): Duel[] {
  const total = new Map<string, number>();
  for (const race of races)
    for (const [key, n] of duelsIn(race.log, players))
      total.set(key, (total.get(key) ?? 0) + n);
  return [...total]
    .map(([key, count]) => {
      const [from, to] = key.split(">");
      return { from, to, count };
    })
    .sort((a, b) => b.count - a.count);
}

/** Who hit whom, keyed by player index where tracked and by character
 *  ("c17") where not, so a CPU nemesis keeps one identity across the night. */
function duelsIn(log: RaceLog, players: Player[]): Map<string, number> {
  const slots = slotsOf(players, log);
  const bySlot = new Map([...slots].map(([i, s]) => [s, i]));
  const out = new Map<string, number>();
  const key = (slot: number) => {
    const i = bySlot.get(slot);
    if (i != null) return String(i);
    const c = log.racer(slot)?.character;
    return `c${c ?? -1}`;
  };
  for (const e of hits(log)) {
    const by = e.by ?? [];
    if (by.length !== 1 || e.slot == null) continue;
    const k = `${key(by[0])}>${key(e.slot)}`;
    out.set(k, (out.get(k) ?? 0) + 1);
  }
  return out;
}

/** The first cleanly-attributed hit of the race: who drew it, and when.
 *
 *  `player` is the tracked-player index when it was one of them, so the UI can
 *  honour the character/name toggle; `name` is the character for a CPU. */
export function firstBlood(log: RaceLog, players: Player[]): FirstBlood | null {
  const slots = slotsOf(players, log);
  for (const e of log.events) {
    if (e.type !== "hit" || e.after) continue;
    const by = e.by ?? [];
    if (by.length !== 1) continue;
    const owner = [...slots].find(([, s]) => s === by[0])?.[0] ?? null;
    return {
      player: owner,
      name: owner != null ? players[owner].name : log.field.name(by[0]),
      t: round(e.t, 1),
    };
  }
  return null;
}

export function winnerOf(log: RaceLog, players: Player[]): Winner | null {
  const s = log.standings.find((x) => x.position === 1);
  if (!s) return null;
  const r = log.racer(s.slot);
  const slots = slotsOf(players, log);
  return {
    slot: s.slot,
    character: r?.character ?? null,
    characterName: log.field.name(s.slot),
    cpu: Boolean(r?.cpu),
    time: s.time,
    player: [...slots].find(([, slot]) => slot === s.slot)?.[0] ?? null,
  };
}

export interface Awards {
  blueMagnet: { players: number[]; count: number } | null;
  sniper: { players: number[]; rate: number; landed: number; thrown: number } | null;
  firstBlood: { player: number | null; name: string | null; count: number } | null;
  collapse: {
    player: number;
    led: number;
    position: number;
    race: number;
    courseName: string;
  } | null;
}

/** Whole-night awards. Fixed rules, so the same night gives the same winners;
 *  ties are shown as ties rather than broken arbitrarily. */
export function awards(races: RaceStats[], players: Player[]): Awards {
  const totals = players.map(() => ({ blues: 0, thrown: 0, landed: 0 }));
  let collapse: Awards["collapse"] = null;
  for (const race of races) {
    for (const [i, row] of race.rows) {
      totals[i].blues += row.blues;
      totals[i].thrown += row.thrown;
      totals[i].landed += row.landed;
      if (row.position != null && row.position > 3 && row.led >= 10) {
        if (collapse == null || row.led > collapse.led)
          collapse = {
            player: i,
            led: row.led,
            position: row.position,
            race: race.n,
            courseName: race.courseName,
          };
      }
    }
  }

  const best = Math.max(0, ...totals.map((t) => t.blues));
  const magnet = best > 0 ? totals.flatMap((t, i) => (t.blues === best ? [i] : [])) : [];

  let sniper: number[] = [];
  let rate = 0;
  totals.forEach((t, i) => {
    if (t.thrown < 5) return; // a lucky first shell is not marksmanship
    const r = t.landed / t.thrown;
    if (r > rate) {
      sniper = [i];
      rate = r;
    } else if (r === rate && r > 0) sniper.push(i);
  });

  const bloods = new Map<string, number>();
  for (const race of races) {
    const fb = race.firstBlood;
    if (!fb) continue;
    const key = fb.player != null ? String(fb.player) : fb.name;
    bloods.set(key, (bloods.get(key) ?? 0) + 1);
  }
  const blood = [...bloods].sort((a, b) => b[1] - a[1])[0];
  const bloodIsPlayer = blood != null && /^\d+$/.test(blood[0]);

  return {
    blueMagnet: magnet.length ? { players: magnet, count: best } : null,
    sniper: sniper.length
      ? {
          players: sniper,
          rate: round(rate, 2),
          landed: sniper.reduce((n, i) => n + totals[i].landed, 0),
          thrown: sniper.reduce((n, i) => n + totals[i].thrown, 0),
        }
      : null,
    firstBlood: blood
      ? {
          player: bloodIsPlayer ? Number(blood[0]) : null,
          name: bloodIsPlayer ? null : blood[0],
          count: blood[1],
        }
      : null,
    collapse,
  };
}

export function sessionStats(
  dir: string,
  meta: { name?: string; started?: string },
  config: PlayersFile,
  logs: RaceLog[],
): SessionStats {
  const players = trackedPlayers(logs, config);
  const races: RaceStats[] = logs.map((log, k) => {
    return {
      n: k + 1,
      file: log.file,
      course: log.course,
      courseName: courseName(log.course),
      laps: log.meta.laps ?? null,
      recorded: log.meta.recorded ?? null,
      duration: round(duration(log), 1),
      winner: winnerOf(log, players),
      firstBlood: firstBlood(log, players),
      rows: rowsFor(log, players),
      log,
    };
  });
  return {
    dir,
    name: meta.name ?? dir,
    started: meta.started ?? null,
    plannedRaces: config.planned_races ?? null,
    players,
    teams: config.teams ?? [],
    races,
    duels: duelTotals(races, players),
    awards: awards(races, players),
  };
}

export interface Totals {
  races: number;
  points: number;
  wins: number;
  podiums: number;
  avgPosition: number | null;
  bestPosition: number | null;
  led: number;
  thrown: number;
  landed: number;
  taken: number;
  blues: number;
  boosts: number;
  out: number;
}

/** One player's night so far. The slider on the dashboard is just a shorter
 *  list of races going into this. */
export function totalsFor(races: RaceStats[], player: number): Totals {
  const rows = races.map((r) => r.rows.get(player)).filter((r) => r != null);
  const finishes = rows.map((r) => r.position).filter((p): p is number => p != null);
  const sum = (pick: (r: Row) => number) => rows.reduce((n, r) => n + pick(r), 0);
  return {
    races: rows.length,
    points: sum((r) => r.points),
    wins: finishes.filter((p) => p === 1).length,
    podiums: finishes.filter((p) => p <= 3).length,
    avgPosition: finishes.length
      ? round(finishes.reduce((a, b) => a + b, 0) / finishes.length, 1)
      : null,
    bestPosition: finishes.length ? Math.min(...finishes) : null,
    led: round(sum((r) => r.led), 1),
    thrown: sum((r) => r.thrown),
    landed: sum((r) => r.landed),
    taken: sum((r) => r.taken),
    blues: sum((r) => r.blues),
    boosts: sum((r) => r.boosts),
    out: round(sum((r) => r.out), 1),
  };
}

/** Cumulative points after each race, index 0 = after race 1. */
export function pointsSeries(races: RaceStats[], player: number): number[] {
  let total = 0;
  return races.map((r) => (total += r.rows.get(player)?.points ?? 0));
}

// --- one race: the worm chart and its markers ------------------------------

export interface Marker {
  player: number;
  t: number;
  index: number;
  position: number | null;
  cause: string;
  blue: boolean;
  by: string[];
  caught: boolean;
  guess: boolean;
}

export interface RaceDetail {
  /** {player index: position every SAMPLE_EVERY seconds}. */
  series: Map<number, number[]>;
  markers: Marker[];
  lapStarts: { lap: number; t: number }[];
  steps: number;
}

/** {slot: position every SAMPLE_EVERY seconds}, from the pos events. */
export function positionSeries(log: RaceLog): Map<number, number[]> {
  const swaps = log.ofType("pos").sort((a, b) => a.t - b.t);
  const end = duration(log);
  const at = new Map<number, number>();
  for (const e of swaps) if (!at.has(e.slot!)) at.set(e.slot!, e.from as number);
  for (const r of log.racers) if (!at.has(r.slot)) at.set(r.slot, r.grid);

  const series = new Map<number, number[]>([...at.keys()].map((s) => [s, []]));
  let i = 0;
  const steps = Math.floor(end / SAMPLE_EVERY) + 1;
  for (let k = 0; k <= steps; k++) {
    const t = k * SAMPLE_EVERY;
    while (i < swaps.length && swaps[i].t <= t) {
      at.set(swaps[i].slot!, swaps[i].to as number);
      i++;
    }
    for (const [s, p] of at) series.get(s)!.push(p);
  }
  return series;
}

export function raceDetail(log: RaceLog, players: Player[]): RaceDetail {
  const bySlot = positionSeries(log);
  const slots = slotsOf(players, log);
  const series = new Map<number, number[]>();
  for (const [i, slot] of slots) {
    const row = bySlot.get(slot);
    if (row) series.set(i, row);
  }
  const markers: Marker[] = [];
  for (const e of log.events) {
    if (e.type !== "hit" || e.after || e.slot == null) continue;
    const owner = [...slots].find(([, s]) => s === e.slot)?.[0];
    if (owner == null) continue;
    const row = series.get(owner) ?? [];
    const index = Math.min(Math.round(e.t / SAMPLE_EVERY), Math.max(row.length - 1, 0));
    markers.push({
      player: owner,
      t: round(e.t, 1),
      index,
      position: row.length ? row[index] : null,
      cause: causeOf(e),
      blue: e.object === BLUE_OBJECT,
      by: (e.by ?? []).map((s) => nameOfSlot(s, log, players, slots)),
      caught: Boolean(e.caught),
      guess: Boolean(e.guess),
    });
  }
  return {
    series,
    markers,
    lapStarts: lapStarts(log),
    steps: Math.max(0, ...[...series.values()].map((r) => r.length)),
  };
}

function nameOfSlot(
  slot: number,
  log: RaceLog,
  players: Player[],
  slots: Map<number, number>,
): string {
  const i = [...slots].find(([, s]) => s === slot)?.[0];
  return i != null ? players[i].name : log.field.name(slot);
}

/** When each lap after the first began: the first crossing per lap. */
export function lapStarts(log: RaceLog): { lap: number; t: number }[] {
  const firsts = new Map<number, number>();
  for (const e of log.ofType("lap")) {
    const lap = e.lap ?? 0;
    if (lap >= 1 && !firsts.has(lap + 1)) firsts.set(lap + 1, round(e.t, 1));
  }
  return [...firsts]
    .sort((a, b) => a[0] - b[0])
    .map(([lap, t]) => ({ lap, t }));
}

// --- the replay screen -----------------------------------------------------

export interface ReplayField {
  slot: number;
  name: string;
  character: number | null;
  cpu: boolean;
  player: number | null;
}

export interface ReplayData {
  courseName: string;
  course: number | null;
  laps: number | null;
  duration: number;
  field: ReplayField[];
  events: { t: number; text: string }[];
  /** Median lap, for turning a progress gap into rough seconds. */
  avgLap: number | null;
}

export function replayData(log: RaceLog, players: Player[]): ReplayData {
  const slots = slotsOf(players, log);
  const named = new Map([...slots].map(([i, s]) => [s, players[i].name]));
  const field: ReplayField[] = log.racers.map((r) => ({
    slot: r.slot,
    name: named.get(r.slot) ?? log.field.name(r.slot),
    character: r.character,
    cpu: Boolean(r.cpu),
    player: [...slots].find(([, s]) => s === r.slot)?.[0] ?? null,
  }));
  const events: { t: number; text: string }[] = [];
  for (const e of log.events) {
    if (e.after) continue;
    const text = tickerLine(e, log, named);
    if (text) events.push({ t: round(e.t, 1), text });
  }
  return {
    courseName: courseName(log.course),
    course: log.course,
    laps: log.meta.laps ?? null,
    duration: round(duration(log), 1),
    field,
    events,
    avgLap: avgLap(log),
  };
}

function avgLap(log: RaceLog): number | null {
  const laps = log.standings.flatMap((s) => s.laps ?? []).sort((a, b) => a - b);
  return laps.length ? round(laps[Math.floor(laps.length / 2)], 1) : null;
}

/** One deterministic sentence, or null for events the ticker skips.
 *
 *  Position swaps are far too many to narrate; the ticker keeps hits, blue
 *  shells, lead changes, and the flag. */
function tickerLine(
  e: RaceEvent,
  log: RaceLog,
  named: Map<number, string>,
): string | null {
  const who = (s: number) => named.get(s) ?? log.field.name(s);
  if (e.type === "hit" && e.slot != null) {
    const victim = who(e.slot);
    const by = e.by ?? [];
    const tail = by.length ? ` (${by.map(who).join(", ")})` : "";
    if (e.object === BLUE_OBJECT) return `Blue shell: ${victim}${tail}`;
    if (e.caught) return `${victim} caught in the blast${tail}`;
    return `${victim} hit by ${causeOf(e)}${tail}`;
  }
  if (e.type === "pos" && e.to === 1 && e.slot != null)
    return `${who(e.slot)} takes the lead`;
  if (e.type === "finish" && e.slot != null) {
    if (e.position === 1) return `${who(e.slot)} takes the flag`;
    if (named.has(e.slot)) return `${who(e.slot)} finishes P${e.position ?? 0}`;
  }
  return null;
}

export function round(x: number, places: number): number {
  const f = 10 ** places;
  return Math.round(x * f) / f;
}
