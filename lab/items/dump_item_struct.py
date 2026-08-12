#!/usr/bin/env python3
"""
Offline: characterise every byte of the 0x248 item struct, per racer.

The known register at +0x000 carries the roulette / award value and clears, so
the settled item is not it. But the thing that holds it is very likely a
neighbour in the same object. Dump a wide window around the array and describe
each offset: change count, alphabet, and how long its runs are.

A held item looks like: small alphabet, a handful of long runs, and it changes
at pickups rather than continuously.

Run (no sudo):
  mk/bin/python3 -m lab.items.dump_item_struct [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
STRIDE = 0x248
N_PLAYERS = 12
WINDOW_BACK = 0x80          # also look just before the array
STEP = 5

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def runs(col):
    """(value, length) runs."""
    out = []
    v, n = col[0], 1
    for x in col[1:]:
        if x == v:
            n += 1
        else:
            out.append((int(v), n))
            v, n = x, 1
    out.append((int(v), n))
    return out


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
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)

    span = WINDOW_BACK + STRIDE * N_PLAYERS
    rows, times = [], []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        base = be_u32(img, ip) + ITEM_DELTA - WINDOW_BACK
        bi = capfmt.addr_to_index(base, s.regions)
        if bi is None:
            continue
        rows.append(img[bi:bi + span].copy())
        times.append(s.index[i]["mono"])
    if not rows:
        print("no usable frames")
        return
    a = np.stack(rows)
    t = np.array(times) - times[0]
    print("%s: %d frames over %.1fs" % (os.path.basename(dirs[0]), len(a), t[-1]))
    print("window starts 0x%x before the array base\n" % WINDOW_BACK)

    print("%-8s %-7s %-7s %-9s %s"
          % ("slot0off", "changes", "runs", "medianrun", "alphabet"))
    interesting = []
    for o in range(WINDOW_BACK, WINDOW_BACK + STRIDE):
        col = a[:, o]
        vals = np.unique(col)
        if vals.size < 2:
            continue
        r = runs(col)
        lens = sorted(x[1] for x in r)
        med = lens[len(lens) // 2]
        ch = len(r) - 1
        alpha = set(int(v) for v in vals)
        item_like = alpha <= set(range(21)) | {0xFF}
        if not (3 <= ch <= 80 and med >= 2):
            continue
        interesting.append((o - WINDOW_BACK, ch, len(r), med, sorted(alpha), item_like))

    for off, ch, nr, med, alpha, item_like in interesting:
        print("+0x%03x   %-7d %-7d %-9d %s%s"
              % (off, ch, nr, med,
                 " ".join(str(v) for v in alpha[:14]),
                 "   <- item-id alphabet" if item_like else ""))
    if not interesting:
        print("nothing piecewise-constant in the struct window")
        return

    # Show the timeline of the most item-like offsets for slot 0.
    best = [x for x in interesting if x[5]][:6]
    for off, ch, nr, med, alpha, _ in best:
        col = a[:, WINDOW_BACK + off]
        print("\n+0x%03x timeline (slot 0):" % off)
        pos = 0
        for v, n in runs(col):
            if n * STEP / 20.0 >= 0.5:
                print("   %6.1fs  %-9s for %5.1fs"
                      % (t[pos], NAMES.get(v, str(v)), n * STEP / 20.0))
            pos += n


if __name__ == "__main__":
    main()
