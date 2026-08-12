#!/usr/bin/env python3
"""
Offline: find a stable path to the race clock.

find_timer.py showed two families of 60 Hz counters: one at static addresses in
0x8038-0x8042 whose value covers the whole Dolphin session, and one in the heap
whose value matches the race length. The second is the race clock, but it moves
between races, so it needs a path.

This looks for the clock as a fixed delta from the player array - the two are
almost certainly owned by the same manager - and intersects that delta across
every recording. Recordings from separate launches make the result mean
something.

Run (no sudo):
  mk/bin/python3 -m lab.timer.find_timer_path
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x12C
STEP = 4
TOL = 1.5
MIN_STEADY = 0.80
SEARCH = 0x40000          # how far either side of the player array to look


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def candidates(s):
    """(delta_from_player_base, final_value) for heap 60 Hz counters."""
    race = [i for i, e in enumerate(s.index) if e["position"] is not None]
    lo, hi = race[0], race[-1]
    base = None
    prev = prev_t = None
    steady = nz = None
    n_samp = 0
    for i, img in s.frames(start=lo, stop=hi + 1, step=STEP):
        if base is None:
            base = be_u32(img, capfmt.addr_to_index(PLAYER_PTR, s.regions)) + PLAYER_DELTA
            bi = capfmt.addr_to_index(base, s.regions)
            lo_i = max(0, (bi - SEARCH) // 4)
            hi_i = min(img.size // 4, (bi + SEARCH) // 4)
        v = img.view(">u4")[lo_i:hi_i].astype(np.int64)
        t = s.index[i]["mono"]
        if prev is not None:
            want = (t - prev_t) * 60.0
            d = v - prev
            if steady is None:
                steady = np.zeros(v.size, dtype=np.uint16)
                nz = np.zeros(v.size, dtype=np.uint16)
            steady += (np.abs(d - want) <= TOL)
            nz += (d != 0)
            n_samp += 1
        prev, prev_t = v, t
    if steady is None:
        return {}, base
    ok = (steady >= n_samp * MIN_STEADY) & (nz >= n_samp * 0.9)
    out = {}
    bi = capfmt.addr_to_index(base, s.regions)
    for k in np.nonzero(ok)[0]:
        idx = (lo_i + int(k)) * 4
        out[idx - bi] = int(prev[k])
    return out, base


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    per = {}
    for d in dirs:
        s = Session(d)
        c, base = candidates(s)
        per[os.path.basename(d)] = c
        print("%-42s base=%s  %d clock candidates nearby"
              % (os.path.basename(d), hex(base or 0), len(c)), flush=True)

    common = None
    for c in per.values():
        keys = set(c)
        common = keys if common is None else (common & keys)
    common = sorted(common or [])
    print("\n%d deltas from the player base hold a 60 Hz clock in EVERY recording"
          % len(common))
    for delta in common[:40]:
        vals = ["%.1fs" % (per[n][delta] / 60.0) for n in per]
        print("   player_base %s 0x%x   race lengths %s"
              % ("+" if delta >= 0 else "-", abs(delta), vals))


if __name__ == "__main__":
    main()
