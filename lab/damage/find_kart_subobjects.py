#!/usr/bin/env python3
"""
Offline: follow each kart's pointers to the sub-object holding the hit timers.

read_kart_timers.py found only four countdown fields inside 0x2000 of a kart
base, which matches the public docs: the timers live in PlayerSub10 and
PlayerSub18, separate allocations the kart points at rather than fields inline.

So walk the pointer table at the head of each kart object, collect everything it
points at in the heap, and look for a countdown field at the SAME offset in all
twelve sub-objects. A field that exists at one offset across all twelve karts is
per-racer state; anything else is coincidence.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_kart_subobjects [recording-substring]
"""

import glob
import os
import sys
from collections import defaultdict

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

VTABLE = 0x808CB6B8
HEAP = (0x81100000, 0x81280000)
PTR_SCAN = 0x400           # bytes at the head of a kart to read pointers from
SUB_SPAN = 0x400           # bytes of each sub-object to examine
STEP = 3
MAX_TIMER = 1500
MIN_FIRES = 2
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

    mid = len(s) // 2
    img = None
    for i, frame in s.frames(stop=mid + 1):
        img = frame
    words = img.view(">u4")
    occ = np.nonzero(words == np.uint32(VTABLE))[0]
    bases = sorted(a for a in (capfmt.index_to_addr(int(k) * 4, s.regions)
                               for k in occ)
                   if a is not None and HEAP[0] <= a < HEAP[1])
    if len(bases) != N_PLAYERS:
        print("vtable found %d times, expected %d" % (len(bases), N_PLAYERS))
        return
    print("%s: %d kart objects" % (os.path.basename(dirs[0]), len(bases)),
          flush=True)

    # Pointer table at the head of each kart, keyed by the offset it sits at.
    subs = defaultdict(list)          # kart offset -> [sub address per kart]
    for b in bases:
        bi = capfmt.addr_to_index(b, s.regions)
        for off in range(0, PTR_SCAN, 4):
            w = int(np.frombuffer(img[bi + off:bi + off + 4].tobytes(),
                                  dtype=">u4")[0])
            if HEAP[0] <= w < HEAP[1]:
                subs[off].append(w)
    subs = {o: v for o, v in subs.items() if len(v) == N_PLAYERS}
    print("%d pointer slots are populated in all twelve karts: %s"
          % (len(subs), [hex(o) for o in sorted(subs)][:20]), flush=True)
    if not subs:
        return

    # Track every candidate sub-object over the race.
    slots = sorted(subs)
    starts = {o: [capfmt.addr_to_index(a, s.regions) for a in subs[o]]
              for o in slots}
    times, blocks = [], []
    for i, frame in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        row = {}
        bad = False
        for o in slots:
            try:
                row[o] = np.stack([
                    np.frombuffer(frame[j:j + SUB_SPAN].tobytes(), dtype=">u2")
                    for j in starts[o]])
            except Exception:
                bad = True
                break
        if bad:
            continue
        times.append(s.index[i]["mono"])
        blocks.append(row)
    t = np.array(times)
    print("%d frames tracked" % len(t), flush=True)
    if len(t) < 50:
        return

    dt = np.diff(t)
    want = dt * 60.0
    print("\ncountdown fields at the same offset in >=4 of the twelve karts:")
    found = False
    for o in slots:
        a = np.stack([blocks[k][o] for k in range(len(blocks))])
        d = a[:-1] - a[1:]
        is_down = (a[:-1] > 0) & (np.abs(d - want[:, None, None]) <= 2.0)
        fires = is_down.sum(axis=0)
        quiet = (a == 0).mean(axis=0)
        good = (fires >= MIN_FIRES) & (quiet >= 0.5) & (a.max(axis=0) <= MAX_TIMER)
        # Requiring all twelve is too strict - plenty of racers never get
        # shocked or inked in a single race. Four is enough to be per-racer.
        allk = np.nonzero((good.sum(axis=0) >= 4)
                          & (quiet >= 0.5).all(axis=0))[0]
        for c in allk:
            vals = sorted(set(int(v) for v in np.unique(a[:, :, c])) - {0})
            print("   kart+0x%03x -> sub+0x%03x   fires %s   values %s"
                  % (o, c * 2, list(fires[:, c]), vals[:8]))
            found = True
    if not found:
        print("   none")


if __name__ == "__main__":
    main()
