#!/usr/bin/env python3
"""Measure the things the next batch of events needs, before writing any.

  1. blast    - when one explosion catches several racers, was the first one
                hit the one in front? That is what separates a direct hit from
                being caught in it.
  2. cloud    - the held field never carries a Thunder Cloud, so who is holding
                one has to come from somewhere else. Which item pools are live
                while a cloud is in play?
  3. rammed   - a Star, Mega or Bullet leaves no object behind, so the only
                candidates are racers who used one recently AND are right next
                to the victim. How close, and how long after?
  4. bullet   - what a Bullet Bill ride looks like in progress per second, and
                whether its end is visible without a new field.
  5. pause    - the race clock repeats across snapshots far too often to mean a
                pause on its own. How long do the runs of repeats get?

Run (no sudo):
  mk/bin/python3 -m lab.events.measure [recording-substring]
"""

import sys
from collections import Counter, defaultdict

from lab.events.snapshots import recordings, racing

STAR, MEGA, BULLET, CLOUD = 9, 11, 15, 14
EMPTY = 20
RAM = {3: STAR, 6: BULLET, 13: MEGA}
NEAR = 0.004               # laps: how close counts as "right next to"
BOOST = 20.0               # how far back to look for the boost item's use


def transitions(frames, key):
    out, prev = [], {}
    for t, r in frames:
        for p in r["players"]:
            s, v = p["slot"], p.get(key)
            if v is None:
                continue
            if s in prev and prev[s] != v:
                out.append((t, s, prev[s], v))
            prev[s] = v
    return out


def at(frames, t, key):
    best = min(frames, key=lambda x: abs(x[0] - t))
    return {p["slot"]: p[key] for p in best[1]["players"]}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    blast = Counter()
    pools = Counter()
    found = defaultdict(Counter)
    lag = defaultdict(list)
    gap = defaultdict(list)
    rides = []
    runs = Counter()
    clouds = []

    for d in recordings(which):
        name, frames = racing(d)
        if not frames:
            continue
        hits = [(t, s, b) for t, s, a, b in transitions(frames, "damage")
                if b >= 0]
        uses = [(t, s, a) for t, s, a, b in transitions(frames, "item")
                if b == EMPTY and a != EMPTY]
        boxes = [(t, s, b) for t, s, a, b in transitions(frames, "roulette")
                 if a == EMPTY and b != EMPTY]
        print("=== %s   %d frames, %d hits, %d uses"
              % (name, len(frames), len(hits), len(uses)))

        # 1. explosions that caught more than one racer
        groups = []
        for t, s, v in sorted(hits):
            if v != 7:
                continue
            if groups and t - groups[-1][0][0] <= 1.0:
                groups[-1].append((t, s, v))
            else:
                groups.append([(t, s, v)])
        for g in groups:
            blast["%d victim(s)" % len(g)] += 1
            if len(g) < 2:
                continue
            pos = at(frames, g[0][0], "position")
            first = min(t for t, _, _ in g)
            hit_first = [s for t, s, _ in g if t == first]
            blast["first hit was P1" if 1 in [pos.get(s) for s in hit_first]
                  else "first hit was not P1"] += 1
            blast["someone in the group was P1"
                  if 1 in [pos.get(s) for _, s, _ in g]
                  else "nobody in the group was P1"] += 1

        # 2. a Thunder Cloud: who got one, who it struck, what pools were live
        got = [(t, s) for t, s, i in boxes if i == CLOUD]
        struck = [(t, s) for t, s, v in hits if v == 17]
        for t, s in got:
            end = min([x for x, _ in struck if x > t], default=None)
            clouds.append((name[9:22], round(t, 1), s,
                           None if end is None else
                           [w for x, w in struck if x == end][0],
                           None if end is None else round(end - t, 1)))
            for ft, r in frames:
                if t <= ft <= (end or t + 12):
                    for _, (kind, _owner) in (r.get("world_items") or {}).items():
                        pools[kind] += 1

        # 3. ram hits: proximity first, then who had used the boost
        for t, victim, v in hits:
            if v not in RAM:
                continue
            prog = at(frames, t, "completion")
            close = {s for s, x in prog.items()
                     if s != victim and victim in prog
                     and abs(x - prog[victim]) <= NEAR}
            cand = [(t - ut, us) for ut, us, ui in uses
                    if ui == RAM[v] and 0 <= t - ut <= BOOST and us in close]
            found[v][len(cand)] += 1
            if len(cand) == 1:
                dt, who = cand[0]
                lag[v].append(round(dt, 2))
                gap[v].append(round(abs(prog[who] - prog[victim]), 4))

        # 4. what a Bullet Bill ride looks like
        for ut, us, ui in uses:
            if ui != BULLET:
                continue
            row = []
            for k in range(14):
                a = at(frames, ut + k, "completion").get(us)
                b = at(frames, ut + k + 1, "completion").get(us)
                row.append(round((b - a) * 100, 2) if a and b else None)
            rides.append((name[9:22], us, row))

        # 5. how long the race clock stands still when nobody paused
        seen = None
        run = 0
        for t, r in frames:
            if t == seen:
                run += 1
            else:
                if run:
                    runs[run] += 1
                run = 0
            seen = t
        if run:
            runs[run] += 1
        print()

    print("1. explosions: %s" % dict(blast))
    print("2. thunder clouds (recording, picked up, by, struck, after):")
    for c in clouds:
        print("     %s" % (c,))
    print("   pools live while a cloud was in play: %s" % dict(pools))
    print("3. ram hits, candidates within %.3f laps who had used the item:"
          % NEAR)
    for v in sorted(found):
        print("   damage %-3d %s" % (v, dict(found[v])))
        if lag[v]:
            x, g = sorted(lag[v]), sorted(gap[v])
            print("       lag %.1f-%.1fs median %.1f, gap %.4f-%.4f median "
                  "%.4f (n=%d)" % (x[0], x[-1], x[len(x) // 2],
                                   g[0], g[-1], g[len(g) // 2], len(x)))
    print("4. bullet rides, progress gained per second x100:")
    for rec, who, row in rides:
        print("   %s slot %-2d %s" % (rec, who, " ".join(
            "-" if v is None else "%5.1f" % v for v in row)))
    print("5. runs of a standing-still race clock, nobody paused: %s"
          % dict(sorted(runs.items())))


if __name__ == "__main__":
    main()
