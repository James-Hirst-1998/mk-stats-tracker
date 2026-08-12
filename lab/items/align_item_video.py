#!/usr/bin/env python3
"""
Offline: align video to memory using pickup edges, then judge the item field.

VIDEO_OFFSET was originally read off the recorder's own terminal, visible in
the screen recording - but that status line only refreshes about once a second,
so the offset carried a second of slop and every comparison inherited it.

The item box appearing is a sharp event in both the video and memory. So align
on those edges: slide the memory series against the video and take the shift
that matches the most appear/disappear transitions. Then, at that shift, report
how the item field's runs line up with the box being drawn.

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.align_item_video [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, FPS

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
OFF_HELD = 0x004
EMPTY = 20
STEP = 1
SHIFTS = np.arange(-2.0, 30.0, 0.05)
TOL = 0.5

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def edges(sig, t):
    up, down = [], []
    for i in range(1, len(sig)):
        if sig[i] and not sig[i - 1]:
            up.append(t[i])
        elif sig[i - 1] and not sig[i]:
            down.append(t[i])
    return np.array(up), np.array(down)


def match(a, b, tol=TOL):
    if not len(a) or not len(b):
        return 0
    return int(sum(np.min(np.abs(b - x)) <= tol for x in a))


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
    os.makedirs(cache, exist_ok=True)
    movs = glob.glob(os.path.join(path, "*.mov"))
    extract(movs[0], os.path.join(cache, "itembox.raw"))
    held = held_series(os.path.join(cache, "itembox.raw"))
    vt = np.arange(len(held)) / FPS
    v_up, v_down = edges(held, vt)

    s = Session(path)
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)
    mt, val = [], []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
        if bi is None:
            continue
        mt.append(s.index[i]["mono"])
        val.append(int(img[bi + OFF_HELD]))
    mt = np.array(mt)
    val = np.array(val)
    m_sig = val != EMPTY
    m_up, m_down = edges(m_sig, mt)
    print("video: %d box-appear, %d box-vanish" % (len(v_up), len(v_down)))
    print("memory: %d item-appear, %d item-vanish" % (len(m_up), len(m_down)))

    best = None
    for sh in SHIFTS:
        sc = match(m_up - sh, v_up) + match(m_down - sh, v_down)
        if best is None or sc > best[1]:
            best = (sh, sc)
    sh, sc = best
    total = len(m_up) + len(m_down)
    print("\nbest shift %.2fs matches %d/%d memory edges to the video"
          % (sh, sc, total))

    # Per-run comparison at the best shift.
    print("\n%-8s %-10s %-8s %-8s" % ("video t", "item", "mem run", "box run"))
    runs = []
    v0, start = val[0], 0
    for j in range(1, len(val) + 1):
        if j == len(val) or val[j] != v0:
            runs.append((int(v0), mt[start], mt[min(j, len(mt) - 1)]))
            if j < len(val):
                v0, start = val[j], j
    late, early = [], []
    for v, a, b in runs:
        if v == EMPTY or b - a < 0.3:
            continue
        va, vb = a - sh, b - sh
        fa, fb = int(va * FPS), int(vb * FPS)
        if fa < 0 or fb >= len(held):
            continue
        # extend the video run around this window
        k = fa
        while k > 0 and held[k - 1]:
            k -= 1
        m = fb
        while m < len(held) - 1 and held[m]:
            m += 1
        print("%-8.1f %-10s %.1f-%.1f  %.1f-%.1f"
              % (va, NAMES.get(v, v), va, vb, k / FPS, m / FPS))
        late.append(va - k / FPS)
        early.append(m / FPS - vb)
    if late:
        print("\nmemory run starts %.2fs after the box appears (median)"
              % float(np.median(late)))
        print("memory run ends   %.2fs before the box vanishes (median)"
              % float(np.median(early)))


if __name__ == "__main__":
    main()
