// One row per racer, rebuilt from the events - the TypeScript half of
// mkw/report.py.
//
// Nothing here is read from the game. If a number cannot be derived from the
// stored events, the events are missing something, and the fix is in the
// recorder rather than here.

import {
  BY_ITEM,
  COUNTDOWN_FRAMES,
  DAMAGE_TYPES,
  OBJECT_TYPES,
} from "../data/names";
import type { RaceEvent, RaceLog } from "./racelog";

export interface RacerSummary {
  slot: number;
  name: string;
  character: number | null;
  cpu: boolean;
  grid: number | null;
  position: number | null;
  finished: boolean;
  time: number | null;
  laps: number[];
  bestLap: number | null;
  /** Seconds in first, the game's own count, less the countdown for pole. */
  leading: number;
  /** The same thing counted a second way, by replaying the position events. */
  leadingFromEvents: number;
  positionTime: Map<number, number>;
  boxes: number;
  used: number;
  hitsTaken: number;
  hitsDealt: Map<string, number>;
  hitBy: Map<number, number>;
  hazards: number;
  caught: number;
  /** Seconds spun out, flipped or flattened. Only hits whose end was seen. */
  out: number;
}

/** How long the race ran, on the race clock. */
export function duration(log: RaceLog): number {
  const ends: number[] = [];
  for (const s of log.standings) {
    if (s.raced) ends.push(s.raced);
    if (s.time) ends.push(s.time);
  }
  if (ends.length) return Math.max(...ends);
  return log.events.reduce((m, e) => Math.max(m, e.t), 0);
}

/** {slot: when that racer's race ended}. Their finish, or where they got to.
 *
 *  `raced` stops when the race ends for that racer whether or not they
 *  crossed the line, so somebody still on track when the last CPU finishes is
 *  not credited with the position they were parked in afterwards. */
export function endsAt(log: RaceLog): Map<number, number> {
  const end = duration(log);
  return new Map(log.standings.map((s) => [s.slot, s.raced ?? s.time ?? end]));
}

/** A short name for whatever caused a hit. */
export function hitBy(e: RaceEvent): string {
  if (e.object != null) return OBJECT_TYPES[e.object] ?? `item ${e.object}`;
  return DAMAGE_TYPES[e.damage as number]?.[1] ?? "something";
}

/** {slot: {position: seconds spent there}}, rebuilt from the `pos` events.
 *
 *  Seeded from each racer's first swap - its `from` is the position they held
 *  for the whole of the log before it - rather than from the grid, which is
 *  only the same thing when the log starts at GO. */
export function positions(log: RaceLog): Map<number, Map<number, number>> {
  const start = log.meta.begins ?? 0;
  const stop = endsAt(log);
  const end = duration(log);
  const swaps = log.ofType("pos").sort((a, b) => a.t - b.t);
  const at = new Map<number, number>();
  for (const e of swaps)
    if (!at.has(e.slot!)) at.set(e.slot!, e.from as number);
  for (const r of log.racers) if (!at.has(r.slot)) at.set(r.slot, r.grid);

  const out = new Map<number, Map<number, number>>();
  const since = new Map<number, number>();
  for (const s of at.keys()) {
    out.set(s, new Map());
    since.set(s, start);
  }
  const add = (slot: number, pos: number, secs: number) => {
    const row = out.get(slot)!;
    row.set(pos, (row.get(pos) ?? 0) + Math.max(0, secs));
  };
  for (const e of swaps) {
    const s = e.slot!;
    const limit = Math.min(e.t, stop.get(s) ?? end);
    add(s, at.get(s)!, limit - since.get(s)!);
    at.set(s, e.to as number);
    since.set(s, Math.max(since.get(s)!, limit));
  }
  for (const s of at.keys()) add(s, at.get(s)!, (stop.get(s) ?? end) - since.get(s)!);
  return out;
}

/** One row per racer, keyed by slot. */
export function summary(log: RaceLog): Map<number, RacerSummary> {
  const final = new Map(log.standings.map((s) => [s.slot, s]));
  const posTime = positions(log);
  const out = new Map<number, RacerSummary>();

  for (const slot of log.slots()) {
    const f = final.get(slot);
    const r = log.racer(slot);
    const laps = f?.laps ?? [];
    // +0x30 starts at the intro, so whoever is on pole is credited the
    // countdown as time in first. Taken off here rather than in the reader,
    // which stays a plain read.
    let lead = f?.leading ?? 0;
    if (f?.leading != null && r?.grid === 1)
      lead = Math.max(0, lead - COUNTDOWN_FRAMES / 60);
    out.set(slot, {
      slot,
      name: log.field.name(slot),
      character: r?.character ?? null,
      cpu: Boolean(r?.cpu),
      grid: r?.grid ?? null,
      position: f?.position ?? null,
      finished: Boolean(f?.finished),
      time: f?.time ?? null,
      laps,
      bestLap: laps.length ? Math.min(...laps) : null,
      leading: lead,
      leadingFromEvents: posTime.get(slot)?.get(1) ?? 0,
      positionTime: posTime.get(slot) ?? new Map(),
      boxes: 0,
      used: 0,
      hitsTaken: 0,
      hitsDealt: new Map(),
      hitBy: new Map(),
      hazards: 0,
      caught: 0,
      out: 0,
    });
  }

  // Everything that happened while the racer it happened to was still racing.
  // A shell that catches somebody parked past the line is in the log, and is
  // not a statistic.
  for (const e of log.events) {
    if (e.after) continue;
    const row = e.slot == null ? undefined : out.get(e.slot);
    if (row) {
      if (e.type === "box") row.boxes += 1;
      else if (e.type === "use") row.used += 1;
      else if (e.type === "hit") {
        row.hitsTaken += 1;
        if (e.for != null) row.out += e.for;
        if (e.caught) row.caught += 1;
        if (!isByItem(e.damage)) row.hazards += 1;
      }
    }
    // Who threw it is only credited when the despawn window named exactly one
    // owner. Two candidate owners is not evidence about either.
    if (e.type === "hit" && (e.by ?? []).length === 1) {
      const by = e.by![0];
      const attacker = out.get(by);
      if (attacker && by !== e.slot) {
        const what = hitBy(e);
        attacker.hitsDealt.set(what, (attacker.hitsDealt.get(what) ?? 0) + 1);
        if (row) row.hitBy.set(by, (row.hitBy.get(by) ?? 0) + 1);
      }
    }
  }
  return out;
}

function isByItem(damage: number | undefined): boolean {
  return damage != null && BY_ITEM.has(damage);
}

export function landed(r: RacerSummary): number {
  let n = 0;
  for (const v of r.hitsDealt.values()) n += v;
  return n;
}
