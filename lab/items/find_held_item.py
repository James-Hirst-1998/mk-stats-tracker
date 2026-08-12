#!/usr/bin/env python3
"""
Offline: find the SETTLED held-item byte, as opposed to the roulette value.

find_item_from_video.py found `0x8124c3db`, which matches the icon on screen at
any sampled moment - but that includes the roulette, so it tracks whatever the
box is cycling through rather than what you end up holding. James spotted this
live: the value moves while the box spins and does not stay put afterwards.

The distinguishing constraint is constancy. Whatever you actually hold does not
change from the moment the roulette settles until you use it, whereas the
roulette value changes several times a second. So:

  1. item box drawn / not drawn, per video frame (as before)
  2. inside each held run, sample several points from 1.5s in (past the
     roulette) to just before the box disappears
  3. keep bytes that are IDENTICAL at every sample within a run, differ from
     the empty value while held, and equal the empty value when not held

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.find_held_item [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, runs_of, FPS, VIDEO_OFFSET

ROULETTE_SKIP = 1.5            # seconds after the box appears before sampling
TAIL_GUARD = 0.3               # stop sampling this long before it disappears
MIN_HELD_RUN = 3.0
MIN_EMPTY_RUN = 2.0
SAMPLES_PER_RUN = 3
MAX_HELD_RUNS = 8
MAX_EMPTY_RUNS = 8

NAMES = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
         4: "Mushroom", 5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell",
         8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
         12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
         16: "Triple Green", 17: "Triple Red", 18: "Triple Bananas",
         19: "(unused)", 20: "empty"}


def nearest_frame(s, mono):
    best, bd = None, 1e9
    for i, e in enumerate(s.index):
        if e["position"] is None:
            continue
        d = abs(e["mono"] - mono)
        if d < bd:
            best, bd = i, d
    return best if bd < 0.4 else None


def plan(s, held):
    """[(frame, run_id_or_None)] in frame order; run_id groups a held run."""
    jobs = []
    held_runs = [r for r in runs_of(held)
                 if r[0] and r[2] - r[1] >= MIN_HELD_RUN][:MAX_HELD_RUNS]
    empty_runs = [r for r in runs_of(held)
                  if not r[0] and r[2] - r[1] >= MIN_EMPTY_RUN][:MAX_EMPTY_RUNS]

    for rid, (_, a, b) in enumerate(held_runs):
        lo, hi = a + ROULETTE_SKIP, b - TAIL_GUARD
        if hi <= lo:
            continue
        for k in range(SAMPLES_PER_RUN):
            t = lo + (hi - lo) * k / max(SAMPLES_PER_RUN - 1, 1)
            f = nearest_frame(s, t + VIDEO_OFFSET)
            if f is not None:
                jobs.append((f, rid))
    for _, a, b in empty_runs:
        f = nearest_frame(s, (a + b) / 2 + VIDEO_OFFSET)
        if f is not None:
            jobs.append((f, None))
    jobs.sort()
    return jobs


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

    movs = glob.glob(os.path.join(path, "*.mov"))
    cache = os.path.join(os.path.dirname(__file__), "cache", os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    raw_path = os.path.join(cache, "itembox.raw")
    extract(movs[0], raw_path)

    held = held_series(raw_path)
    s = Session(path)
    jobs = plan(s, held)
    runs = sorted({r for _, r in jobs if r is not None})
    print("%d held runs x %d samples + %d empty samples"
          % (len(runs), SAMPLES_PER_RUN, sum(1 for _, r in jobs if r is None)),
          flush=True)

    mask = None
    empty_val = None
    ref = None
    ref_run = None
    stop = max(f for f, _ in jobs)

    for i, img in s.frames(stop=stop + 1):
        todo = [r for f, r in jobs if f == i]
        if not todo:
            continue
        rid = todo[0]
        if empty_val is None:
            if rid is not None:
                continue                       # need an empty frame first
            empty_val = img.copy()
            mask = np.ones(img.size, dtype=bool)
            continue

        if rid is None:
            mask &= img == empty_val
            ref, ref_run = None, None
            label = "empty"
        else:
            mask &= img != empty_val
            if rid != ref_run:
                ref, ref_run = img.copy(), rid
                label = "held run %d start" % rid
            else:
                mask &= img == ref
                label = "held run %d same " % rid
        print("   f%-5d %-18s %d survivors" % (i, label, int(mask.sum())), flush=True)

    surv = np.nonzero(mask)[0]
    print("\n%d bytes hold one constant value for the whole time the box is up, "
          "and the empty value when it is down:" % surv.size)
    for idx in surv[:40]:
        addr = capfmt.index_to_addr(int(idx), s.regions)
        print("    %s  empty value = %d" % (hex(addr), int(empty_val[idx])))


if __name__ == "__main__":
    main()
