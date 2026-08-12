#!/usr/bin/env python3
"""
Offline: find the out-of-bounds / Lakitu rescue field.

The Yoshi Falls recording has one confirmed fall. Race completion goes backward
when Lakitu puts you back, which is already a usable signal on its own, but it
also gives an exact labelled window to search in: video shows the kart leaving
the cliff at 79.6s, hitting the water at 80.2s and the screen wiping at 81.2s,
which is mono 90.6-92.2 at this recording's 11.0s offset.

So: find u16 fields that are non-zero across that window and zero for
essentially the whole rest of the race. One event cannot prove a field, but it
narrows 48M bytes to a handful that a second recording can then confirm.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_offroad [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

WINDOW = (89.5, 93.5)         # mono seconds around the confirmed fall
QUIET = 0.97                  # must be zero at least this often elsewhere
TOP = 40


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "yoshi"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])

    n = capfmt.image_size(s.regions) // 2
    inside = np.zeros(n, dtype=np.uint16)
    outside_zero = np.zeros(n, dtype=np.uint16)
    n_in = n_out = 0
    for i, img in s.frames(step=2):
        if s.index[i]["position"] is None:
            continue
        v = img.view(">u2")
        t = s.index[i]["mono"]
        if WINDOW[0] <= t <= WINDOW[1]:
            inside += (v != 0)
            n_in += 1
        elif t < WINDOW[0] - 3 or t > WINDOW[1] + 3:
            outside_zero += (v == 0)
            n_out += 1

    print("%d frames inside the fall, %d outside" % (n_in, n_out), flush=True)
    if not n_in or not n_out:
        print("window does not overlap the recording")
        return

    score = (inside.astype(np.float32) / n_in) * (
        outside_zero.astype(np.float32) / n_out >= QUIET)
    order = np.argsort(-score)[:TOP]
    print("\n%-12s %-10s %s" % ("address", "on in fall", "zero elsewhere"))
    for j in order:
        if score[j] <= 0:
            break
        print("%-12s %8.0f%%   %8.1f%%"
              % (hex(capfmt.index_to_addr(int(j) * 2, s.regions)),
                 100.0 * inside[j] / n_in, 100.0 * outside_zero[j] / n_out))


if __name__ == "__main__":
    main()
