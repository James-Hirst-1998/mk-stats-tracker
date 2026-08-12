#!/usr/bin/env python3
"""
Offline: validate race progress, and fix the player-array base while at it.

find_progress.py found 12 monotone floats at stride 0xc4 running from
u32(0x809bd730) + 0x12c - one struct-width EARLIER than the base this repo has
been using. So the real array starts 0x14 lower than assumed and the layout is:

    +0x000 race completion (float, lap + fraction of lap)
    +0x004 second monotone float
    +0x014 position (u8, 1..12)      <- previously called +0x000
    +0x01a lap (u8)                  <- previously called +0x006

That off-by-one struct is why check_progress_field.py measured chance-level
agreement: reading +0x0b0 from the old base is +0x000 of the NEXT racer, so it
was ranking everyone by their neighbour's progress.

This validates the corrected layout on every recording: ordering by progress
must reproduce position, and progress must sit inside [lap, lap+1).

Run (no sudo):
  mk/bin/python3 -m analysis.validate_progress
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x12C            # was 0x140
STRIDE = 0xC4
N_PLAYERS = 12
OFF_PROGRESS = 0x000
OFF_PROGRESS_ALT = 0x004
OFF_POSITION = 0x014
OFF_LAP = 0x01A
STEP = 20


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]

    for d in dirs:
        s = Session(d)
        pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)
        stats = {o: dict(rank=0, rank_t=0, grid=0, grid_t=0, fit=0, fit_t=0)
                 for o in (OFF_PROGRESS, OFF_PROGRESS_ALT)}
        frames = 0

        for i, img in s.frames(step=STEP):
            if s.index[i]["position"] is None:
                continue
            bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
            if bi is None:
                continue
            pos = [int(img[bi + p * STRIDE + OFF_POSITION]) for p in range(N_PLAYERS)]
            if sorted(pos) != list(range(1, N_PLAYERS + 1)):
                continue
            lap = [int(img[bi + p * STRIDE + OFF_LAP]) for p in range(N_PLAYERS)]
            frames += 1

            for o in (OFF_PROGRESS, OFF_PROGRESS_ALT):
                vals = [float(np.frombuffer(
                    img[bi + p * STRIDE + o:bi + p * STRIDE + o + 4].tobytes(),
                    dtype=">f4")[0]) for p in range(N_PLAYERS)]
                order = sorted(range(N_PLAYERS), key=lambda p: -vals[p])
                implied = {p: r + 1 for r, p in enumerate(order)}
                ok = sum(1 for p in range(N_PLAYERS) if implied[p] == pos[p])
                st = stats[o]
                st["rank"] += ok
                st["rank_t"] += N_PLAYERS
                st["grid"] += 1 if ok == N_PLAYERS else 0
                st["grid_t"] += 1
                for p in range(N_PLAYERS):
                    if lap[p]:
                        st["fit_t"] += 1
                        st["fit"] += 1 if lap[p] <= vals[p] < lap[p] + 1.001 else 0

        print("=" * 78)
        print("%s  (%d frames)" % (os.path.basename(d), frames))
        for o in (OFF_PROGRESS, OFF_PROGRESS_ALT):
            st = stats[o]
            print("  +0x%03x  per-racer rank %6.2f%%   whole grid exact %6.2f%%   "
                  "inside [lap,lap+1) %6.2f%%"
                  % (o,
                     100.0 * st["rank"] / max(st["rank_t"], 1),
                     100.0 * st["grid"] / max(st["grid_t"], 1),
                     100.0 * st["fit"] / max(st["fit_t"], 1)))


if __name__ == "__main__":
    main()
