#!/usr/bin/env python3
"""Offline: name the item behind each hit by matching it to a despawn.

The damage field says "knockback", which is a green shell, a red shell or a
fake item box. The item object that caused it is destroyed in the same game
frame the damage is written, so a despawn of the right kind at the right moment
names it - and the object carries `+0x6C`, the racer who fired it, which the
damage path never gets.

Which object types can produce which damage type is not guessed. Each type's
handler is `u32(0x808B5468 + type*0xC + 8)` and disassembling them gives:

    0, 1  -> `li r3,2`   green and red shells, knockback
    7     -> `li r31,2`  fake item box, knockback
    2     -> `neg r3,r0` banana, 0 or -1
    5, 9  -> `li r3,7` when the bomb/shell has gone off, else 0

Run (no sudo):
  mk/bin/python3 -m lab.items.match_hits [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

import numpy as np

from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import read as read_damage, spans, DAMAGE, N_PLAYERS
from lab.items.track_pools import track, transitions

# damage type -> object types whose handler can return it
CAN_CAUSE = {
    0: {2, 5, 9},
    2: {0, 1, 7},
    7: {5, 9},
}
OBJECTS = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 4: "Star",
           5: "Blue Shell", 7: "Fake Item Box", 9: "Bob-omb",
           12: "Golden Mushroom"}
# The object outlives the hit by a fixed 20 game frames (0.333s) while it
# breaks. Measured: 131 of 182 nearest despawns land in 0.25-0.40s, peaking at
# 0.30-0.35s, against a flat background elsewhere.
LAG_LO, LAG_HI = 0.20, 0.45


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    total = Counter()
    lags = []
    for d in dirs:
        s = Session(d)
        t, dmg, _, _ = read_damage(s)
        if np.all(np.isnan(t)):
            continue
        _, objs = track(s)
        spawns, despawns = transitions(t, objs)
        t0 = np.nanmin(t)

        named = ambiguous = unmatched = 0
        lines = []
        for k in range(N_PLAYERS):
            for st, dur, v in spans(t, dmg[:, k]):
                if v not in CAN_CAUSE:
                    continue
                want = CAN_CAUSE[v]
                near = [x for x in despawns
                        if x[2] in want and abs(x[0] - st) <= 4.0]
                if near:
                    lags.append((v, min(near, key=lambda x: abs(x[0] - st))[0] - st))
                else:
                    lags.append((v, None))
                cand = [x for x in despawns
                        if x[2] in want and LAG_LO <= x[0] - st <= LAG_HI]
                # your own shell does not hit you
                other = [x for x in cand if x[3] != k]
                pick = other or cand
                kinds = {x[2] for x in pick}
                if len(kinds) == 1:
                    named += 1
                    typ = pick[0][2]
                    owner = {x[3] for x in pick}
                    total[OBJECTS.get(typ, typ)] += 1
                    lines.append("  %6.1fs slot %-2d  %-13s -> %s%s"
                                 % (st - t0, k, DAMAGE[v][1],
                                    OBJECTS.get(typ, "type %d" % typ),
                                    " (slot %s)" % ", ".join(map(str, sorted(owner)))
                                    if owner else ""))
                elif kinds:
                    ambiguous += 1
                    lines.append("  %6.1fs slot %-2d  %-13s -> ambiguous %s"
                                 % (st - t0, k, DAMAGE[v][1],
                                    sorted(OBJECTS.get(x, x) for x in kinds)))
                else:
                    unmatched += 1
                    lines.append("  %6.1fs slot %-2d  %-13s -> no despawn"
                                 % (st - t0, k, DAMAGE[v][1]))
        n = named + ambiguous + unmatched
        print("=== %-44s %d/%d named, %d ambiguous, %d unmatched"
              % (os.path.basename(d)[:44], named, n, ambiguous, unmatched))
        for line in sorted(lines)[:14]:
            print(line)
        print()

    print("named hits by item: %s" % dict(total.most_common()))
    edges = [-4, -1, -0.4, -0.1, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 1, 2, 4]
    for v in sorted({x[0] for x in lags}):
        got = [x[1] for x in lags if x[0] == v]
        miss = sum(1 for g in got if g is None)
        a = np.array([g for g in got if g is not None])
        print("\ndamage %d (%s): %d hits, %d with no candidate despawn within 4s"
              % (v, DAMAGE[v][1], len(got), miss))
        for lo, hi in zip(edges, edges[1:]):
            n = int(((a >= lo) & (a < hi)).sum()) if len(a) else 0
            if n:
                print("   %+5.2f .. %+5.2f  %-4d %s" % (lo, hi, n, "#" * n))


if __name__ == "__main__":
    main()
