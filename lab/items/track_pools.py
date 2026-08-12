#!/usr/bin/env python3
"""Offline: track every item object in the world, and name the type enum.

Layout established by `probe_pool_fields.py` and `probe_live_flag.py`:

    entry = ItemDirector + 0x48 + type * 0x24
      +0x00  type index (equals its own position in the table)
      +0x04  -> array of pointers to that type's objects
      +0x08  capacity
      +0x10  how many are live right now
    live objects are array[0 .. live-1], densely packed
    object +0x6C  the racer who owns it

Each pool slot is a fixed address for the whole race, so an address is a stable
identity and spawn/despawn are just set membership. The old read of
`ItemDirector + 0x264` saw at most 3 objects because that is a per-kart
collision buffer, not the world.

Run (no sudo):
  mk/bin/python3 -m lab.items.track_pools [recording-substring]
"""

import glob
import os
import sys
from collections import Counter, defaultdict

import numpy as np

from mkw.capture.session import Session, RECORDINGS
from analysis.cross_check_damage import read_held, uses, ITEM_NAMES

ITEM_DIRECTOR = 0x809C3618
TABLE = 0x48
STRIDE = 0x24
OFF_TYPE = 0x00
OFF_ARRAY = 0x04
OFF_CAP = 0x08
OFF_LIVE = 0x10
OFF_OWNER = 0x6C
N_TYPES = 15
SPAWN_WINDOW = 1.0          # seconds after a use for the object to appear


def is_heap(a):
    return a is not None and 0x80900000 <= a < 0x81800000


def live_objects(s, i):
    """{object address: (type, owner)} for one frame, or None."""
    director = s.u32(i, ITEM_DIRECTOR)
    if not is_heap(director):
        return None
    out = {}
    for t in range(N_TYPES):
        e = director + TABLE + t * STRIDE
        if s.u32(i, e + OFF_TYPE) != t:
            return None
        arr = s.u32(i, e + OFF_ARRAY)
        cap = s.u32(i, e + OFF_CAP)
        live = s.u32(i, e + OFF_LIVE)
        if not is_heap(arr) or not cap or cap > 64:
            return None
        if live is None or live > cap:
            return None
        for k in range(live):
            obj = s.u32(i, arr + k * 4)
            if is_heap(obj):
                out[obj] = (t, s.u8(i, obj + OFF_OWNER))
    return out


def track(s):
    """(t, [{addr: (type, owner)}]) per frame."""
    n = len(s)
    t = np.full(n, np.nan)
    objs = [None] * n
    for i, _ in s.frames():
        if s.index[i]["position"] is None:
            continue
        t[i] = s.index[i]["mono"]
        objs[i] = live_objects(s, i)
    return t, objs


def transitions(t, objs):
    """(spawns, despawns) as (time, addr, type, owner)."""
    spawns, despawns = [], []
    prev = {}
    for i, cur in enumerate(objs):
        if cur is None:
            continue
        for a, v in cur.items():
            if a not in prev:
                spawns.append((float(t[i]), a, v[0], v[1]))
        for a, v in prev.items():
            if a not in cur:
                despawns.append((float(t[i]), a, v[0], v[1]))
        prev = cur
    return spawns, despawns


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    votes = defaultdict(Counter)
    for d in dirs:
        s = Session(d)
        t, objs = track(s)
        if all(o is None for o in objs):
            print("%-46s no pool table" % os.path.basename(d)[:46])
            continue
        used = uses(t, read_held(s))
        spawns, despawns = transitions(t, objs)
        peak = max(len(o) for o in objs if o is not None)
        for when, addr, typ, owner in spawns:
            cand = [u for u in used if u[1] == owner
                    and 0.0 <= when - u[0] <= SPAWN_WINDOW]
            if len(cand) == 1:
                votes[typ][cand[0][2]] += 1
        print("%-46s %4d spawns, %4d despawns, %3d item uses, peak %d live"
              % (os.path.basename(d)[:46], len(spawns), len(despawns),
                 len(used), peak))

    print("\nobject type -> the held item that produced it")
    print("%-6s %-24s %s" % ("type", "best match", "votes"))
    for typ in sorted(votes):
        c = votes[typ]
        best, n = c.most_common(1)[0]
        print("%-6d %-24s %d/%d   %s"
              % (typ, ITEM_NAMES.get(best, best), n, sum(c.values()),
                 ", ".join("%s x%d" % (ITEM_NAMES.get(k, k), v)
                           for k, v in c.most_common(4))))


if __name__ == "__main__":
    main()
