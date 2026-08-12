#!/usr/bin/env python3
"""
Offline: find the held-item byte using item pickups as the anchor.

`0x8124c3db` (found via the screen recording) carries the item you have just
been awarded and then clears back to 20. It is an acquisition event, not the
held state - James spotted this live, and a frame-by-frame trace confirms it
reads 20 for the whole time the item box is on screen.

But it gives a much better anchor than the video does. Whatever holds the item
must equal the awarded value for a sustained period right after each pickup,
and every pickup awards a different item, so a handful of pickups collapses the
search fast. This needs no video at all.

  1. trace the acquisition register over the race, take frames where it goes
     from empty to some item X
  2. a while later, keep bytes equal to that same X
  3. intersect over pickups with differing X

Run (no sudo):
  mk/bin/python3 -m lab.items.find_held_from_pickup [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PICKUP_ADDR = 0x8124C3DB
EMPTY = 20
DELAYS = (10, 20, 30)          # frames after the pickup to test (0.5s, 1s, 1.5s)
MAX_EVENTS = 12

NAMES = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
         4: "Mushroom", 5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell",
         8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
         12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
         16: "Triple Green", 17: "Triple Red", 18: "Triple Bananas",
         19: "(unused)", 20: "empty"}


def trace(s, addr):
    idx = capfmt.addr_to_index(addr, s.regions)
    out = np.full(len(s), -1, dtype=np.int16)
    for i, img in s.frames():
        out[i] = img[idx]
    return out


def pickups(tr):
    """Frames where the register goes empty -> item, with the item value."""
    ev = []
    for i in range(1, len(tr)):
        if tr[i] != EMPTY and tr[i] >= 0 and tr[i - 1] == EMPTY:
            ev.append((i, int(tr[i])))
    return ev


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "frantic"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])
    print("tracing acquisition register %s" % hex(PICKUP_ADDR), flush=True)
    tr = trace(s, PICKUP_ADDR)

    ev = pickups(tr)
    print("%d pickup events: %s"
          % (len(ev), [(f, NAMES.get(v, v)) for f, v in ev[:16]]), flush=True)
    if len(ev) < 3:
        print("not enough pickups to match against")
        return

    # Prefer events whose awarded item differs from the previous one, so each
    # constraint rules out different bytes.
    chosen, last = [], None
    for f, v in ev:
        if v != last:
            chosen.append((f, v))
            last = v
        if len(chosen) >= MAX_EVENTS:
            break

    want = {}
    for f, v in chosen:
        for d in DELAYS:
            if f + d < len(s):
                want.setdefault(f + d, []).append(v)

    mask = None
    for i, img in s.frames(stop=max(want) + 1):
        if i not in want:
            continue
        v = want[i][0]
        eq = img == np.uint8(v)
        mask = eq.copy() if mask is None else (mask & eq)
        print("   f%-5d expect %-16s %d survivors"
              % (i, NAMES.get(v, v), int(mask.sum())), flush=True)
        if int(mask.sum()) == 0:
            print("   -> nothing survives; the held value may not persist this long")
            break

    if mask is None:
        return
    surv = np.nonzero(mask)[0]
    print("\n%d bytes equal the awarded item after every pickup:" % surv.size)
    for idx in surv[:40]:
        print("    %s" % hex(capfmt.index_to_addr(int(idx), s.regions)))


if __name__ == "__main__":
    main()
