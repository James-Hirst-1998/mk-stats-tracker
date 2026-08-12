#!/usr/bin/env python3
"""
Offline: find the per-racer damage / hit state.

find_hits.py already detects hits without any new field: a racer who is struck
stops advancing, so their raceCompletion rate collapses. Three predicted hits
were checked against the video and all three are real - a lightning bolt
flattening the kart, a white-out, and a spin-out with stars.

That gives labelled intervals for free, for all twelve racers, which is exactly
what a search needs. Whatever holds the hit state must be non-resting during a
racer's stalls and resting the rest of the time. Score every byte on that, then
require the winner to repeat at a constant stride across racers - the same
constraint that identified the player array.

James does not need to know who threw it, only that a hit happened and ideally
what kind, so a state enum is a better target than an attacker id.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_damage_state [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.progress.find_hits import (PLAYER_PTR, PLAYER_DELTA, PLAYER_STRIDE, OFF_COMPLETION,
                       OFF_POSITION, N_PLAYERS, be_u32, stalls)

GUARD = 0.5           # seconds around a stall edge to ignore
TOP = 40
SLOT = 0


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
    pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)

    # Pass 1: completion for the chosen slot, to locate its stalls.
    t = np.full(len(s), np.nan)
    comp = np.full((len(s), N_PLAYERS), np.nan)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
        if bi is None:
            continue
        p = [int(img[bi + k * PLAYER_STRIDE + OFF_POSITION])
             for k in range(N_PLAYERS)]
        if sorted(p) != list(range(1, N_PLAYERS + 1)):
            continue
        t[i] = s.index[i]["mono"]
        for k in range(N_PLAYERS):
            o = bi + k * PLAYER_STRIDE + OFF_COMPLETION
            comp[i, k] = float(np.frombuffer(img[o:o + 4].tobytes(),
                                             dtype=">f4")[0])

    ev = stalls(t, comp, SLOT)
    print("slot %d: %d stalls" % (SLOT, len(ev)), flush=True)
    if len(ev) < 5:
        print("not enough stalls to score against")
        return

    label = {}
    for i in range(len(s)):
        if np.isnan(t[i]):
            continue
        near = False
        hit = False
        for when, dur in ev:
            if when - GUARD <= t[i] <= when + dur + GUARD:
                near = True
            if when <= t[i] <= when + dur:
                hit = True
        if hit:
            label[i] = True
        elif not near:
            label[i] = False
    n_hit = sum(1 for v in label.values() if v)
    print("labelled %d hit frames, %d clean frames"
          % (n_hit, len(label) - n_hit), flush=True)

    n = capfmt.image_size(s.regions)
    rest = None
    agree = np.zeros(n, dtype=np.uint16)
    done = 0
    for i, img in s.frames():
        st = label.get(i)
        if st is None:
            continue
        if rest is None:
            if st:
                continue
            rest = img.copy()
        ne = img != rest
        agree += ne if st else ~ne
        done += 1

    frac = agree.astype(np.float32) / done
    order = np.argsort(-frac)[:TOP]
    print("\n%-12s %-8s %s" % ("address", "agree", "resting value"))
    for j in order:
        print("%-12s %6.1f%%   %d"
              % (hex(capfmt.index_to_addr(int(j), s.regions)),
                 100 * frac[j], int(rest[j])))

    good = set(int(j) for j in order if frac[j] >= 0.9)
    print("\nruns of >=8 high scorers at a constant stride:")
    seen = False
    for a in sorted(good):
        for stride in range(4, 0x4000, 4):
            k = 1
            while a + k * stride in good and k < N_PLAYERS:
                k += 1
            if k >= 8:
                print("   x%-3d stride 0x%-5x base %s"
                      % (k, stride, hex(capfmt.index_to_addr(a, s.regions))))
                seen = True
    if not seen:
        print("   none - the state is probably per-racer somewhere else, or the "
              "top scorers are local-player-only")


if __name__ == "__main__":
    main()
