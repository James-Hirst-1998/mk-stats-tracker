#!/usr/bin/env python3
"""Offline: check the damage field against the item field, with no video.

These two are read from completely different places - the held item comes from
the KartItem struct, the damage type from the sub-object the collision code
writes. If the damage reads are real, then every hit of a given type should be
preceded by somebody using an item that produces that type, and the two
field-wide items should be exact:

  Lightning must strike every racer in the same frame as somebody uses item 8
  POW Block must strike a group in the same frame as somebody uses item 13

Anything left over is a track hazard, a dropped banana from earlier, or a hit
by a player whose item use was not caught.

Run (no sudo):
  mk/bin/python3 -m analysis.cross_check_damage [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import (read, spans, DAMAGE, BY_ITEM, N_PLAYERS,
                             ITEM_DIRECTOR, OFF_ITEM_ARRAY, ITEM_STRIDE,
                             be_u32)

OFF_HELD = 0x8F            # same byte as read_race's base + 0x1c
EMPTY = 20
ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
    4: "Mushroom", 5: "Triple Mushrooms", 6: "Bob-omb", 7: "Blue Shell",
    8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
    12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
    16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "-",
}

# damage type -> the item ids that can produce it
CAUSES = {
    0:  {2, 18, 3},
    2:  {0, 1, 16, 17, 3},
    3:  {9},
    6:  {15},
    7:  {6, 7},
    10: {8},
    11: {13},
    13: {11},
    17: {14},
}
# the two that hit the whole field at once
FIELD_WIDE = {10: 8, 11: 13}
WINDOW = 12.0              # seconds a shell or banana may be in flight or lying


def read_held(s):
    n = len(s)
    held = np.full((n, N_PLAYERS), -1, dtype=np.int16)
    di = capfmt.addr_to_index(ITEM_DIRECTOR, s.regions)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        j = capfmt.addr_to_index(be_u32(img, di) + OFF_ITEM_ARRAY, s.regions)
        if j is None:
            continue
        items = be_u32(img, j)
        row = []
        for k in range(N_PLAYERS):
            ki = capfmt.addr_to_index(items + k * ITEM_STRIDE + OFF_HELD,
                                      s.regions)
            if ki is None:
                row = None
                break
            row.append(int(img[ki]))
        if row and max(row) <= EMPTY:
            held[i] = row
    return held


def uses(t, held):
    """(time, racer, item) each time a held item goes to empty."""
    out = []
    for k in range(N_PLAYERS):
        prev = None
        for i in range(len(t)):
            v = int(held[i, k])
            if v < 0 or np.isnan(t[i]):
                continue
            if prev is not None and prev != EMPTY and v == EMPTY:
                out.append((float(t[i]), k, int(prev)))
            prev = v
    out.sort()
    return out


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]

    grand_ok = grand_tot = 0
    for d in dirs:
        s = Session(d)
        t, dmg, last, prio = read(s)
        if np.all(np.isnan(t)):
            continue
        held = read_held(s)
        used = uses(t, held)
        t0 = np.nanmin(t)
        print("=== %s  (%d item uses)" % (os.path.basename(d), len(used)))

        # 1. field-wide items must land on everyone at once
        for dtype, item in FIELD_WIDE.items():
            fired = [u for u in used if u[2] == item]
            for when, who, _ in fired:
                victims = []
                for k in range(N_PLAYERS):
                    for st, dur, v in spans(t, dmg[:, k]):
                        if v == dtype and when - 1.0 <= st <= when + 4.0:
                            victims.append(k)
                            break
                print("   %6.1fs  slot %-2d used %-11s -> %2d racers took "
                      "damage type %d" % (when - t0, who, ITEM_NAMES[item],
                                          len(victims), dtype))

        # 2. every hit by an item type should have a plausible cause
        ok = tot = 0
        unexplained = []
        for k in range(N_PLAYERS):
            for st, dur, v in spans(t, dmg[:, k]):
                if v not in BY_ITEM:
                    continue
                tot += 1
                want = CAUSES.get(v, set())
                cause = [u for u in used
                         if u[2] in want and st - WINDOW <= u[0] <= st + 0.5
                         and not (u[1] == k and v in FIELD_WIDE)]
                if cause:
                    ok += 1
                else:
                    unexplained.append((st - t0, k, v))
        grand_ok += ok
        grand_tot += tot
        print("   %d of %d item-caused hits have a matching item use within %.0fs"
              % (ok, tot, WINDOW))
        for st, k, v in unexplained[:8]:
            print("      unexplained: %6.1fs slot %-2d %s"
                  % (st, k, DAMAGE[v][1]))
        print()
    if grand_tot:
        print("overall: %d of %d (%.0f%%)"
              % (grand_ok, grand_tot, 100.0 * grand_ok / grand_tot))


if __name__ == "__main__":
    main()
