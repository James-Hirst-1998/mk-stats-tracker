#!/usr/bin/env python3
"""Offline: locate the per-player config array without assuming its phase.

`dump_race_config.py` guessed the array starts one 0xF0 stride into the struct
`*(0x809BD728)` points at. The grid-position column came out as a clean 12..1,
but slot 11 read as junk in almost every other field, which means the phase is
wrong somewhere. Rather than shift it by hand, find it.

Two shapes give the phase away, and both are checked against the frame-0
positions from `RaceinfoPlayer`, which is already proven:

  - the starting grid: twelve bytes at stride 0xF0 that are a permutation
    of 1..12
  - a per-player id: twelve bytes at stride 0xF0 that are all distinct and
    small

Every offset whose twelve bytes form a permutation is reported, so the array
base falls out of where those offsets cluster.

Run (no sudo):
  mk/bin/python3 -m lab.players.find_config_array [recording-substring]
"""

import glob
import os
import sys

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

RACE_CONFIG = 0x809BD728
STRIDE = 0xF0
N_PLAYERS = 12
SEARCH = 0x1400             # bytes after the pointer to look through
WANT = set(range(1, N_PLAYERS + 1))


def grid_at_frame_zero(s):
    """Starting positions per slot, from the racer struct already established."""
    for i in range(len(s)):
        if s.index[i]["position"] is None:
            continue
        base = s.u32(i, 0x809BD730)
        if base is None:
            continue
        base += 0x120
        got = [s.u8(i, base + k * 0xC4 + 0x20) for k in range(N_PLAYERS)]
        if got and sorted(got) == sorted(WANT):
            return got
    return None


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    for d in dirs:
        s = Session(d)
        frames = [i for i in range(len(s)) if s.index[i]["position"] is not None]
        if not frames:
            continue
        mid = frames[len(frames) // 2]
        cfg = s.u32(mid, RACE_CONFIG)
        grid = grid_at_frame_zero(s)
        print("=== %s   config 0x%08x" % (os.path.basename(d), cfg))
        print("    grid at frame 0, by slot: %s" % grid)

        img = s.frame(mid)
        start = capfmt.addr_to_index(cfg, s.regions)
        if start is None:
            print("    config pointer is outside the recorded regions\n")
            continue
        buf = img[start:start + SEARCH + N_PLAYERS * STRIDE]

        hits = []
        for off in range(SEARCH):
            col = [int(buf[off + k * STRIDE]) for k in range(N_PLAYERS)]
            if set(col) == WANT:
                hits.append((off, col))
        for off, col in hits:
            note = "MATCHES frame-0 grid" if grid == col else ""
            print("    +0x%04x  %s  %s"
                  % (off, " ".join("%3d" % v for v in col), note))
        if not hits:
            print("    no permutation column found")
        print()


if __name__ == "__main__":
    main()
