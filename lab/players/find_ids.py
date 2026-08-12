#!/usr/bin/env python3
"""Offline: find the per-player id columns in RaceConfig.

`find_config_array.py` pins the array down: the starting grid appears at
`*(0x809BD728) + 0x108 + i*0xF0`, and again 0xBF0 later, which is the second of
RaceConfig's scenarios. Working out where each struct formally begins is not
needed - what matters is the address of a field, and that is `C + i*0xF0` for
some C. So scan every C.

A character or vehicle id looks like: one byte, fixed for the whole race,
mostly different between racers, and small.

Run (no sudo):
  mk/bin/python3 -m lab.players.find_ids [recording-substring]
"""

import glob
import os
import sys
from collections import defaultdict

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

RACE_CONFIG = 0x809BD728
STRIDE = 0xF0
N_PLAYERS = 12
SEARCH = 0x300              # candidate column starts, before the array repeats
SAMPLES = 16
GRID_AT = 0x108             # where the starting grid was found


def columns(s, frames):
    """{offset: [value per slot]} for columns fixed across the whole race."""
    cfg = s.u32(frames[0], RACE_CONFIG)
    start = capfmt.addr_to_index(cfg, s.regions)
    if start is None:
        return None, None
    fixed = {}
    first = None
    for i in frames:
        if s.u32(i, RACE_CONFIG) != cfg:
            return cfg, {}
        buf = s.frame(i)[start:start + SEARCH + N_PLAYERS * STRIDE]
        cur = {off: tuple(int(buf[off + k * STRIDE]) for k in range(N_PLAYERS))
               for off in range(SEARCH)}
        if first is None:
            first = cur
        else:
            for off in list(first):
                if cur[off] != first[off]:
                    del first[off]
    for off, col in first.items():
        if max(col) <= 0x40 and len(set(col)) >= 6:
            fixed[off] = list(col)
    return cfg, fixed


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    everywhere = defaultdict(list)
    for d in dirs:
        s = Session(d)
        frames = [i for i in range(len(s)) if s.index[i]["position"] is not None]
        if not frames:
            continue
        frames = frames[::max(1, len(frames) // SAMPLES)]
        cfg, fixed = columns(s, frames)
        if not fixed:
            continue
        print("=== %s   config 0x%08x" % (os.path.basename(d), cfg))
        for off in sorted(fixed):
            col = fixed[off]
            everywhere[off].append(col)
            print("    +0x%03x  %s  %s"
                  % (off, " ".join("%3d" % v for v in col),
                     "grid" if off in (GRID_AT, GRID_AT + 1) else
                     ("all different" if len(set(col)) == N_PLAYERS else "")))
        print()

    print("columns present in all %d recordings, with slot 0's value each time:"
          % len(dirs))
    for off in sorted(everywhere):
        cols = everywhere[off]
        if len(cols) != len(dirs):
            continue
        print("  +0x%03x  slot 0: %s   distinct per race: %s"
              % (off, " ".join("%3d" % c[0] for c in cols),
                 " ".join("%2d" % len(set(c)) for c in cols)))


if __name__ == "__main__":
    main()
