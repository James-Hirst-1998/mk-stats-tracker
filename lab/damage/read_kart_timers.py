#!/usr/bin/env python3
"""
Offline: map kart objects to racer slots, then read their hit timers.

find_kart_objects.py finds three vtables that each occur exactly twelve times in
the player heap - 0x808cb6b8, 0x808c99bc and 0x808c9d74, at fixed offsets from
one another. Scanning for a vtable locates the twelve kart objects in any race
without a pointer path, which is the same property that made the player array
usable.

Which object belongs to which racer is then settled by correlation: a racer's
stalls and their object's timers have to line up. With that mapping, the timer
fields can finally be named, because different items land on different ones.

Run (no sudo):
  mk/bin/python3 -m lab.damage.read_kart_timers [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.progress.find_hits import (PLAYER_PTR, PLAYER_DELTA, PLAYER_STRIDE, OFF_COMPLETION,
                       OFF_POSITION, N_PLAYERS, be_u32, stalls, race_start)

VTABLE = 0x808CB6B8
HEAP = (0x81100000, 0x81280000)
SPAN = 0x2000              # bytes of each object to examine
STEP = 2
MAX_TIMER = 1500
MIN_FIRES = 2
SLACK = 1.0


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

    mid = len(s) // 2
    img = None
    for i, frame in s.frames(stop=mid + 1):
        img = frame
    words = img.view(">u4")
    occ = np.nonzero(words == np.uint32(VTABLE))[0]
    bases = sorted(a for a in (capfmt.index_to_addr(int(k) * 4, s.regions)
                               for k in occ)
                   if a is not None and HEAP[0] <= a < HEAP[1])
    print("%s: vtable %s found at %d heap addresses"
          % (os.path.basename(dirs[0]), hex(VTABLE), len(bases)), flush=True)
    if len(bases) != N_PLAYERS:
        print("expected %d - not usable here" % N_PLAYERS)
        return
    for k, b in enumerate(bases):
        print("   object[%2d] %s" % (k, hex(b)))

    starts = [capfmt.addr_to_index(b, s.regions) for b in bases]
    t_list, comp_list, blocks = [], [], []
    for i, frame in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(frame, pi) + PLAYER_DELTA, s.regions)
        if bi is None:
            continue
        pos = [int(frame[bi + k * PLAYER_STRIDE + OFF_POSITION])
               for k in range(N_PLAYERS)]
        if sorted(pos) != list(range(1, N_PLAYERS + 1)):
            continue
        t_list.append(s.index[i]["mono"])
        comp_list.append([
            float(np.frombuffer(
                frame[bi + k * PLAYER_STRIDE + OFF_COMPLETION:
                      bi + k * PLAYER_STRIDE + OFF_COMPLETION + 4].tobytes(),
                dtype=">f4")[0]) for k in range(N_PLAYERS)])
        blocks.append(np.stack([
            np.frombuffer(frame[j:j + SPAN].tobytes(), dtype=">u2")
            for j in starts]))
    t = np.array(t_list)
    comp = np.array(comp_list)
    a = np.stack(blocks)                      # (frames, 12 objects, SPAN/2)
    print("\n%d frames tracked, %d u16 per object" % (a.shape[0], a.shape[2]),
          flush=True)

    # Countdown fields, computed per object.
    dt = np.diff(t)
    want = dt * 60.0
    d = a[:-1] - a[1:]
    is_down = (a[:-1] > 0) & (np.abs(d - want[:, None, None]) <= 2.0)
    fires = is_down.sum(axis=0)               # (12, SPAN/2)
    quiet = (a == 0).mean(axis=0)
    good = (fires >= MIN_FIRES) & (quiet >= 0.5) & (a.max(axis=0) <= MAX_TIMER)
    keep = np.nonzero(good.any(axis=0))[0]
    print("%d offsets behave as countdown timers in at least one object"
          % keep.size, flush=True)

    start = race_start(t, comp)
    ev = {k: [(w, dd) for w, dd in stalls(t, comp, k) if w > start + 1.0]
          for k in range(N_PLAYERS)}

    on = (a[:, :, keep] > 0).any(axis=2)      # (frames, 12 objects)
    print("\nmapping object -> slot by stall overlap:")
    table = np.zeros((N_PLAYERS, N_PLAYERS))
    for oi in range(N_PLAYERS):
        col = on[:, oi]
        if not col.any():
            continue
        for k in range(N_PLAYERS):
            if not ev[k]:
                continue
            inside = np.zeros(len(t), dtype=bool)
            for w, dd in ev[k]:
                inside |= (t >= w - SLACK) & (t <= w + dd + SLACK)
            table[oi, k] = (col & inside).sum() / max(col.sum(), 1)
    used = set()
    mapping = {}
    for oi in np.argsort(-table.max(axis=1)):
        k = int(np.argmax(np.where(np.isin(np.arange(N_PLAYERS), list(used)),
                                   -1, table[oi])))
        mapping[int(oi)] = k
        used.add(k)
        print("   object[%2d] -> slot %-2d  (%.0f%% of its timer time is inside "
              "that racer's stalls)" % (oi, k, 100 * table[oi, k]))

    mine = [o for o, k in mapping.items() if k == 0]
    if not mine:
        return
    oi = mine[0]
    print("\ntimers in object[%d] (mapped to you):" % oi)
    for c in keep:
        if not good[oi, c]:
            continue
        col = a[:, oi, c]
        spans, st = [], None
        for j in range(len(col) + 1):
            v = col[j] > 0 if j < len(col) else False
            if v and st is None:
                st = j
            elif not v and st is not None:
                spans.append((t[st] - t[0], t[min(j, len(t) - 1)] - t[st],
                              int(col[st])))
                st = None
        spans = [x for x in spans if x[1] >= 0.3]
        if not spans:
            continue
        print("  +0x%04x  x%-2d  %s"
              % (c * 2, len(spans),
                 "  ".join("%.0fs(%.1fs,v%d)" % x for x in spans[:7])))


if __name__ == "__main__":
    main()
