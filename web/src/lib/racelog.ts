// A stored race, read back - the TypeScript half of mkw/racelog.py.
//
// The file format is the one that module writes: JSON Lines, one `race`
// header, the events in race order, an optional `progress` record, and a
// `standings` record last. Unknown record types and unknown fields are
// ignored on purpose, so the recorder can add an event without this needing
// to change.

import { CHARACTERS, JUMP, TRACK_HZ } from "../data/names";

export interface Racer {
  slot: number;
  character: number;
  vehicle: number;
  type: number;
  cpu: boolean;
  grid: number;
}

export interface RaceMeta {
  type: "race";
  version: number;
  recorded?: string;
  course: number | null;
  laps?: number | null;
  begins?: number;
  local_slot?: number;
  racers?: Racer[];
  source?: string;
  notes?: string;
}

export interface RaceEvent {
  t: number;
  type: string;
  slot?: number;
  item?: number;
  damage?: number;
  object?: number | null;
  by?: number[];
  for?: number;
  caught?: boolean;
  after?: boolean;
  guess?: boolean;
  from?: number;
  to?: number;
  lap?: number;
  position?: number;
  time?: number;
}

export interface Standing {
  slot: number;
  position: number | null;
  finished: boolean;
  time: number | null;
  lap_reached?: number;
  laps?: number[];
  leading?: number | null;
  raced?: number | null;
}

/** Display names for the twelve slots, built the way mkw/events.py builds
 *  them: the character name, numbered only if two racers share one. */
export class Field {
  private names = new Map<number, string>();

  constructor(racers: Racer[] | undefined) {
    if (!racers) return;
    const repeated = new Map<number, number>();
    for (const r of racers)
      repeated.set(r.character, (repeated.get(r.character) ?? 0) + 1);
    const used = new Map<number, number>();
    const top = Math.max(...Object.keys(CHARACTERS).map(Number));
    for (const r of racers) {
      const c = r.character;
      let name = CHARACTERS[c] ?? (c > top ? "Mii" : `?${c}`);
      if ((repeated.get(c) ?? 0) > 1) {
        const n = (used.get(c) ?? 0) + 1;
        used.set(c, n);
        name = `${name} #${n}`;
      }
      this.names.set(r.slot, name);
    }
  }

  name(slot: number): string {
    return this.names.get(slot) ?? `slot ${slot}`;
  }
}

export class RaceLog {
  file: string;
  meta: RaceMeta = { type: "race", version: 1, course: null };
  events: RaceEvent[] = [];
  standings: Standing[] = [];
  track = new Map<number, number[]>();
  trackHz = TRACK_HZ;
  trackT0 = 0;
  field: Field;

  constructor(file: string, text: string) {
    this.file = file;
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      const rec = JSON.parse(line);
      switch (rec.type) {
        case "race":
          this.meta = rec;
          break;
        case "standings":
          this.standings = rec.standings ?? [];
          break;
        case "progress":
          for (const [slot, row] of Object.entries(rec.completion ?? {}))
            this.track.set(Number(slot), row as number[]);
          this.trackHz = rec.hz ?? TRACK_HZ;
          this.trackT0 = rec.t0 ?? 0;
          break;
        default:
          this.events.push(rec);
      }
    }
    this.field = new Field(this.meta.racers);
  }

  get course() {
    return this.meta.course;
  }

  get racers(): Racer[] {
    return this.meta.racers ?? [];
  }

  ofType(...types: string[]): RaceEvent[] {
    return this.events.filter((e) => types.includes(e.type));
  }

  slots(): number[] {
    return this.racers.map((r) => r.slot).sort((a, b) => a - b);
  }

  racer(slot: number): Racer | undefined {
    return this.racers.find((r) => r.slot === slot);
  }

  trackTimes(): number[] {
    let n = 0;
    for (const row of this.track.values()) n = Math.max(n, row.length);
    return Array.from({ length: n }, (_, k) => this.trackT0 + k / this.trackHz);
  }

  /** {slot: lap + fraction of a lap} at any moment, between samples.
   *
   *  Crossing the line puts progress back to the start of the last lap, so a
   *  step bigger than JUMP is that, not motion, and the nearer reading is
   *  taken rather than a value a whole lap out. */
  progressAt(t: number): Map<number, number> {
    const out = new Map<number, number>();
    if (!this.track.size) return out;
    const x = (t - this.trackT0) * this.trackHz;
    const i = Math.floor(x);
    const frac = x - i;
    for (const [slot, row] of this.track) {
      if (!row.length) continue;
      const j = Math.min(Math.max(i, 0), row.length - 1);
      const k = Math.min(j + 1, row.length - 1);
      const f = j === i ? frac : 0;
      out.set(
        slot,
        Math.abs(row[k] - row[j]) > JUMP
          ? f < 0.5
            ? row[j]
            : row[k]
          : row[j] + (row[k] - row[j]) * f,
      );
    }
    return out;
  }

  /** The running order at any moment: slots, leader first. */
  orderAt(t: number): number[] {
    return [...this.progressAt(t)]
      .sort((a, b) => b[1] - a[1])
      .map(([slot]) => slot);
  }
}
