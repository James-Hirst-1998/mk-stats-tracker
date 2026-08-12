#!/usr/bin/env python3
"""SUPERSEDED - kept as the record of a wrong read. Use `name_hit_items.py`.

`ItemDirector + 0x264` is not a list of the items in the world. Disassembling
`0x80799CAC` shows it packing the objects near ONE kart into that buffer,
capped at 16, for the collision loop below to consume. That is why this script
never saw more than three items at once. The real per-type pools are at
`ItemDirector + 0x48`, and the type-enum votes below (red 5/6, banana 25/33)
come out unanimous when taken from those instead.

Offline: read the live item objects, and learn what their type index means.

The damage field says "knockback", which covers a green shell, a red shell and
a fake item box alike - the game never tells the victim which it was, because
the collision code passes only the damage type. The item OBJECT does know. From
the collision loop at 0x805725e8:

    lwz r0, 13848(r21)      ItemDirector = *(0x809C3618)
    add r4, r0, r19         r19 steps by 4
    lwz r31, 612(r4)        live objects at ItemDirector + 0x264 + i*4
    lwz r0, 4(r31)          +0x04 item type index
    lbz r23, 108(r31)       +0x6c owner, the racer who fired it
    mulli r0, r0, 12        the type indexes the handler table at 0x808b5468
    bl  ...                 which returns the damage type

That type index is a different enum from the held-item ids, so this script
learns the mapping instead of assuming it: every time a racer's held item goes
to empty, whatever object appears with that racer as owner names the index.

Run (no sudo):
  mk/bin/python3 -m analysis.find_item_objects [recording-substring]
"""

import glob
import os
import sys
from collections import Counter, defaultdict

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import ITEM_DIRECTOR, N_PLAYERS, be_u32
from analysis.cross_check_damage import read_held, uses, ITEM_NAMES, EMPTY

OFF_OBJECT_ARRAY = 0x264
MAX_OBJECTS = 16            # entry 16 of the array is a static pointer, so 16
OFF_TYPE = 0x04
OFF_OWNER = 0x6C
SPAWN_WINDOW = 0.6          # seconds after a use for the object to appear


def is_heap(a):
    return 0x80900000 <= a < 0x81800000 or 0x90000000 <= a < 0x91800000


def live_objects(img, regions):
    """{array index: (type, owner)} for every item currently in the world.

    Keyed by index, not address: the game hands objects out of a pool, so the
    same address comes back for a later item and keying by address would count
    a dozen shells as one.
    """
    di = capfmt.addr_to_index(ITEM_DIRECTOR, regions)
    director = be_u32(img, di)
    out = {}
    for i in range(MAX_OBJECTS):
        j = capfmt.addr_to_index(director + OFF_OBJECT_ARRAY + i * 4, regions)
        if j is None:
            break
        p = be_u32(img, j)
        if not is_heap(p):
            continue
        tj = capfmt.addr_to_index(p + OFF_TYPE, regions)
        oj = capfmt.addr_to_index(p + OFF_OWNER, regions)
        if tj is None or oj is None:
            continue
        typ = be_u32(img, tj)
        owner = int(img[oj])
        if typ < 24 and owner <= N_PLAYERS:
            out[i] = (typ, owner)
    return out


def track(s):
    """(t, [{index: (type, owner)} per frame])"""
    t = np.full(len(s), np.nan)
    objs = [None] * len(s)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        t[i] = s.index[i]["mono"]
        objs[i] = live_objects(img, s.regions)
    return t, objs


def spawns(t, objs, order):
    """(time, index, type, owner) each time a slot starts holding a new item."""
    out = []
    prev = {}
    for i in order:
        cur = objs[i]
        for k, v in cur.items():
            if prev.get(k) != v:
                out.append((float(t[i]), k, v[0], v[1]))
        prev = cur
    return out


def despawns(t, objs, order):
    """(time, index, type, owner) each time a slot stops holding an item."""
    out = []
    prev = {}
    for i in order:
        cur = objs[i]
        for k, v in prev.items():
            if cur.get(k) != v:
                out.append((float(t[i]), k, v[0], v[1]))
        prev = cur
    return out


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]

    votes = defaultdict(Counter)
    peak = 0
    for d in dirs:
        s = Session(d)
        t, objs = track(s)
        if all(o is None for o in objs):
            continue
        used = uses(t, read_held(s))
        order = [i for i in range(len(t)) if objs[i] is not None]
        peak = max(peak, max(len(objs[i]) for i in order))

        sp = spawns(t, objs, order)
        for when, k, typ, owner in sp:
            cand = [u for u in used if u[1] == owner
                    and 0.0 <= when - u[0] <= SPAWN_WINDOW]
            if len(cand) == 1:
                votes[typ][cand[0][2]] += 1
        print("%-40s %4d spawns, %d item uses"
              % (os.path.basename(d)[:40], len(sp), len(used)), flush=True)

    print("\nmost objects alive at once: %d (array scanned to %d)"
          % (peak, MAX_OBJECTS))
    print("\nworld item type index -> held item that produced it")
    print("%-6s %-24s %s" % ("index", "best match", "votes"))
    for typ in sorted(votes):
        c = votes[typ]
        best, n = c.most_common(1)[0]
        total = sum(c.values())
        print("%-6d %-24s %d/%d   %s"
              % (typ, ITEM_NAMES.get(best, best), n, total,
                 ", ".join("%s x%d" % (ITEM_NAMES.get(k, k), v)
                           for k, v in c.most_common(4))))


if __name__ == "__main__":
    main()
