#!/usr/bin/env python3
"""
Offline: find the held item by SHAPE, the way progress was just found.

Matching on value against the screen failed, and matching against the pickup
register failed, because the held item may not be encoded the same way the HUD
draws it. So stop matching values and match structure instead. Whatever holds
the item must:

  - be one byte per racer, twelve of them at a constant stride
  - draw from a small alphabet (item ids, or ids plus a sentinel)
  - be piecewise constant: it settles, holds while you carry it, then changes
  - not be constant for the whole race, and not change every frame

Nothing else in memory looks like that. Twelve-at-a-constant-stride is the
constraint that does the work; it is what identified the player array.

Run (no sudo):
  mk/bin/python3 -m lab.items.find_held_array [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

STEP = 10                 # sample every 10th frame (2 Hz)
MAX_VALUE = 32            # item ids are 0..20; allow a little headroom
MIN_CHANGES = 4
MAX_CHANGES = 120
MIN_DISTINCT = 3
N_PLAYERS = 12
MIN_RUN = 8               # accept a partial array (some slots may be idle)
MAX_STRIDE = 0x1000


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

    race = [i for i, e in enumerate(s.index) if e["position"] is not None]
    lo, hi = race[0], race[-1]
    print("%s: in-race frames %d..%d, sampling every %d"
          % (os.path.basename(dirs[0]), lo, hi, STEP), flush=True)

    n = capfmt.image_size(s.regions)
    vmax = np.zeros(n, dtype=np.uint8)
    changes = np.zeros(n, dtype=np.uint16)
    seen = np.zeros((4, n), dtype=np.uint8)   # cheap distinct-value proxy
    prev = None
    nsamp = 0

    for i, img in s.frames(start=lo, stop=hi + 1, step=STEP):
        np.maximum(vmax, img, out=vmax)
        if prev is not None:
            changes += (img != prev)
        # remember up to 4 sampled values per byte, spread over the race
        slot = min(3, (nsamp * 4) // max(1, (hi - lo) // STEP + 1))
        seen[slot] = img
        prev = img.copy()
        nsamp += 1
        if nsamp % 50 == 0:
            print("   %d samples" % nsamp, flush=True)

    print("%d samples taken" % nsamp, flush=True)

    mask = (vmax <= MAX_VALUE) & (changes >= MIN_CHANGES) & (changes <= MAX_CHANGES)
    distinct = np.zeros(n, dtype=np.uint8)
    for a in range(4):
        d = np.ones(n, dtype=bool)
        for b in range(a):
            d &= seen[a] != seen[b]
        distinct += d
    mask &= distinct >= min(MIN_DISTINCT, 4)
    idx = np.nonzero(mask)[0]
    print("%d bytes are small-alphabet and piecewise-constant" % idx.size, flush=True)
    if idx.size == 0:
        return

    # Twelve at a constant stride.
    idxset = set(int(x) for x in idx)
    hits = []
    for a in idx:
        a = int(a)
        if a - 1 in idxset:
            continue                     # only consider run starts per stride below
        for stride in range(1, MAX_STRIDE):
            if a + stride not in idxset:
                continue
            k = 1
            while a + k * stride in idxset and k < N_PLAYERS:
                k += 1
            if k >= MIN_RUN:
                hits.append((k, stride, a))
    hits.sort(reverse=True)

    print("\nconstant-stride runs (count, stride, base):")
    seen_bases = set()
    shown = 0
    for k, stride, a in hits:
        key = (stride, a % max(stride, 1))
        if key in seen_bases:
            continue
        seen_bases.add(key)
        addr = capfmt.index_to_addr(a, s.regions)
        print("   x%-3d stride 0x%-5x base %s  values %s"
              % (k, stride, hex(addr),
                 [int(seen[t][a]) for t in range(4)]))
        shown += 1
        if shown >= 40:
            break
    if not hits:
        print("   none")


if __name__ == "__main__":
    main()
