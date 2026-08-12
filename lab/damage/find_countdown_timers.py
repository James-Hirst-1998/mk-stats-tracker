#!/usr/bin/env python3
"""
Offline: find the per-racer hit timers by their countdown shape.

Scoring bytes against progress stalls does not work - stalls also come from
walls, grass and bad lines, so the label is too noisy and nothing beats the
base rate. But the public structure docs name the fields we want and they are
all the same shape:

    PlayerSub10 +0x18c shockTimer          (Zappers, Thunder Cloud, Lightning)
                +0x18e blooperCharacterInk
                +0x192 crushTimer          (Thwomp and Mega)
                +0x194 megaTimer
    PlayerSub18 +0x2e  solidOobTimer       (out of bounds)
    PlayerSub1c +0x10  bitfield: hit by an item, respawning

A countdown timer sits at zero, jumps to some positive value when the thing
happens, then decrements once per game frame back to zero. At a 20 Hz capture
against a 60 Hz game that is -3 per sample. Nothing else in memory looks like
that, so this needs no ground truth at all.

Twelve hits at a constant stride then gives the player object array.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_countdown_timers [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

STEP = 2
MAX_TIMER = 1500          # 25s at 60Hz
MIN_RUNS = 8              # samples seen counting down
N_PLAYERS = 12
TOP = 60


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

    n = capfmt.image_size(s.regions) // 2
    down = np.zeros(n, dtype=np.uint16)      # decrementing while positive
    zero = np.zeros(n, dtype=np.uint16)      # resting at zero
    huge = np.zeros(n, dtype=bool)           # ever implausibly large
    samples = 0
    prev = None
    prev_t = None

    for i, img in s.frames(start=lo, stop=hi + 1, step=STEP):
        v = img.view(">u2").astype(np.int32)
        t = s.index[i]["mono"]
        if prev is not None:
            want = (t - prev_t) * 60.0
            d = prev - v
            down += (prev > 0) & (v >= 0) & (np.abs(d - want) <= 2.0)
            zero += (v == 0)
            huge |= v > MAX_TIMER
            samples += 1
        prev, prev_t = v, t
        if samples and samples % 200 == 0:
            print("   %d samples" % samples, flush=True)

    print("%d samples" % samples, flush=True)
    ok = (~huge) & (down >= MIN_RUNS) & (zero >= samples * 0.5)
    idx = np.nonzero(ok)[0]
    print("%d u16 fields count down at 60Hz and rest at zero" % idx.size,
          flush=True)
    if idx.size == 0:
        return

    order = idx[np.argsort(-down[idx])][:TOP]
    print("\n%-12s %-8s %s" % ("address", "counting", "at rest"))
    for j in order:
        print("%-12s %6d    %.0f%%"
              % (hex(capfmt.index_to_addr(int(j) * 2, s.regions)),
                 int(down[j]), 100.0 * zero[j] / samples))

    # Twelve at a constant stride.
    hits = set(int(x) for x in idx)
    print("\nruns of >=8 at a constant stride (byte addresses):")
    best = []
    for a in idx:
        a = int(a)
        for stride in range(2, 0x4000, 2):
            k = 1
            while a + k * stride in hits and k < N_PLAYERS:
                k += 1
            if k >= 8:
                best.append((k, stride * 2, a * 2))
    best.sort(reverse=True)
    shown = set()
    for k, stride, a in best:
        key = (k, stride)
        if key in shown:
            continue
        shown.add(key)
        print("   x%-3d stride 0x%-5x base %s"
              % (k, stride, hex(capfmt.index_to_addr(a, s.regions))))
        if len(shown) >= 15:
            break
    if not best:
        print("   none")


if __name__ == "__main__":
    main()
