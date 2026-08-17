// Where a lap starts on a course, and which way round it goes.
//
// A layout drawing does not say either. The trace begins wherever the thinning
// happened to begin and runs whichever way the search happened to walk it, so
// two courses traced the same way can put the start line in opposite corners
// and run in opposite directions - which is what makes a replay look like the
// karts are wandering.
//
// Neither fact is in the drawing or in the logs, so both are set by hand once
// per course at #/tracks and kept in assets/tracks/starts.json. The start is
// stored as a point on the drawing rather than as a distance along the path,
// so re-tracing a course does not move it. A course file (`source: "course"`)
// already knows both and is left alone.

import { useEffect, useState } from "react";
import type { Track } from "../data/tracks";

export interface Start {
  /** The start line, in the drawing's own coordinates. */
  x: number;
  y: number;
  /** True if the traced path runs against the racing direction. */
  reverse: boolean;
}

export type Starts = Record<number, Start>;

export const STARTS_URL = "/assets/tracks/starts.json";

/** The points of a path built by tools/build_tracks.py: all M and L, evenly
 *  spaced, so an index into them is a fraction of a lap. */
export function pointsOf(d: string): [number, number][] {
  const out: [number, number][] = [];
  for (const m of d.matchAll(/([-\d.]+)\s+([-\d.]+)/g))
    out.push([Number(m[1]), Number(m[2])]);
  return out;
}

function pathOf(points: [number, number][], closed: boolean): string {
  const d = points.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ");
  return closed ? `${d} Z` : d;
}

export function nearestIndex(points: [number, number][], x: number, y: number) {
  let best = 0;
  let far = Infinity;
  points.forEach((p, i) => {
    const d = (p[0] - x) ** 2 + (p[1] - y) ** 2;
    if (d < far) {
      far = d;
      best = i;
    }
  });
  return best;
}

/** The same course with its lap starting where it really starts and running
 *  the way it is really driven.
 *
 *  The path is turned end for end first and rotated second, because a replay
 *  reads it as a loop either way - even the courses whose drawing has gaps in
 *  it, where the trace could not close. */
export function oriented(track: Track, start: Start | undefined): Track {
  if (!start || track.source === "course") return track;
  const pts = pointsOf(track.d);
  if (pts.length < 3) return track;

  const turned = start.reverse ? [...pts].reverse() : pts;
  const cut = nearestIndex(turned, start.x, start.y);
  return {
    ...track,
    d: pathOf([...turned.slice(cut), ...turned.slice(0, cut)], track.closed),
  };
}

/** The file, kept in step with what the tracks screen saves. */
export function useStarts(): [Starts, (next: Starts) => Promise<void>] {
  const [starts, setStarts] = useState<Starts>({});

  useEffect(() => {
    let alive = true;
    fetch(STARTS_URL, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .then((got) => alive && setStarts(got ?? {}))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const save = async (next: Starts) => {
    setStarts(next);
    await fetch("/api/starts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
  };

  return [starts, save];
}
