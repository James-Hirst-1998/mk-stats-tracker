#!/usr/bin/env python3
"""Offline: read the per-item-type object pools out of ItemDirector.

The dump shows a regular table at `ItemDirector + 0x4C`, stride 0x24, one entry
per item type:

    +0x00  -> array of pointers to that type's objects (a free-list stack)
    +0x04  capacity
    +0x08  how many are still free

so the live objects of type t are the tail of that array, and
`capacity - free` is how many of that item are in the world right now. The
type's own index into the table is the same index the collision code feeds to
the handler table at 0x808B5468.

Run (no sudo):
  mk/bin/python3 -m lab.items.read_item_pools [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import is_heap, OFF_TYPE

ITEM_DIRECTOR = 0x809C3618
POOL_TABLE = 0x4C            # ItemDirector + this, then type * POOL_STRIDE
POOL_STRIDE = 0x24
OFF_POOL_ARRAY = 0x00
OFF_POOL_CAP = 0x04
OFF_POOL_FREE = 0x08
N_TYPES = 20


def pools(s, i):
    """{type: (array, capacity, free)} for every type with a real pool."""
    director = s.u32(i, ITEM_DIRECTOR)
    if not is_heap(director):
        return {}
    out = {}
    for t in range(N_TYPES):
        e = director + POOL_TABLE + t * POOL_STRIDE
        arr = s.u32(i, e + OFF_POOL_ARRAY)
        cap = s.u32(i, e + OFF_POOL_CAP)
        free = s.u32(i, e + OFF_POOL_FREE)
        if is_heap(arr) and cap and cap <= 64 and free is not None and free <= cap:
            out[t] = (arr, cap, free)
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s\n" % os.path.basename(dirs[0]))

    i = len(s) // 2
    print("%-5s %-10s %-4s %-4s %-10s %-6s %s"
          % ("type", "array", "cap", "free", "obj[0]", "vtable", "obj type"))
    for t, (arr, cap, free) in sorted(pools(s, i).items()):
        obj = s.u32(i, arr)
        print("%-5d 0x%08x %-4d %-4d 0x%08x 0x%08x %s"
              % (t, arr, cap, free, obj or 0, s.u32(i, obj) or 0,
                 s.u32(i, obj + OFF_TYPE)))

    # Does `cap - free` behave like a live count over the race?
    print("\nlive objects per type, over the race:")
    peak = Counter()
    ever = Counter()
    step = max(1, len(s) // 600)
    for j in range(0, len(s), step):
        if s.index[j]["position"] is None:
            continue
        for t, (arr, cap, free) in pools(s, j).items():
            n = cap - free
            peak[t] = max(peak[t], n)
            ever[t] += n
    for t in sorted(peak):
        print("  type %-3d peak %-3d live, %d object-frames" % (t, peak[t], ever[t]))


if __name__ == "__main__":
    main()
