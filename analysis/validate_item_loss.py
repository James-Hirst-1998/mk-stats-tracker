#!/usr/bin/env python3
"""Offline: which hits knock the item out of your hands, on every recording.

An item leaving the held field means one of two things - the racer threw it, or
somebody took it off them - and the event log called both of them "used". A
Lightning therefore read as eleven racers all choosing to use what they were
holding, in the same frame.

The two fields here are read from different places: the held item from the
KartItem struct, the damage type from the sub-object the collision code writes.
This walks every moment a held item went empty and asks what, if anything, had
just hit that racer - which is the question `mkw.events` asks, in that
direction, so the counts here are the `lost` events it will emit.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_item_loss [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

import numpy as np

from mkw.names import DAMAGE_TYPES, ITEMS, DROPS_ITEM
from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import read, spans, N_PLAYERS
from analysis.cross_check_damage import read_held, uses

# The reader calls it lost if the damage field is reading a DROPS_ITEM type at
# the moment the item goes. This window is only for reporting the near misses:
# clearings with a hit close by that the rule does not act on, which is where a
# wrong rule would show up.
NEAR = 0.60


def main():
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]

    lost = Counter()          # damage type -> item clearings it took
    near = Counter()          # damage type -> clearings close to one, not in it
    items = Counter()
    gaps = []
    clean = 0                 # clearings with no hit anywhere near: plain throws
    for d in dirs:
        s = Session(d)
        t, dmg, _, _ = read(s)
        if np.all(np.isnan(t)):
            continue
        hits = []
        for k in range(N_PLAYERS):
            hits += [(st, dur, k, v) for st, dur, v in spans(t, dmg[:, k])]
        for when, k, item in uses(t, read_held(s)):
            # The rule: was this racer being flipped, flattened or shocked at
            # the moment the item went?
            during = [(st, v) for st, dur, who, v in hits
                      if who == k and st <= when <= st + dur
                      and v in DROPS_ITEM]
            if during:
                st, v = max(during)
                lost[v] += 1
                items[item] += 1
                gaps.append(round(when - st, 3))
                continue
            close = sorted((abs(st - when), v) for st, dur, who, v in hits
                           if who == k and abs(st - when) <= NEAR)
            if close:
                near[close[0][1]] += 1
            else:
                clean += 1
        print("read %s" % os.path.basename(d))

    print("\nevery time a held item went empty, and what was happening to that "
          "racer.\nlost = the damage field was reading a DROPS_ITEM type at "
          "that moment.\n")
    print("  %-4s %-30s %-6s %s" % ("type", "cause", "lost", "near, not lost"))
    for v in sorted(set(lost) | set(near)):
        print("  %-4d %-30s %-6d %-6d%s"
              % (v, DAMAGE_TYPES[v][1], lost[v], near[v],
                 "   <- in DROPS_ITEM" if v in DROPS_ITEM else ""))
    total = sum(lost.values()) + sum(near.values()) + clean
    print("\n  %d of %d clearings are throws with no hit within %.2fs at all"
          % (clean, total, NEAR))
    print("  %d are the racer being hit as the item went - reported as lost"
          % sum(lost.values()))
    print("  %d had a hit near but not on them, and stay uses"
          % sum(near.values()))
    print("\nitems taken: %s"
          % ", ".join("%dx %s" % (n, ITEMS.get(i, i))
                      for i, n in items.most_common()))
    if gaps:
        gaps.sort()
        print("gap from the hit to the item clearing: %.3f to %.3f, median "
              "%.3f (n=%d)" % (gaps[0], gaps[-1], gaps[len(gaps) // 2],
                               len(gaps)))


if __name__ == "__main__":
    main()
