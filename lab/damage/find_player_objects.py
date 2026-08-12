#!/usr/bin/env python3
"""
Offline: find the twelve player objects and map them to racer slots.

find_countdown_timers.py shows twelve separately-allocated objects in the
0x8113-0x811f heap, each carrying the same countdown fields. They are not at a
constant stride, so something holds an array of pointers to them. Find that
array, then work out which pointer belongs to which racer slot.

The slot mapping comes for free from data already proven: whichever object's
long ~7.5s timer fires exactly when that slot is carrying a Star or a Mega
Mushroom is that slot's object. That names the field and the mapping in one go.

Run (no sudo):
  mk/bin/python3 -m lab.damage.find_player_objects [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

HEAP_LO = 0x81100000
HEAP_HI = 0x81280000
N_PLAYERS = 12

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
ITEM_STRIDE = 0x248
OFF_HELD = 0x01C
STAR, MEGA = 9, 11
LONG_TIMER = 0x7A
STEP = 2


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def pointer_arrays(img, regions):
    """Aligned runs of >=12 words that all point into the player heap."""
    words = img.view(">u4")
    good = (words >= HEAP_LO) & (words < HEAP_HI)
    out = []
    i = 0
    n = good.size
    while i < n:
        if not good[i]:
            i += 1
            continue
        j = i
        while j < n and good[j]:
            j += 1
        if j - i >= N_PLAYERS:
            out.append((capfmt.index_to_addr(i * 4, regions), j - i,
                        [int(words[k]) for k in range(i, min(j, i + 16))]))
        i = j
    return out


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
    mid = len(s) // 2
    img = None
    for i, frame in s.frames(stop=mid + 1):
        img = frame

    arrays = pointer_arrays(img, s.regions)
    print("%d aligned runs of >=12 player-heap pointers" % len(arrays))
    for addr, ln, vals in arrays[:12]:
        gaps = sorted({vals[k + 1] - vals[k] for k in range(len(vals) - 1)})
        print("  at %s  len %-3d  first %s  distinct gaps %d"
              % (hex(addr), ln, hex(vals[0]), len(gaps)))
    if not arrays:
        print("none - the objects are reached some other way")
        return

    # Take the first run of exactly 12 distinct ascending pointers.
    best = None
    for addr, ln, vals in arrays:
        v = vals[:N_PLAYERS]
        if len(set(v)) == N_PLAYERS and all(
                v[k] < v[k + 1] for k in range(N_PLAYERS - 1)):
            best = (addr, v)
            break
    if best is None:
        best = (arrays[0][0], arrays[0][2][:N_PLAYERS])
    addr, objs = best
    print("\nusing the array at %s" % hex(addr))
    for k, o in enumerate(objs):
        print("   [%2d] %s" % (k, hex(o)))

    # Now map objects to slots via Star / Mega.
    ii = capfmt.addr_to_index(ITEM_PTR, s.regions)
    tidx = [capfmt.addr_to_index(o + LONG_TIMER, s.regions) for o in objs]
    held = []
    timers = []
    for i, frame in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        ib = capfmt.addr_to_index(be_u32(frame, ii) + ITEM_DELTA, s.regions)
        if ib is None:
            continue
        held.append([int(frame[ib + k * ITEM_STRIDE + OFF_HELD])
                     for k in range(N_PLAYERS)])
        timers.append([
            int(np.frombuffer(frame[j:j + 2].tobytes(), dtype=">u2")[0])
            if j is not None else 0 for j in tidx])
    held = np.array(held)
    timers = np.array(timers)

    print("\nmatching object -> slot on Star/Mega (+0x%02x running vs holding):"
          % LONG_TIMER)
    score = np.zeros((N_PLAYERS, N_PLAYERS))
    for oi in range(N_PLAYERS):
        run = timers[:, oi] > 0
        if not run.any():
            continue
        for sl in range(N_PLAYERS):
            boost = np.isin(held[:, sl], (STAR, MEGA))
            # the timer starts as the item is used, so allow it to follow
            shifted = boost | np.roll(boost, 20) | np.roll(boost, 40)
            score[oi, sl] = (run & shifted).sum() / max(run.sum(), 1)
    for oi in range(N_PLAYERS):
        sl = int(np.argmax(score[oi]))
        print("   object[%2d] %s -> slot %-2d  (%.0f%% overlap)"
              % (oi, hex(objs[oi]), sl, 100 * score[oi, sl]))


if __name__ == "__main__":
    main()
