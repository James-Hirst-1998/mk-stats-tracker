#!/usr/bin/env python3
"""
Offline: print the value timeline of specific addresses next to the roulette.

find_held_by_pickup_times.py turns up a handful of bytes that change at every
pickup and hardly ever otherwise. Whether any of them is the committed item is
a question about what they contain, not how often they move, so print them.

The committed item should turn non-empty as the roulette result clears - the
frames show the box settling on the final icon at exactly that moment - and
stay put until the item is used.

Run (no sudo):
  mk/bin/python3 -m lab.damage.trace_candidates [recording] [addr ...]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
OFF_ANNOUNCE = 0x004
EMPTY = 20

DEFAULT = [0x8140956E, 0x8140956F, 0x81409571, 0x81409572, 0x81409573,
           0x81409575, 0x81409576, 0x81409577, 0x813CD579, 0x813CD57A,
           0x813CD57B, 0x8140C37C, 0x8140C38B, 0x8140C38E, 0x8124C3CC,
           0x8124C3C3, 0x8124C3DF, 0x809C283C, 0x809C283F]

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def main():
    args = sys.argv[1:]
    which = args[0] if args and not args[0].startswith("0x") else "frantic"
    addrs = [int(a, 16) for a in args if a.startswith("0x")] or DEFAULT

    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)
    idx = [capfmt.addr_to_index(a, s.regions) for a in addrs]

    rows, ann, times = [], [], []
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
        ann.append(int(img[bi + OFF_ANNOUNCE]) if bi is not None else -1)
        rows.append([int(img[j]) if j is not None else -1 for j in idx])
        times.append(s.index[i]["mono"])
    a = np.array(rows)
    ann = np.array(ann)
    t = np.array(times) - times[0]

    print("%s: %d frames\n" % (os.path.basename(dirs[0]), len(a)))
    off = [i for i in range(1, len(ann))
           if ann[i] == EMPTY and ann[i - 1] not in (-1, EMPTY)]
    print("roulette settles at t = %s\n"
          % ["%.1f" % t[i] for i in off[:10]])

    for k, addr in enumerate(addrs):
        col = a[:, k]
        vals = sorted(set(int(v) for v in np.unique(col)))
        item_like = set(vals) <= set(range(21))
        print("%s  values %s%s"
              % (hex(addr), vals[:14], "   <- item-id alphabet" if item_like else ""))
        v, start = col[0], 0
        line = []
        for j in range(1, len(col) + 1):
            if j == len(col) or col[j] != v:
                dur = t[min(j, len(t) - 1)] - t[start]
                if dur >= 0.5:
                    label = NAMES.get(int(v), str(int(v))) if item_like else str(int(v))
                    line.append("%.0f:%s(%.1fs)" % (t[start], label, dur))
                if j < len(col):
                    v, start = col[j], j
        print("   " + "  ".join(line[:18]))
        print()


if __name__ == "__main__":
    main()
