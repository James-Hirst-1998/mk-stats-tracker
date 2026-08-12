#!/usr/bin/env python3
"""
Offline: find race progress by its SHAPE, not by guessing offsets.

The previous attempt picked plausible-looking floats out of the 0xc4 player
struct and checked their range. That was wrong (see ATTEMPTS.md). This searches
every 4-byte-aligned float in the whole recorded image for the one property
race completion must have and almost nothing else does: it never goes down.

Constraints applied in order, cheapest first:
  1. finite, and inside a sane band the whole race
  2. non-decreasing at every sampled frame
  3. actually moves - a constant is trivially non-decreasing
  4. total travel over the race is lap-shaped (roughly 1 unit per lap)

Survivors are then grouped by address so a 12-racer array shows up as 12 hits
at a constant stride.

Run (no sudo):
  mk/bin/python3 -m lab.progress.find_progress [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

SAMPLES = 60           # frames spread across the race
BAND = (-1.0, 64.0)    # plausible range for a lap/checkpoint counter
MIN_TRAVEL = 1.5       # must advance at least this far over the race
MAX_TRAVEL = 48.0
MIN_MOVES = 0.5        # fraction of steps where it must strictly increase
EPS = 1e-4


def race_frames(s):
    return [i for i, e in enumerate(s.index) if e["position"] is not None]


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

    rf = race_frames(s)
    if len(rf) < SAMPLES * 2:
        print("only %d in-race frames" % len(rf))
        return
    step = max(1, len(rf) // SAMPLES)
    want = set(rf[::step])
    print("%s: %d in-race frames, sampling %d"
          % (os.path.basename(dirs[0]), len(rf), len(want)), flush=True)

    mask = None
    prev = None
    first = None
    moves = None
    n_steps = 0

    for i, img in s.frames(stop=max(want) + 1):
        if i not in want:
            continue
        v = img.view(">f4").astype(np.float32)
        ok = np.isfinite(v) & (v >= BAND[0]) & (v <= BAND[1])
        if mask is None:
            mask = ok
            first = v.copy()
            moves = np.zeros(v.size, dtype=np.int16)
        else:
            mask &= ok
            mask &= v >= prev - EPS
            moves += (v > prev + EPS)
            n_steps += 1
        prev = v
        alive = int(mask.sum())
        print("   f%-5d %10d still non-decreasing" % (i, alive), flush=True)
        if alive == 0:
            break

    if mask is None or not mask.any():
        print("nothing survives; loosen BAND or EPS")
        return

    travel = prev - first
    mask &= travel >= MIN_TRAVEL
    mask &= travel <= MAX_TRAVEL
    mask &= moves >= int(n_steps * MIN_MOVES)

    surv = np.nonzero(mask)[0]
    print("\n%d floats are monotone, moving, and lap-shaped" % surv.size)
    if surv.size == 0:
        return

    rows = []
    for j in surv[:4000]:
        addr = capfmt.index_to_addr(int(j) * 4, s.regions)
        rows.append((addr, float(first[j]), float(prev[j]), int(moves[j])))
    rows.sort()

    print("\n%-12s %10s %10s %8s" % ("address", "start", "end", "moves"))
    for addr, a, b, m in rows[:60]:
        print("%-12s %10.4f %10.4f %8d" % (hex(addr), a, b, m))
    if len(rows) > 60:
        print("... %d more" % (len(rows) - 60))

    # Group by constant stride: a per-racer array is 12 hits evenly spaced.
    addrs = np.array([r[0] for r in rows], dtype=np.int64)
    print("\nconstant-stride runs of >= 6 hits:")
    found = False
    for k in range(len(addrs)):
        d = None
        n = 1
        for j in range(k + 1, len(addrs)):
            gap = addrs[j] - addrs[j - 1]
            if d is None:
                d = gap
            elif gap != d:
                break
            n += 1
        if n >= 6 and d:
            print("   base %s  stride 0x%x  x%d" % (hex(int(addrs[k])), d, n))
            found = True
    if not found:
        print("   none")


if __name__ == "__main__":
    main()
