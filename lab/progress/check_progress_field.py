#!/usr/bin/env python3
"""
Offline: test whether +0x0b0 in the player struct really is race progress.

If it is, then ordering racers by it must reproduce ordering by position at
essentially every in-race frame. This measures that agreement instead of
assuming it, and also reports how the field relates to lap and lap_fraction.

Run (no sudo):
  mk/bin/python3 -m lab.progress.check_progress_field
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x140
STRIDE = 0xC4
N_PLAYERS = 12
OFF_POSITION = 0x000
OFF_LAP = 0x006
CANDIDATES = [0x0B0, 0x0B4, 0x0B8, 0x0BC, 0x0C0]
STEP = 25


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def be_f32(img, i):
    return float(np.frombuffer(img[i:i + 4].tobytes(), dtype=">f4")[0])


def main():
    root = RECORDINGS
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        s = Session(d)
        pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)
        agree = {o: [0, 0] for o in CANDIDATES}
        zero_slots = {o: np.zeros(N_PLAYERS, dtype=int) for o in CANDIDATES}
        frames = 0

        for i, img in s.frames(step=STEP):
            if s.index[i]["position"] is None:
                continue
            base = be_u32(img, pi) + PLAYER_DELTA
            bi = capfmt.addr_to_index(base, s.regions)
            if bi is None:
                continue
            pos = [int(img[bi + p * STRIDE + OFF_POSITION]) for p in range(N_PLAYERS)]
            if sorted(pos) != list(range(1, N_PLAYERS + 1)):
                continue
            frames += 1
            for o in CANDIDATES:
                vals = [be_f32(img, bi + p * STRIDE + o) for p in range(N_PLAYERS)]
                for p, v in enumerate(vals):
                    if v == 0.0:
                        zero_slots[o][p] += 1
                # rank by value descending should reproduce position ascending
                order = sorted(range(N_PLAYERS), key=lambda p: -vals[p])
                implied = {p: r + 1 for r, p in enumerate(order)}
                ok = sum(1 for p in range(N_PLAYERS) if implied[p] == pos[p])
                agree[o][0] += ok
                agree[o][1] += N_PLAYERS

        print("=" * 78)
        print("%s  (%d frames)" % (os.path.basename(d), frames))
        for o in CANDIDATES:
            ok, tot = agree[o]
            zs = [p for p in range(N_PLAYERS) if zero_slots[o][p] > frames * 0.9]
            print("  +0x%03x  ranks match position %5.1f%% of the time%s"
                  % (o, 100.0 * ok / max(tot, 1),
                     ("   always-zero slots: %s" % zs) if zs else ""))


if __name__ == "__main__":
    main()
