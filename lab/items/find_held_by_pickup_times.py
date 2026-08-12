#!/usr/bin/env python3
"""
Offline: find the persistent held item using pickup TIMES, not values.

item-struct +0x004 names the item correctly and turns on the instant the box
appears - but its runs are 3.55, 3.57, 3.55, 3.57 seconds for the local player
and 1.15s for every AI. That is a fixed lifetime, not a player deciding when to
throw something, so +0x004 is an announce slot: right item, wrong duration.

The real inventory field must change at the same moments. So search on timing
and ignore encoding entirely: score every byte in memory by how many pickup
instants it changes at, penalising bytes that change constantly. This finds the
field even if it stores items differently from the way the HUD numbers them.

Run (no sudo):
  mk/bin/python3 -m lab.items.find_held_by_pickup_times [recording]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
STRIDE = 0x248
OFF_ANNOUNCE = 0x004
EMPTY = 20
N_PLAYERS = 12
WINDOW = 24           # frames either side of an edge (1.2s at 20 Hz)
TOP = 40

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


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
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)

    # Pass 1: local player's announce slot, to get pickup frames and item ids.
    ann = np.full(len(s), -1, dtype=np.int16)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
        if bi is not None:
            ann[i] = int(img[bi + OFF_ANNOUNCE])
    rise = [i for i in range(1, len(s))
            if ann[i] not in (-1, EMPTY) and ann[i - 1] == EMPTY]
    fall = [i for i in range(1, len(s))
            if ann[i] == EMPTY and ann[i - 1] not in (-1, EMPTY)]
    print("%s: %d announce-on, %d announce-off events"
          % (os.path.basename(dirs[0]), len(rise), len(fall)), flush=True)
    print("  items: %s"
          % [NAMES.get(int(ann[i]), int(ann[i])) for i in rise[:10]], flush=True)
    if len(rise) < 5:
        print("not enough pickups")
        return

    edges = {"on": rise, "off": fall}
    n = capfmt.image_size(s.regions)
    marks = {k: np.zeros((len(v), n), dtype=bool) for k, v in edges.items()}
    which = {k: {} for k in edges}
    for k, v in edges.items():
        for m, f in enumerate(v):
            for j in range(max(0, f - WINDOW), min(len(s), f + WINDOW + 1)):
                which[k][j] = m

    total_changes = np.zeros(n, dtype=np.uint16)
    prev = None
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            prev = None
            continue
        if prev is not None:
            d = img != prev
            total_changes += d
            for k in edges:
                m = which[k].get(i)
                if m is not None:
                    marks[k][m] |= d
        prev = img.copy()
        if i % 500 == 0:
            print("   frame %d/%d" % (i, len(s)), flush=True)

    for k in edges:
        report(s, k, edges[k], marks[k], total_changes)


def report(s, label, picks, marks, total_changes):
    hits = marks.sum(axis=0)
    score = hits.astype(np.float32) / len(picks)
    # A field that changes at every pickup but also thousands of other times is
    # just churn; require its total change count to be pickup-shaped.
    score[total_changes > len(picks) * 12] = 0
    score[total_changes < len(picks)] = 0

    order = np.argsort(-score)[:TOP]
    print("\n=== changes at announce-%s ===" % label)
    print("%-12s %-9s %-9s" % ("address", "events", "total changes"))
    for j in order:
        addr = capfmt.index_to_addr(int(j), s.regions)
        print("%-12s %2d/%-6d %d"
              % (hex(addr), int(hits[j]), len(picks), int(total_changes[j])))

    good = [int(j) for j in order if score[j] >= 0.8]
    print("\n%d bytes change at >=80%% of pickups" % len(good))
    gs = set(good)
    print("of those, runs of 12 at a constant stride:")
    found = False
    for a in good:
        for stride in list(range(4, 0x800, 4)) + [STRIDE]:
            k = 1
            while a + k * stride in gs and k < N_PLAYERS:
                k += 1
            if k >= 8:
                print("   x%-3d stride 0x%-4x base %s"
                      % (k, stride, hex(capfmt.index_to_addr(a, s.regions))))
                found = True
    if not found:
        print("   none")


if __name__ == "__main__":
    main()
