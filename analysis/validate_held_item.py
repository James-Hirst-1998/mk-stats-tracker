#!/usr/bin/env python3
"""
Offline: validate item-struct +0x004 as the held item, on every recording.

Alignment on pickup edges (align_item_video.py) shows +0x004 turns non-empty
within 0.13s of the item box being drawn, holds one constant id for the whole
time the item is carried, and clears when it is used. The id matches the icon
on screen in every case checked by eye - Bullet Bill, Red Shell, Banana,
Bob-omb, Fake Item Box, Triple Bananas.

This checks it holds structurally for all twelve racers on every recording, and
looks for the quantity field that goes with triple items.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_held_item
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
STRIDE = 0x248
N_PLAYERS = 12
OFF_HELD = 0x01C
EMPTY = 20
COUNT_CANDIDATES = (0x008, 0x00B, 0x020, 0x094, 0x193, 0x230)
TRIPLES = {5: 3, 16: 3, 17: 3, 18: 3}
STEP = 5

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

    for d in dirs:
        s = Session(d)
        ip = capfmt.addr_to_index(ITEM_PTR, s.regions)
        held = [[] for _ in range(N_PLAYERS)]
        counts = {o: [] for o in COUNT_CANDIDATES}
        frames = 0
        for i, img in s.frames(step=STEP):
            if s.index[i]["position"] is None:
                continue
            bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
            if bi is None:
                continue
            frames += 1
            for p in range(N_PLAYERS):
                held[p].append(int(img[bi + p * STRIDE + OFF_HELD]))
            for o in COUNT_CANDIDATES:
                counts[o].append(int(img[bi + o]))

        print("=" * 78)
        print("%s  (%d frames)" % (os.path.basename(d), frames))
        if not frames:
            continue
        bad = 0
        for p in range(N_PLAYERS):
            a = np.array(held[p])
            vals = sorted(set(int(v) for v in np.unique(a)))
            if not set(vals) <= set(range(21)):
                bad += 1
            n_runs = int((np.diff(a) != 0).sum())
            busy = 100.0 * (a != EMPTY).mean()
            print("  slot %-2d holding %5.1f%% of the race, %3d changes, items %s"
                  % (p, busy, n_runs,
                     " ".join(NAMES.get(v, str(v)) for v in vals if v != EMPTY)[:60]))
        print("  %d/%d slots have a clean item-id alphabet" % (N_PLAYERS - bad, N_PLAYERS))

        # Which neighbouring byte reads 3 while a triple item is held?
        h0 = np.array(held[0])
        trip = np.isin(h0, list(TRIPLES))
        single = (h0 != EMPTY) & ~trip
        if trip.sum() > 5 and single.sum() > 5:
            print("  quantity candidates (value while holding a triple / a single):")
            for o in COUNT_CANDIDATES:
                c = np.array(counts[o])
                print("    +0x%03x  triple %-18s single %s"
                      % (o,
                         sorted(set(int(v) for v in np.unique(c[trip])))[:6],
                         sorted(set(int(v) for v in np.unique(c[single])))[:6]))


if __name__ == "__main__":
    main()
