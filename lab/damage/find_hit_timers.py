#!/usr/bin/env python3
"""
Offline: find the local player's hit timers, and with them the hit type.

The Mushroom Gorge recording was driven clean - no walls, no scraping - so
almost every stall in it is a real event rather than a bad line. That is the
label that was missing when scoring against the frantic recording produced
nothing above the base rate.

Search space is narrowed first by shape, not by the label: a hit timer rests at
zero, jumps when the thing happens, and decrements once per game frame. Only
then is each candidate scored on how well its firing windows line up with the
local player's stalls. Requiring both kills the noise that either test alone
lets through.

Different items should land on different timers (shock, ink, crush, spin), so
the winning fields are reported with the values they take, which is what names
the hit type.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_hit_timers [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.progress.find_hits import (PLAYER_PTR, PLAYER_DELTA, PLAYER_STRIDE, OFF_COMPLETION,
                       OFF_POSITION, N_PLAYERS, be_u32, stalls, race_start)

STEP = 2
MAX_TIMER = 1500
MIN_FIRES = 3
SLOT = 0
SLACK = 1.0            # seconds a timer may lead or lag a stall
TOP = 40


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "mushroom"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])
    pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)

    n2 = capfmt.image_size(s.regions) // 2
    down = np.zeros(n2, dtype=np.uint16)
    zero = np.zeros(n2, dtype=np.uint16)
    huge = np.zeros(n2, dtype=bool)
    nonzero_at = []            # (time, boolean array) sampled sparsely later
    t_list, comp_list = [], []

    prev = prev_t = None
    samples = 0
    frames_kept = []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
        if bi is None:
            continue
        pos = [int(img[bi + k * PLAYER_STRIDE + OFF_POSITION])
               for k in range(N_PLAYERS)]
        if sorted(pos) != list(range(1, N_PLAYERS + 1)):
            continue
        t = s.index[i]["mono"]
        t_list.append(t)
        comp_list.append([
            float(np.frombuffer(
                img[bi + k * PLAYER_STRIDE + OFF_COMPLETION:
                    bi + k * PLAYER_STRIDE + OFF_COMPLETION + 4].tobytes(),
                dtype=">f4")[0]) for k in range(N_PLAYERS)])
        frames_kept.append(i)

        v = img.view(">u2").astype(np.int32)
        if prev is not None:
            want = (t - prev_t) * 60.0
            d = prev - v
            down += (prev > 0) & (v >= 0) & (np.abs(d - want) <= 2.0)
            zero += (v == 0)
            huge |= v > MAX_TIMER
            samples += 1
        prev, prev_t = v, t

    t = np.array(t_list)
    comp = np.array(comp_list)
    print("%s: %d samples" % (os.path.basename(dirs[0]), samples), flush=True)

    start = race_start(t, comp)
    ev = [(w, d) for w, d in stalls(t, comp, SLOT) if w > start + 1.0]
    print("slot %d: %d stalls after the start" % (SLOT, len(ev)), flush=True)
    if len(ev) < 4:
        print("not enough stalls")
        return

    ok = (~huge) & (down >= MIN_FIRES) & (zero >= samples * 0.5)
    idx = np.nonzero(ok)[0]
    print("%d u16 fields have the countdown shape" % idx.size, flush=True)
    if idx.size == 0:
        return

    # Second pass: track just those fields, then score against the stalls.
    track = []
    for i, img in s.frames():
        if i not in set(frames_kept):
            continue
        track.append(img.view(">u2")[idx].copy())
    a = np.stack(track)
    inside = np.zeros(len(t), dtype=bool)
    for w, d in ev:
        inside |= (t >= w - SLACK) & (t <= w + d + SLACK)

    on = a > 0
    covered = np.zeros(idx.size)
    precise = np.zeros(idx.size)
    for c in range(idx.size):
        col = on[:, c]
        if not col.any():
            continue
        precise[c] = (col & inside).sum() / col.sum()
        hit_ev = sum(1 for w, d in ev
                     if col[(t >= w - SLACK) & (t <= w + d + SLACK)].any())
        covered[c] = hit_ev / len(ev)
    score = precise * covered

    order = np.argsort(-score)[:TOP]
    print("\n%-12s %-9s %-9s %s" % ("address", "precision", "recall", "values"))
    for c in order:
        if score[c] <= 0:
            break
        vals = sorted(set(int(v) for v in np.unique(a[:, c])) - {0})
        print("%-12s %8.0f%% %8.0f%%   %s"
              % (hex(capfmt.index_to_addr(int(idx[c]) * 2, s.regions)),
                 100 * precise[c], 100 * covered[c], vals[:10]))


if __name__ == "__main__":
    main()
