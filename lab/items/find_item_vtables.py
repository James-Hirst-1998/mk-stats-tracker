#!/usr/bin/env python3
"""Offline: learn the item object vtables, then count instances in the heap.

The manager at `*(0x809C2EF0)` is a per-frame registration list - it reads
empty on ~90% of sampled frames, so it cannot be used to watch items over time.
But the objects it hands out are real, and an object's vtable at `+0x00` is a
static address. Collect the vtables from the frames where the list happens to
be populated, then scan the heap for them on any frame.

If the game keeps a fixed pool of item objects for the whole race, the scan
count will be constant and large, and some field will say which are live.

Run (no sudo):
  mk/bin/python3 -m lab.items.find_item_vtables [recording-substring]
"""

import glob
import os
import sys
from collections import Counter, defaultdict

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import (OBJ_MANAGER, OFF_ENTRIES, OFF_COUNT,
                                       OFF_ENTRY_FLAGS, OFF_ENTRY_OBJ,
                                       OFF_TYPE, is_heap)

MEM1 = (0x80000000, 0x81800000)


def learn(s, step=1):
    """{vtable: Counter(type)} from every frame where the list is populated."""
    seen = defaultdict(Counter)
    for i in range(0, len(s), step):
        if s.index[i]["position"] is None:
            continue
        mgr = s.u32(i, OBJ_MANAGER)
        if not is_heap(mgr):
            continue
        table = s.u32(i, mgr + OFF_ENTRIES)
        count = s.u32(i, mgr + OFF_COUNT)
        if not is_heap(table) or not count or count > 4096:
            continue
        for k in range(count):
            entry = s.u32(i, table + k * 4)
            if not is_heap(entry):
                continue
            flags = s.u32(i, entry + OFF_ENTRY_FLAGS)
            if not flags or not flags & 2:
                continue
            obj = s.u32(i, entry + OFF_ENTRY_OBJ)
            if not is_heap(obj):
                continue
            vt = s.u32(i, obj)
            typ = s.u32(i, obj + OFF_TYPE)
            if vt is not None and MEM1[0] <= vt < MEM1[1] and typ is not None:
                seen[vt][typ] += 1
    return seen


def scan(img, regions, vtables):
    """Addresses whose word equals one of `vtables`, over MEM1 only."""
    start = capfmt.addr_to_index(MEM1[0], regions)
    end = capfmt.addr_to_index(MEM1[1] - 4, regions) + 4
    words = img[start:end].view(">u4")
    hit = np.zeros(len(words), dtype=bool)
    for vt in vtables:
        hit |= (words == vt)
    return MEM1[0] + np.nonzero(hit)[0] * 4


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s\n" % os.path.basename(dirs[0]))

    seen = learn(s)
    print("vtable      seen  item types")
    for vt, c in sorted(seen.items(), key=lambda kv: -sum(kv[1].values())):
        print("0x%08x  %4d  %s" % (vt, sum(c.values()), dict(c.most_common())))
    if not seen:
        print("  (list never populated)")
        return

    vtables = sorted(seen)
    print("\ninstances of those vtables in MEM1, over the race:")
    for i in range(0, len(s), max(1, len(s) // 12)):
        if s.index[i]["position"] is None:
            continue
        img = s.frame(i)
        addrs = scan(img, s.regions, vtables)
        heap = [a for a in addrs if is_heap(a)]
        print("  frame %5d  %3d total, %3d in heap  %s"
              % (i, len(addrs), len(heap),
                 " ".join("0x%08x" % a for a in heap[:8])))


if __name__ == "__main__":
    main()
