#!/usr/bin/env python3
"""Offline: find which word of a pool entry is the live count.

`read_item_pools.py` located a table of 0x24-byte entries in ItemDirector, one
per item type, but guessed the field layout - `cap - free` never moved. This
just watches all nine words of every entry across a race and reports what
changes, which is the only honest way to label them.

Run (no sudo):
  mk/bin/python3 -m lab.items.probe_pool_fields [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import is_heap
from analysis.cross_check_damage import read_held, uses, ITEM_NAMES

ITEM_DIRECTOR = 0x809C3618
TABLE = 0x48                 # entry 0 starts here; word 0 is the type index
STRIDE = 0x24
WORDS = STRIDE // 4
N_TYPES = 15


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    print("%s\n" % os.path.basename(dirs[0]))

    n = len(s)
    t = np.full(n, np.nan)
    vals = np.full((n, N_TYPES, WORDS), -1, dtype=np.int64)
    for i, _ in s.frames():
        if s.index[i]["position"] is None:
            continue
        t[i] = s.index[i]["mono"]
        director = s.u32(i, ITEM_DIRECTOR)
        if not is_heap(director):
            continue
        for ty in range(N_TYPES):
            e = director + TABLE + ty * STRIDE
            for w in range(WORDS):
                v = s.u32(i, e + w * 4)
                if v is not None:
                    vals[i, ty, w] = v

    ok = ~np.isnan(t)
    print("%-5s %s" % ("type", "  ".join("w%-14d" % w for w in range(WORDS))))
    for ty in range(N_TYPES):
        cells = []
        for w in range(WORDS):
            col = vals[ok, ty, w]
            col = col[col >= 0]
            if not len(col):
                cells.append("-")
                continue
            lo, hi = col.min(), col.max()
            cells.append("%d" % lo if lo == hi else "%d..%d" % (lo, hi))
        print("%-5d %s" % (ty, "  ".join("%-15s" % c for c in cells)))

    # The word that moves should move when somebody throws that kind of item.
    used = uses(t, read_held(s))
    t0 = np.nanmin(t)
    moving = [(ty, w) for ty in range(N_TYPES) for w in range(WORDS)
              if len(set(vals[ok, ty, w].tolist())) > 1]
    print("\nwords that move: %s" % moving)
    for ty, w in moving[:6]:
        col = vals[:, ty, w]
        rises = [j for j in range(1, n) if col[j] > col[j - 1] >= 0]
        print("\n type %d word %d: %d rises" % (ty, w, len(rises)))
        for j in rises[:10]:
            near = [u for u in used if abs(u[0] - t[j]) < 1.5]
            print("   %6.1fs  %d -> %d   uses within 1.5s: %s"
                  % (t[j] - t0, col[j - 1], col[j],
                     ", ".join("slot %d %s" % (u[1], ITEM_NAMES.get(u[2], u[2]))
                               for u in near) or "-"))


if __name__ == "__main__":
    main()
