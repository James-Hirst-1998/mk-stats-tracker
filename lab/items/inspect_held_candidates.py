#!/usr/bin/env python3
"""
Offline: inspect the bytes that scored well against the video.

score_held_global.py ranks every byte by how well "differs from resting" tracks
"item box on screen". The top of that list is HUD animation state (floats whose
top byte is 0xbf, i.e. -1.0f), which is real but only exists for the local
player. What we want is a gameplay field: item-id alphabet, twelve of them at a
constant stride.

This takes every byte above THRESHOLD, records its full value timeline, and
reports the ones whose alphabet looks like item ids - then checks whether they
repeat at a constant stride.

Run (no sudo):
  mk/bin/python3 -m lab.items.inspect_held_candidates [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, FPS, VIDEO_OFFSET

THRESHOLD = 0.88
STEP = 5
MAX_TRACK = 20000

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "frantic"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    path = dirs[0]
    cache = os.path.join(os.path.dirname(__file__), "cache", os.path.basename(path))
    frac = np.load(os.path.join(cache, "held_agreement.npy"))

    idx = np.nonzero(frac >= THRESHOLD)[0]
    print("%d bytes score >= %.0f%%" % (idx.size, 100 * THRESHOLD), flush=True)
    if idx.size == 0 or idx.size > MAX_TRACK:
        print("raise/lower THRESHOLD (%d candidates)" % idx.size)
        if idx.size > MAX_TRACK:
            idx = idx[np.argsort(-frac[idx])[:MAX_TRACK]]
            idx.sort()
        else:
            return

    s = Session(path)
    track, times = [], []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        track.append(img[idx].copy())
        times.append(s.index[i]["mono"])
    a = np.stack(track)
    t = np.array(times) - times[0]

    movs = glob.glob(os.path.join(path, "*.mov"))
    extract(movs[0], os.path.join(cache, "itembox.raw"))
    held = held_series(os.path.join(cache, "itembox.raw"))

    item_like = []
    for k in range(idx.size):
        vals = set(int(v) for v in np.unique(a[:, k]))
        if vals <= set(range(21)) and len(vals) >= 3:
            item_like.append(k)

    print("\n%d of them have an item-id alphabet" % len(item_like))
    for k in item_like[:40]:
        addr = capfmt.index_to_addr(int(idx[k]), s.regions)
        vals = sorted(set(int(v) for v in np.unique(a[:, k])))
        print("  %-12s %5.1f%%  values %s" % (hex(addr), 100 * frac[idx[k]], vals))

    if item_like:
        k = item_like[0]
        addr = capfmt.index_to_addr(int(idx[k]), s.regions)
        print("\ntimeline of %s vs video:" % hex(addr))
        col = a[:, k]
        v, start = col[0], 0
        for j in range(1, len(col) + 1):
            if j == len(col) or col[j] != v:
                dur = t[min(j, len(t) - 1)] - t[start]
                if dur >= 0.4:
                    vf = int((t[start] + times[0] - VIDEO_OFFSET) * FPS)
                    box = held[vf] if 0 <= vf < len(held) else None
                    print("   %6.1fs  %-9s %5.1fs   box=%s"
                          % (t[start], NAMES.get(int(v), str(int(v))), dur, box))
                if j < len(col):
                    v, start = col[j], j

    # Constant-stride check across all high scorers, not just item-like ones.
    print("\nlooking for 12 high scorers at a constant stride")
    hs = set(int(x) for x in idx)
    best = []
    for a0 in idx:
        a0 = int(a0)
        for stride in list(range(0x10, 0x1000, 4)) + [0x248, 0xc4]:
            k = 1
            while a0 + k * stride in hs and k < 12:
                k += 1
            if k >= 8:
                best.append((k, stride, a0))
    best.sort(reverse=True)
    for k, stride, a0 in best[:10]:
        print("   x%-3d stride 0x%-4x base %s"
              % (k, stride, hex(capfmt.index_to_addr(a0, s.regions))))
    if not best:
        print("   none")


if __name__ == "__main__":
    main()
