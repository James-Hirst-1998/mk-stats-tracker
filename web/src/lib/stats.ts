// Everything the dashboard shows, computed from stored race logs.
//
// Same files in, same numbers out: no randomness, no clock, no model. A number
// on screen that cannot be derived here cannot be shown, which keeps one
// source for every figure and keeps the components to rendering.
//
// The unit of identity is the *player*: a person who keeps the same character
// for a session. `players.json` in a session directory says who is tracked:
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

/** The order items are shown in, front of the field to back: what lands in
 *  your hands while you are winning first, what lands in them while you are
 *  losing last. James gave the sequence; the ones he did not name sit with
 *  their neighbours. Names rather than ids, so a corrected id in mkw/names.py
 *  moves with it - the same reason BOOST_ITEMS is built this way. */
export const ITEM_ORDER = [
  "Banana",
  "Triple Bananas",
  "Fake Item Box",
  "Green Shell",
  "Triple Green Shells",
  "Red Shell",
  "Triple Red Shells",
  "Bob-omb",
  "Mushroom",
  "Triple Mushrooms",
  "Blooper",
  "POW Block",
  "Thunder Cloud",
  "Mega Mushroom",
  "Star",
  "Golden Mushroom",
  "Bullet Bill",
  "Blue Shell",
  "Lightning",
];

/** Where an item sorts. Anything unlisted goes after the lot, in id order, so
 *  an item added to the table without being added here still has one place. */
export function itemRank(id: number): number {
  const i = ITEM_ORDER.indexOf(ITEMS[id] ?? "");
  return i < 0 ? ITEM_ORDER.length + id : i;
}

/** Hits where the object was not read, so the name covers two items
 *  (DAMAGE_TYPES in mkw/names.py). They sort after the items they might be. */
const UNCERTAIN_CAUSES = ["Shell or Fake Item Box", "Bob-omb or Blue Shell"];

/** Everything that hits you that nobody threw. Last, because a Chain Chomp is
 *  not somebody's doing and does not belong among the items. */
const HAZARD_CAUSES = [
  "an enemy",
  "Chain Chomp",
  "a boosted kart, cow or car",
  "a Moonview car",
  "a Moonview truck",
  "a Cataquack",
  "a Thwomp",
  "a Thwomp, then respawned",
  "a Zapper",
  "fire",
  "something",
];

/** Where a cause sorts: the items in ITEM_ORDER, then the two-item names,
 *  then the hazards. `causeOf` gives these names. */
export function causeRank(cause: string): number {
  const item = ITEM_ORDER.indexOf(cause);
  if (item >= 0) return item;
  const uncertain = UNCERTAIN_CAUSES.indexOf(cause);
  if (uncertain >= 0) return ITEM_ORDER.length + uncertain;
  const hazard = HAZARD_CAUSES.indexOf(cause);
  const tail = ITEM_ORDER.length + UNCERTAIN_CAUSES.length;
  return hazard >= 0 ? tail + hazard : tail + HAZARD_CAUSES.length;
}

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
  /** Blue shells thrown at them while leading that never landed. */
  bluesDodged: number;
  boosts: number;
  out: number;
  /** Items that landed in their hands (`hold` events). */
  got: number;
  /** Items knocked out of their hands before they could use them. */
  lost: number;
  /** {position: seconds spent there}, from the position events. */
  positionTime: Map<number, number>;
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
  /** Every blue shell thrown, who it was aimed at, and whether it landed. */
  blueShells: BlueShell[];
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
  const race = raceRows(log);
  const rows = new Map<number, Row>();
  for (const [i, slot] of slotsOf(players, log)) {
    const row = race.get(slot);
    if (row) rows.set(i, row);
  }
  return rows;
}

/** The same row for every racer in the field, keyed by slot. Tracked players
 *  and CPUs are measured by one function so a CPU's line on the leaderboard
 *  cannot mean something different from a player's. */
export function raceRows(log: RaceLog): Map<number, Row> {
  const stats = summary(log);
  const rows = new Map<number, Row>();
  const landedHits = hits(log);
  const blues = blueShells(log);
  for (const [slot, r] of stats) {
    const mine = log.events.filter((e) => !e.after && e.slot === slot);
    const uses = mine.filter((e) => e.type === "use");
    rows.set(slot, {
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
      bluesDodged: blues.filter((b) => b.target === slot && !b.landed).length,
      boosts: uses.filter((e) => BOOST_ITEMS.has(e.item as number)).length,
      out: round(r.out, 1),
      got: mine.filter((e) => e.type === "hold").length,
      lost: mine.filter((e) => e.type === "lost").length,
      positionTime: r.positionTime,
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
 *  ("c17") where not, so a CPU nemesis keeps one identity across a session. */
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

/** Whole-session awards. Fixed rules, so the same races give the same winners;
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
      blueShells: blueShells(log),
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
  bluesDodged: number;
  boosts: number;
  out: number;
  got: number;
  lost: number;
}

/** One player's session so far. The slider on the dashboard is just a shorter
 *  list of races going into this. */
export function totalsFor(races: RaceStats[], player: number): Totals {
  return totalsOf(races.map((r) => r.rows.get(player)).filter((r) => r != null));
}

/** Add up whatever rows are handed over. Players and CPUs both come through
 *  here, so a CPU's column means exactly what a player's column means. */
export function totalsOf(rows: Row[]): Totals {
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
    bluesDodged: sum((r) => r.bluesDodged),
    boosts: sum((r) => r.boosts),
    out: round(sum((r) => r.out), 1),
    got: sum((r) => r.got),
    lost: sum((r) => r.lost),
  };
}

/** A CPU on the leaderboard: the character, and the same totals a player
 *  gets. */
export interface CpuStanding {
  key: string;
  character: number;
  name: string;
  totals: Totals;
}

/** Every CPU in these races, added up the same way the players are.
 *
 *  Identity is the character, the key `duelTotals` and `hitMatrix` already
 *  use, so the Waluigi on the leaderboard is the Waluigi in the hit matrix.
 *  Two CPUs on one character would therefore be one row; no stored race has
 *  a repeated character. */
export function cpuTotals(races: RaceStats[], players: Player[]): CpuStanding[] {
  const rows = new Map<number, Row[]>();
  for (const race of races) {
    const tracked = new Set(slotsOf(players, race.log).values());
    for (const [slot, row] of raceRows(race.log)) {
      if (tracked.has(slot)) continue;
      const c = race.log.racer(slot)?.character;
      if (c == null) continue;
      rows.set(c, [...(rows.get(c) ?? []), row]);
    }
  }
  return [...rows]
    .map(([character, list]) => ({
      key: `c${character}`,
      character,
      name: CHARACTERS[character] ?? `character ${character}`,
      totals: totalsOf(list),
    }))
    .sort((a, b) => b.totals.points - a.totals.points || a.name.localeCompare(b.name));
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

/** `nameFor` decides what a tracked player is called, so the ticker and the
 *  running order say the same thing under the Characters/Names toggle. Left
 *  out, everybody is their own name. */
export function replayData(
  log: RaceLog,
  players: Player[],
  nameFor?: (player: Player, character: string) => string,
): ReplayData {
  const slots = slotsOf(players, log);
  const named = new Map(
    [...slots].map(([i, s]) => [
      s,
      nameFor ? nameFor(players[i], log.field.name(s)) : players[i].name,
    ]),
  );
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


// --- drilling down: items, hits, who hit whom ------------------------------

/** How many of each item a player picked up, threw, and had knocked out of
 *  their hands, keyed by item id. A triple is one pickup and one throw: the
 *  log records the deploy, not the three shots (docs/RACE_LOG.md). */
export interface ItemTally {
  got: Map<number, number>;
  used: Map<number, number>;
  lost: Map<number, number>;
}

export function itemTally(races: RaceStats[], player: number): ItemTally {
  const out: ItemTally = { got: new Map(), used: new Map(), lost: new Map() };
  const bump = (m: Map<number, number>, k: number) => m.set(k, (m.get(k) ?? 0) + 1);
  for (const race of races) {
    const slot = race.rows.get(player)?.slot;
    if (slot == null) continue;
    for (const e of race.log.events) {
      if (e.after || e.slot !== slot || e.item == null) continue;
      if (e.type === "hold") bump(out.got, e.item);
      else if (e.type === "use") bump(out.used, e.item);
      else if (e.type === "lost") bump(out.lost, e.item);
    }
  }
  return out;
}

/** Every item anybody in these races picked up, in ITEM_ORDER, so a table has
 *  the same columns for every player and they read in one sequence rather
 *  than in whatever order the races happened to hand them out. */
export function itemsSeen(races: RaceStats[], players: Player[]): number[] {
  const seen = new Set<number>();
  players.forEach((_, i) => {
    for (const item of itemTally(races, i).got.keys()) seen.add(item);
  });
  return [...seen].sort((a, b) => itemRank(a) - itemRank(b));
}

/** How long after an item box the item lands in your hands. Measured over the
 *  715 holds in the stored races: 0.98-3.80s, 1.15 median (CPUs are quick,
 *  a human waits out the roulette). 6s is well clear of the longest. */
export const BOX_TO_HOLD = 6;

/** Items picked up off the road rather than out of a box, by item id.
 *
 *  The rule: a `hold` with no `box` for that racer in the BOX_TO_HOLD seconds
 *  before it, each box counting for one hold. Nothing else in the log
 *  distinguishes the two.
 *
 *  This is 0 in every stored race - all 715 holds follow a box - and James
 *  drove over a Star on Mario Circuit that the log has nothing for at all, so
 *  a count of zero here means "the recorder saw none", not "there were none".
 *  docs/EXPERIMENTS.md, 2026-09-03. */
export function scavenged(races: RaceStats[], player: number): Map<number, number> {
  const out = new Map<number, number>();
  for (const race of races) {
    const slot = race.rows.get(player)?.slot;
    if (slot == null) continue;
    let box: RaceEvent | null = null;
    for (const e of race.log.events) {
      if (e.after || e.slot !== slot) continue;
      if (e.type === "box") box = e;
      else if (e.type === "hold" && e.item != null) {
        if (box && e.t - box.t <= BOX_TO_HOLD) box = null;
        else out.set(e.item, (out.get(e.item) ?? 0) + 1);
      }
    }
  }
  return out;
}

export interface HitCause {
  /** What hit them: the object's name where one was read, else the damage
   *  type's description. The same names `causeOf` gives a marker. */
  cause: string;
  count: number;
  /** How many of those were standing in somebody else's blast. */
  caught: number;
  /** How many carry `guess: true` on the attribution. */
  guessed: number;
  /** Seconds it cost, over the hits whose end was seen. */
  out: number;
}

/** What a player was hit by, most often first. */
export function hitsTakenBy(races: RaceStats[], player: number): HitCause[] {
  const out = new Map<string, HitCause>();
  for (const race of races) {
    const slot = race.rows.get(player)?.slot;
    if (slot == null) continue;
    for (const e of hits(race.log)) {
      if (e.slot !== slot) continue;
      const cause = causeOf(e);
      const row = out.get(cause) ?? { cause, count: 0, caught: 0, guessed: 0, out: 0 };
      row.count += 1;
      if (e.caught) row.caught += 1;
      if (e.guess) row.guessed += 1;
      if (e.for != null) row.out += e.for;
      out.set(cause, row);
    }
  }
  // Rounded once, at the end, so a table's total is the sum of its rows.
  return [...out.values()]
    .map((r) => ({ ...r, out: round(r.out, 1) }))
    .sort((a, b) => b.count - a.count);
}

/** Somebody who can hit or be hit: a tracked player, or a CPU character. The
 *  key is the one `duelTotals` uses, so the two agree about who is who. */
export interface Identity {
  key: string;
  name: string;
  character: number | null;
  player: number | null;
  cpu: boolean;
}

export interface HitMatrix {
  /** Players first, in index order, then every CPU character seen. */
  identities: Identity[];
  /** "from>to" -> hits. Self-hits (driving into your own banana) sit on the
   *  diagonal and are counted. */
  counts: Map<string, number>;
  dealt: (key: string) => number;
  taken: (key: string) => number;
}

export function hitMatrix(races: RaceStats[], players: Player[]): HitMatrix {
  const identities: Identity[] = players.map((p, i) => ({
    key: String(i),
    name: p.name,
    character: p.character ?? null,
    player: i,
    cpu: false,
  }));
  const cpus = new Map<number, Identity>();
  for (const race of races) {
    const tracked = new Set(slotsOf(players, race.log).values());
    for (const r of race.log.racers) {
      if (tracked.has(r.slot) || cpus.has(r.character)) continue;
      cpus.set(r.character, {
        key: `c${r.character}`,
        name: CHARACTERS[r.character] ?? `character ${r.character}`,
        character: r.character,
        player: null,
        cpu: true,
      });
    }
  }
  identities.push(...[...cpus.values()].sort((a, b) => a.name.localeCompare(b.name)));

  const counts = new Map<string, number>();
  for (const d of duelTotals(races, players)) counts.set(`${d.from}>${d.to}`, d.count);
  const sumWhere = (pick: (from: string, to: string) => boolean) => {
    let n = 0;
    for (const [k, v] of counts) {
      const [from, to] = k.split(">");
      if (pick(from, to)) n += v;
    }
    return n;
  };
  return {
    identities,
    counts,
    dealt: (key) => sumWhere((from, to) => from === key && to !== key),
    taken: (key) => sumWhere((_, to) => to === key),
  };
}

// --- blue shells: thrown, landed, dodged -----------------------------------

export interface BlueShell {
  t: number;
  /** Who threw it. */
  thrower: number;
  /** Who was leading when it was thrown - the racer it went for - or null if
   *  nobody was still racing. */
  target: number | null;
  landed: boolean;
  /** Who it landed on, if it did. Normally the target; at the end of a race
   *  a shell can land on somebody who had just crossed the line. */
  victim: number | null;
  /** When it landed, if it did. */
  hitT: number | null;
}

/** How long a Blue Shell is given to arrive. Over the 13 stored races the
 *  use-to-hit gap is 3.2-9.6s (median 5.2); 15s leaves room for a long
 *  course without pairing a shell with the one thrown after it. */
export const BLUE_FLIGHT = 15;

/** Every Blue Shell thrown, paired with the launched hit it produced. A shell
 *  with no such hit within BLUE_FLIGHT was dodged, by whoever was leading when
 *  it was thrown: a cannon, a Mushroom timed right, a Star, or a Bill.
 *
 *  The hit is looked for on the leader at the throw first, and failing that
 *  on anybody - one of the 30 shells in the stored races landed on a racer
 *  who had passed the leader and crossed the line while it was in the air.
 *  A Bob-omb is the other thing that launches you, and is told apart by its
 *  object type; a launched hit with no object read is accepted only when the
 *  log marked it as a guess against a Blue Shell or Bob-omb use. Anybody
 *  else in the crater is `caught` and is not the hit. */
export function blueShells(log: RaceLog): BlueShell[] {
  const leader = leaderAt(log);
  const uses = log.events
    .filter((e) => e.type === "use" && e.item === 7 && e.slot != null)
    .sort((a, b) => a.t - b.t);
  const launched = log.events.filter(
    (e) =>
      e.type === "hit" &&
      e.damage === 7 &&
      !e.caught &&
      e.slot != null &&
      (e.object === BLUE_OBJECT || (e.object == null && e.guess)),
  );
  const used = new Set<RaceEvent>();
  return uses.map((u) => {
    const target = leader(u.t);
    const inFlight = (h: RaceEvent) =>
      !used.has(h) && h.t >= u.t && h.t <= u.t + BLUE_FLIGHT;
    const hit =
      launched.find((h) => inFlight(h) && h.slot === target) ??
      launched.find(inFlight);
    if (hit) used.add(hit);
    return {
      t: round(u.t, 1),
      thrower: u.slot!,
      target,
      landed: Boolean(hit),
      victim: hit?.slot ?? null,
      hitT: hit ? round(hit.t, 1) : null,
    };
  });
}

/** Who was in first among the racers still racing at `t`, from the position
 *  events. A Blue Shell goes for the leader, and once the leader has crossed
 *  the line that is the leader of whoever is left. */
function leaderAt(log: RaceLog): (t: number) => number | null {
  const swaps = log.ofType("pos").sort((a, b) => a.t - b.t);
  const finishes = log.ofType("finish");
  const start = new Map<number, number>();
  for (const e of swaps) if (!start.has(e.slot!)) start.set(e.slot!, e.from as number);
  for (const r of log.racers) if (!start.has(r.slot)) start.set(r.slot, r.grid);
  return (t) => {
    const at = new Map(start);
    for (const e of swaps) {
      if (e.t > t) break;
      at.set(e.slot!, e.to as number);
    }
    const done = new Set(finishes.filter((f) => f.t <= t).map((f) => f.slot!));
    let best: number | null = null;
    for (const [slot, pos] of at)
      if (!done.has(slot) && (best == null || pos < at.get(best)!)) best = slot;
    return best;
  };
}

/** The tracked player a slot belongs to in one race, or null for a CPU. */
export function playerOfSlot(slot: number, log: RaceLog, players: Player[]): number | null {
  return [...slotsOf(players, log)].find(([, s]) => s === slot)?.[0] ?? null;
}

export function round(x: number, places: number): number {
  const f = 10 ** places;
  return Math.round(x * f) / f;
}
