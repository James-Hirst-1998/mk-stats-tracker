#!/usr/bin/env python3
"""Offline: does the object manager's population track item uses?

If `*(0x809C2EF0)` really is the item object pool, its entry count should climb
when somebody throws something and fall when it hits or is picked up. If it
does not move with item uses, it is the wrong manager and the low "3 alive"
number means nothing.

Run (no sudo):
  mk/bin/python3 -m lab.items.trace_obj_count <recording-substring>
"""

import glob
import os
import sys

import numpy as np

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import OBJ_MANAGER, OFF_COUNT, is_heap
from analysis.cross_check_damage import read_held, uses, ITEM_NAMES


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s\n" % os.path.basename(dirs[0]))

    n = len(s)
    t = np.full(n, np.nan)
    count = np.full(n, -1)
    for i, _ in s.frames():
        if s.index[i]["position"] is None:
            continue
        t[i] = s.index[i]["mono"]
        mgr = s.u32(i, OBJ_MANAGER)
        if not is_heap(mgr):
            continue
        c = s.u32(i, mgr + OFF_COUNT)
        if c is not None and c < 4096:
            count[i] = c

    ok = count >= 0
    print("count read on %d/%d frames, range %d..%d, mean %.2f"
          % (ok.sum(), n, count[ok].min(), count[ok].max(), count[ok].mean()))
    print("histogram %s" % dict(zip(*[x.tolist() for x in
                                      np.unique(count[ok], return_counts=True)])))

    used = uses(t, read_held(s))
    t0 = np.nanmin(t)
    print("\n%d item uses; count around each of the first 25:" % len(used))
    for when, who, item in used[:25]:
        j = int(np.nanargmin(np.abs(t - when)))
        window = count[max(0, j - 2):j + 8]
        print("  %6.1fs slot %-2d %-20s %s"
              % (when - t0, who, ITEM_NAMES.get(item, item),
                 " ".join("%d" % v for v in window)))


if __name__ == "__main__":
    main()
