#!/usr/bin/env python3
"""
Offline: pin the twelve kart objects via their vtable.

Scoring bytes against stalls keeps failing because a stall window is wide and
half the heap contains something that ticks. The structural route is better: if
the twelve player objects share a class, they share a vtable pointer, and a
vtable is a static address that appears exactly twelve times in the heap. That
identifies the objects with no labels at all - the same trick that confirmed the
player array earlier.

Steps:
  1. find u16 fields with the countdown shape inside the player heap
  2. group them into clusters - one cluster per object
  3. walk backwards from a cluster looking for a static pointer that repeats
     exactly twelve times at a consistent spacing from each cluster
  4. report the object bases and where the countdown fields sit inside them

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_kart_objects [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

HEAP = (0x81100000, 0x81280000)
STATIC = (0x80000000, 0x80A00000)
STEP = 2
MAX_TIMER = 1500
MIN_FIRES = 3
CLUSTER_GAP = 0x300
BACK = 0x600
N_PLAYERS = 12


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "mushroom"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])
    race = [i for i, e in enumerate(s.index) if e["position"] is not None]
    lo, hi = race[0], race[-1]

    n2 = capfmt.image_size(s.regions) // 2
    down = np.zeros(n2, dtype=np.uint16)
    zero = np.zeros(n2, dtype=np.uint16)
    huge = np.zeros(n2, dtype=bool)
    prev = prev_t = None
    samples = 0
    last = None
    for i, img in s.frames(start=lo, stop=hi + 1, step=STEP):
        v = img.view(">u2").astype(np.int32)
        t = s.index[i]["mono"]
        if prev is not None:
            want = (t - prev_t) * 60.0
            d = prev - v
            down += (prev > 0) & (v >= 0) & (np.abs(d - want) <= 2.0)
            zero += (v == 0)
            huge |= v > MAX_TIMER
            samples += 1
        prev, prev_t = v, t
        last = img
    print("%s: %d samples" % (os.path.basename(dirs[0]), samples), flush=True)

    ok = (~huge) & (down >= MIN_FIRES) & (zero >= samples * 0.5)
    idx = np.nonzero(ok)[0]
    addrs = sorted(a for a in (capfmt.index_to_addr(int(j) * 2, s.regions)
                               for j in idx)
                   if a is not None and HEAP[0] <= a < HEAP[1])
    print("%d countdown fields inside the player heap" % len(addrs), flush=True)
    if not addrs:
        return

    clusters, cur = [], [addrs[0]]
    for a in addrs[1:]:
        if a - cur[-1] <= CLUSTER_GAP:
            cur.append(a)
        else:
            clusters.append(cur)
            cur = [a]
    clusters.append(cur)
    clusters = [c for c in clusters if len(c) >= 2]
    print("%d clusters: %s" % (len(clusters), [hex(c[0]) for c in clusters[:16]]),
          flush=True)
    if len(clusters) < 4:
        return

    # Which static pointer sits just before every cluster, at the same distance?
    words = last.view(">u4")
    votes = Counter()
    for c in clusters:
        head = c[0]
        for back in range(0, BACK, 4):
            a = (head & ~3) - back
            j = capfmt.addr_to_index(a, s.regions)
            if j is None:
                continue
            w = int(np.frombuffer(last[j:j + 4].tobytes(), dtype=">u4")[0])
            if STATIC[0] <= w < STATIC[1]:
                votes[(w, back)] += 1

    print("\nstatic pointers appearing before many clusters:")
    for (w, back), cnt in votes.most_common(12):
        occ = np.nonzero(words == np.uint32(w))[0]
        occ_heap = [capfmt.index_to_addr(int(k) * 4, s.regions) for k in occ]
        occ_heap = [a for a in occ_heap if a and HEAP[0] <= a < HEAP[1]]
        print("   %s at -0x%-4x  before %2d clusters, %d occurrences in the heap"
              % (hex(w), back, cnt, len(occ_heap)))
        if cnt >= N_PLAYERS - 2 and len(occ_heap) in range(N_PLAYERS,
                                                           N_PLAYERS + 3):
            print("      -> object bases: %s"
                  % [hex(a) for a in sorted(occ_heap)[:N_PLAYERS]])


if __name__ == "__main__":
    main()
