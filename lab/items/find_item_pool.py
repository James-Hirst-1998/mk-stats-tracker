#!/usr/bin/env python3
"""Offline: map the fixed pool of item objects, and find a path to it.

Scanning MEM1 for the three item vtables found by `find_item_vtables.py` gives
42 hits at a constant stride of 0x1FC, at the same addresses on every frame of
the race. So the game keeps a fixed pool of item object slots and reuses them,
rewriting the vtable when a slot is handed to a different kind of item.

This walks the pool, reports which slots are ever used and what fields move,
and looks for a pointer to the pool base that is reachable from a static
address - a fitted constant is not acceptable here.

Run (no sudo):
  mk/bin/python3 -m lab.items.find_item_pool [recording-substring]
"""

import glob
import os
import sys
import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_vtables import learn, scan
from lab.items.find_live_items import is_heap, OFF_TYPE

ITEM_DIRECTOR = 0x809C3618
STRIDE = 0x1FC


def runs(addrs):
    """[(base, stride, count)] for every constant-stride run in `addrs`.

    The pool is not one array: each item class gets its own, so a run and the
    class that occupies it are the same thing.
    """
    addrs = sorted(addrs)
    out = []
    i = 0
    while i < len(addrs):
        j = i + 1
        step = addrs[j] - addrs[i] if j < len(addrs) else 0
        while j + 1 < len(addrs) and addrs[j + 1] - addrs[j] == step:
            j += 1
        out.append((addrs[i], step, j - i + 1))
        i = j + 1
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s\n" % os.path.basename(dirs[0]))

    vtables = sorted(learn(s))
    mid = len(s) // 2
    addrs = [a for a in scan(s.frame(mid), s.regions, vtables) if is_heap(a)]
    print("known vtables: %s" % " ".join("0x%08x" % v for v in vtables))
    print("%d instances, in %d runs:" % (len(addrs), len(runs(addrs))))

    groups = runs(addrs)
    for base, stride, n in groups:
        vt = s.u32(mid, base)
        print("  base 0x%08x stride 0x%-5x count %-3d vtable 0x%08x  type %s"
              % (base, stride, n, vt, s.u32(mid, base + OFF_TYPE)))

    lo = min(b for b, _, _ in groups)
    hi = max(b + st * n for b, st, n in groups) + 0x200
    print("\npool spans 0x%08x-0x%08x" % (lo, hi))

    director = s.u32(mid, ITEM_DIRECTOR)
    print("\npointers into that span from ItemDirector (0x%08x):" % director)
    for off in range(0, 0x400, 4):
        v = s.u32(mid, director + off)
        if v is not None and lo <= v < hi:
            print("  ItemDirector + 0x%03x -> 0x%08x" % (off, v))

    print("\nstatic words in 0x80900000-0x81800000 pointing into the span:")
    img = s.frame(mid)
    a0 = capfmt.addr_to_index(0x80900000, s.regions)
    a1 = capfmt.addr_to_index(0x81800000 - 4, s.regions) + 4
    words = img[a0:a1].view(">u4")
    m = np.nonzero((words >= lo) & (words < hi))[0]
    print("  (%d total)" % len(m))


if __name__ == "__main__":
    main()
