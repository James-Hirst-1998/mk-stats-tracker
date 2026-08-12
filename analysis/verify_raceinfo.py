#!/usr/bin/env python3
"""
Offline: check the player array against the public RaceinfoPlayer layout.

SeekyCt's mkw-structures documents RaceinfoPlayer as:

    0x0c raceCompletion  float      0x20 position     u8
    0x10 raceCompletionMax float    0x24 currentLap   u16
    0x18 nextCheckpointLapCompletion 0x26 maxLap      u8
    0x2c frameCounter    u32        0x30 framesInFirst u32
    0x38 lapFinishTimes  Timer*     0x3c raceFinishTime Timer*
    Timer = {0x0 u16 minutes, 0x2 u8 seconds, 0xa u16 milliseconds}, size 0xc

That is a candidate, not evidence. It lines up with what was found here if the
array actually starts 0xc earlier than the base in use - this repo's +0x000
progress is the doc's 0x0c, +0x014 position is the doc's 0x20, and so on.

This tests that reading: the two Timer pointers must be valid MEM1 addresses,
and the lap times behind them must match the splits measured independently from
capture timestamps.

Run (no sudo):
  mk/bin/python3 -m analysis.verify_raceinfo [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
STRUCT_DELTA = 0x120           # was 0x12c; doc layout says the struct starts 0xc earlier
STRIDE = 0xC4
N_PLAYERS = 12

OFF_COMPLETION = 0x0C
OFF_POSITION = 0x20
OFF_CURRENT_LAP = 0x24
OFF_MAX_LAP = 0x26
OFF_FRAME_COUNTER = 0x2C
OFF_FRAMES_IN_FIRST = 0x30
OFF_LAP_TIMES = 0x38
OFF_FINISH_TIME = 0x3C
TIMER_SIZE = 0xC


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def be_u16(img, i):
    return int(np.frombuffer(img[i:i + 2].tobytes(), dtype=">u2")[0])


def timer(img, regions, addr):
    i = capfmt.addr_to_index(addr, regions)
    if i is None:
        return None
    mins = be_u16(img, i)
    secs = int(img[i + 2])
    ms = be_u16(img, i + 0xA)
    if mins > 20 or secs > 59 or ms > 999:
        return None
    return mins * 60 + secs + ms / 1000.0


def fmt(t):
    return "-" if t is None else "%d:%06.3f" % (int(t // 60), t % 60)


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in dirs if which in d]

    for d in dirs:
        s = Session(d)
        pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)
        last = None
        for i, img in s.frames():
            if s.index[i]["position"] is not None:
                last = i
        if last is None:
            continue
        img = s.frame(last)
        base = be_u32(img, pi) + STRUCT_DELTA
        bi = capfmt.addr_to_index(base, s.regions)
        print("=" * 78)
        print("%s   struct base %s" % (os.path.basename(d), hex(base)))
        if bi is None:
            print("  base outside recorded regions")
            continue

        for p in range(N_PLAYERS):
            o = bi + p * STRIDE
            pos = int(img[o + OFF_POSITION])
            lap = be_u16(img, o + OFF_CURRENT_LAP)
            mx = int(img[o + OFF_MAX_LAP])
            comp = float(np.frombuffer(
                img[o + OFF_COMPLETION:o + OFF_COMPLETION + 4].tobytes(),
                dtype=">f4")[0])
            fc = be_u32(img, o + OFF_FRAME_COUNTER)
            fif = be_u32(img, o + OFF_FRAMES_IN_FIRST)
            lt_ptr = be_u32(img, o + OFF_LAP_TIMES)
            ft_ptr = be_u32(img, o + OFF_FINISH_TIME)
            laps = []
            if 0x80000000 <= lt_ptr < 0x81800000:
                for k in range(3):
                    laps.append(timer(img, s.regions, lt_ptr + k * TIMER_SIZE))
            finish = (timer(img, s.regions, ft_ptr)
                      if 0x80000000 <= ft_ptr < 0x81800000 else None)
            print("  P%-2d slot %-2d lap %d/%d comp %6.3f  clock %6.1fs  "
                  "lead %5.1fs  laps %s  finish %s"
                  % (pos, p, lap, mx, comp, fc / 60.0, fif / 60.0,
                     " ".join(fmt(x) for x in laps), fmt(finish)))


if __name__ == "__main__":
    main()
