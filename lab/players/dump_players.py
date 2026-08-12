#!/usr/bin/env python3
"""Offline: read the per-player config struct, now that the base is known.

`find_config_readers.py` settles the layout from the game's own code, at
0x8052880c:

    lwz  r3,-10456(r3)      cfg = *(0x809BD728)
    lbz  r4,36(r3)          cfg + 0x24 = how many players
    addi r6,r3,40           cfg + 0x28 = the player array
    mulli r0,r0,240         stride 0xF0
    lwz  r3,16(r3)          player + 0x10, compared against 0 and 2

That places the grid position found earlier at `cfg + 0x108` at struct `+0xE0`,
and the team field the collision code reads at `cfg + i*0xF0 + 0xF4` at struct
`+0xCC`. Twelve players from 0x28 end at 0xB68, just before the settings word
at 0xB90 - so it all fits.

The two id columns are then struct `+0x0B` and `+0x0F`, which are the low bytes
of u32s at `+0x08` and `+0x0C`.

Run (no sudo):
  mk/bin/python3 -m lab.players.dump_players [recording-substring]
"""

import glob
import os
import sys

from mkw.capture.session import Session, RECORDINGS

RACE_CONFIG = 0x809BD728
OFF_COUNT = 0x24
OFF_PLAYERS = 0x28
STRIDE = 0xF0
N_PLAYERS = 12


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
        i = frames[len(frames) // 2]
        cfg = s.u32(i, RACE_CONFIG)
        print("=== %s   config 0x%08x, %d players"
              % (os.path.basename(d), cfg, s.u8(i, cfg + OFF_COUNT)))
        print("  %-4s %-10s %-10s %-10s %-10s %-6s %-6s %s"
              % ("slot", "+0x00", "+0x04", "+0x08", "+0x0c", "+0x10",
                 "+0xcc", "+0xe0"))
        for k in range(N_PLAYERS):
            p = cfg + OFF_PLAYERS + k * STRIDE
            print("  %-4d %-10d %-10d %-10d %-10d %-6d %-6d %d"
                  % (k, s.u32(i, p + 0x00), s.u32(i, p + 0x04),
                     s.u32(i, p + 0x08), s.u32(i, p + 0x0C),
                     s.u32(i, p + 0x10), s.u32(i, p + 0xCC),
                     s.u8(i, p + 0xE0)))
        print()


if __name__ == "__main__":
    main()
