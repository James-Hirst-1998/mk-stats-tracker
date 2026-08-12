#!/usr/bin/env python3
"""Offline: which objects in a pool are the live ones?

`probe_pool_fields.py` labels word 4 of a pool entry as the number of live
objects of that type - it went 0 -> 3 on a Triple Green Shell and 3 -> 4 when
another green was thrown. That gives a count but not an owner. To get the owner
we need to know WHICH objects those are, so this dumps every object in a pool
at a frame where the count is non-zero and looks for a field that separates
exactly `count` of them from the rest.

Run (no sudo):
  mk/bin/python3 -m lab.items.probe_live_flag [recording-substring] [type]
"""

import glob
import os
import sys

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import is_heap

ITEM_DIRECTOR = 0x809C3618
TABLE = 0x48
STRIDE = 0x24
OFF_ARRAY = 0x04
OFF_CAP = 0x08
OFF_LIVE = 0x10             # word 4


def entry(s, i, ty):
    director = s.u32(i, ITEM_DIRECTOR)
    if not is_heap(director):
        return None
    e = director + TABLE + ty * STRIDE
    arr, cap, live = (s.u32(i, e + OFF_ARRAY), s.u32(i, e + OFF_CAP),
                      s.u32(i, e + OFF_LIVE))
    if not is_heap(arr) or not cap or cap > 64 or live is None or live > cap:
        return None
    return arr, cap, live


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    ty = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s  item type %d\n" % (os.path.basename(dirs[0]), ty))

    shown = 0
    for i, _ in s.frames():
        if s.index[i]["position"] is None:
            continue
        e = entry(s, i, ty)
        if e is None or not e[2]:
            continue
        arr, cap, live = e
        print("frame %d  %.1fs  %d of %d live" % (i, s.index[i]["mono"], live, cap))
        print("  %-3s %-10s %-6s %-6s %-10s %-10s %-10s %s"
              % ("k", "object", "type", "owner", "+0x78", "+0x7c", "+0x0c", "+0x10"))
        for k in range(cap):
            obj = s.u32(i, arr + k * 4)
            if not is_heap(obj):
                continue
            print("  %-3d 0x%08x %-6s %-6s 0x%08x 0x%08x 0x%08x 0x%08x"
                  % (k, obj, s.u32(i, obj + 0x04), s.u8(i, obj + 0x6C),
                     s.u32(i, obj + 0x78) or 0, s.u32(i, obj + 0x7C) or 0,
                     s.u32(i, obj + 0x0C) or 0, s.u32(i, obj + 0x10) or 0))
        print()
        shown += 1
        if shown >= 3:
            break


if __name__ == "__main__":
    main()
