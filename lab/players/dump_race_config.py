#!/usr/bin/env python3
"""Offline: mine the per-player config struct for character, vehicle and CPU.

The lead is already in code disassembled for the item work. Inside the
collision routine at 0x80572614:

    lwz  r5,-10456(r25)     r25 = 0x809C0000, so r5 = *(0x809BD728)
    lwz  r0,2960(r5)        r5 + 0xB90, bit 0x2 tested -> a settings flag
    mulli r0,r23,240        owner * 0xF0, so 12 players at stride 0xF0
    lwz  r4,244(r4)         + 0xF4
    cmpwi r4,2              compared between the owner and the victim, and
                            skipped when either reads 2 - a team check

So there is a 12-entry array of 0xF0-byte structs hanging off a static in MEM2,
which is where a character id would live. The array does not start at the
pointer: reading `cfg + k*0xF0 + 0x18` gives 12, 11, 10 ... for k = 1 upward,
which is the starting grid, so player i sits at `cfg + 0xF0 + i*0xF0` and the
first 0xF0 bytes are settings. That also puts the team field the code reads at
struct `+0x04`.

Rather than take offsets from a decomp, this dumps every byte of the struct and
keeps the ones that behave like a setting: fixed for the whole race, and not
identical for all twelve racers.

Run (no sudo):
  mk/bin/python3 -m lab.players.dump_race_config [recording-substring]
"""

import glob
import os
import sys

from mkw.capture.session import Session, RECORDINGS

RACE_CONFIG = 0x809BD728
PLAYERS = 0xF0              # first 0xF0 bytes are settings, players follow
STRIDE = 0xF0
N_PLAYERS = 12
SAMPLES = 24


def captured(a):
    """RaceConfig lives in MEM2, which the recorder covers to 0x91800000."""
    return a is not None and (0x80000000 <= a < 0x81800000
                              or 0x90000000 <= a < 0x91800000)


def settings(s, frames):
    """[(struct offset, [value per slot])] for every byte that looks like one."""
    base = s.u32(frames[0], RACE_CONFIG)
    if not captured(base):
        return None, None
    seen = {}
    for i in frames:
        if s.u32(i, RACE_CONFIG) != base:
            continue
        for k in range(N_PLAYERS):
            p = base + PLAYERS + k * STRIDE
            for off in range(STRIDE):
                seen.setdefault((off, k), set()).add(s.u8(i, p + off))
    out = []
    for off in range(STRIDE):
        vals = [seen.get((off, k), {None}) for k in range(N_PLAYERS)]
        if any(len(v) != 1 for v in vals):
            continue                        # moved during the race
        vals = [next(iter(v)) for v in vals]
        if len(set(vals)) == 1 or max(vals) > 0x40:
            continue                        # same for all, or too big for an id
        out.append((off, vals))
    return base, out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    for d in dirs:
        s = Session(d)
        frames = [i for i in range(0, len(s), max(1, len(s) // SAMPLES))
                  if s.index[i]["position"] is not None]
        if not frames:
            continue
        base, rows = settings(s, frames)
        if rows is None:
            print("%s: no config pointer" % os.path.basename(d))
            continue
        print("=== %s   config 0x%08x" % (os.path.basename(d), base))
        print("%-8s %s   %s" % ("offset", "value per slot 0..11", "note"))
        for off, vals in rows:
            note = ""
            if sorted(vals) == list(range(1, N_PLAYERS + 1)):
                note = "permutation of 1..12"
            elif len(set(vals)) == N_PLAYERS:
                note = "all different"
            elif len(set(vals)) == 2 and vals.count(vals[0]) == 1:
                note = "slot 0 alone"
            print("+0x%03x   %s   %s"
                  % (off, " ".join("%3d" % v for v in vals), note))
        print()


if __name__ == "__main__":
    main()
