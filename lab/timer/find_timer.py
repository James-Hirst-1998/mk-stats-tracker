#!/usr/bin/env python3
"""
Offline: find the race timer, then the lap splits sitting next to it.

The timer has an unmistakable shape: a u32 that advances by the same number of
emulated frames between every pair of samples and never goes backwards. At a
20 Hz capture against a 60 Hz game that is +3 per sample, every sample.

Once found, the neighbourhood is dumped, because Mario Kart Wii keeps the lap
splits as a small array of timer structs beside the running clock - so lap and
finish times come from the same object.

Run (no sudo):
  mk/bin/python3 -m lab.timer.find_timer [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

STEP = 4
TOP = 30


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
    race = [i for i, e in enumerate(s.index) if e["position"] is not None]
    lo, hi = race[0], race[-1]

    n = capfmt.image_size(s.regions) // 4
    steady = np.zeros(n, dtype=np.uint16)
    nonzero = np.zeros(n, dtype=np.uint16)
    prev = None
    prev_t = None
    samples = 0
    for i, img in s.frames(start=lo, stop=hi + 1, step=STEP):
        v = img.view(">u4").astype(np.int64)
        t = s.index[i]["mono"]
        if prev is not None:
            want = (t - prev_t) * 60.0
            d = v - prev
            steady += (np.abs(d - want) <= 1.5)
            nonzero += (d != 0)
            samples += 1
        prev, prev_t = v, t
        if samples and samples % 100 == 0:
            print("   %d samples" % samples, flush=True)

    print("%d samples" % samples, flush=True)
    score = steady.astype(np.float32) / max(samples, 1)
    score[nonzero < samples * 0.9] = 0        # must actually be running
    order = np.argsort(-score)[:TOP]
    print("\n%-12s %-8s %s" % ("address", "60Hz-like", "last value"))
    for j in order:
        addr = capfmt.index_to_addr(int(j) * 4, s.regions)
        print("%-12s %6.1f%%   %d" % (hex(addr), 100 * score[j], int(prev[j])))

    best = int(order[0])
    if score[best] < 0.9:
        print("\nno clean 60 Hz counter found")
        return
    addr = capfmt.index_to_addr(best * 4, s.regions)
    print("\ndumping 0x80 around %s at the last in-race frame" % hex(addr))
    img = s.frame(hi)
    base = best * 4 - 0x40
    for o in range(0, 0x80, 4):
        j = base + o
        a = capfmt.index_to_addr(j, s.regions)
        if a is None:
            continue
        w = int(np.frombuffer(img[j:j + 4].tobytes(), dtype=">u4")[0])
        f = float(np.frombuffer(img[j:j + 4].tobytes(), dtype=">f4")[0])
        mark = "  <- counter" if j == best * 4 else ""
        print("  %-12s u32 %-12d  f32 %-14.4f  %s%s"
              % (hex(a), w, f if abs(f) < 1e9 else float("nan"),
                 "frames->%.2fs" % (w / 60.0) if 0 < w < 60 * 600 else "", mark))


if __name__ == "__main__":
    main()
