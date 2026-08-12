#!/usr/bin/env python3
"""Offline: say exactly which item hit each racer, not just "a shell".

The damage field the game writes says "knockback", which is a green shell, a
red shell and a fake item box alike. The item object that did it knows: `+0x00`
is its class, `+0x6C` is the racer who fired it. Matching the two needs the
world item objects, which this repo previously read from `ItemDirector + 0x264`
- a per-kart collision buffer, capped at 16 and refilled per kart, which is why
it never saw more than three items at once.

The real pools are a table in ItemDirector, one entry per item type:

    entry = ItemDirector + 0x48 + type * 0x24
      +0x00  type index          +0x08  capacity
      +0x04  -> object array     +0x10  how many are live now
    live objects are array[0 .. live-1]; each slot keeps its address all race

Two independent things then pin a hit to an object:

  1. Which object types can produce a given damage type is read out of the
     game's code, not guessed. `u32(0x808B5468 + type*0xC + 8)` is that type's
     getDamageType; disassembled, types 0 and 1 return 2, type 7 returns 2,
     type 2 returns 0, and types 5 and 9 return 7 once they have gone off.
  2. The object is destroyed a fixed delay after the hit lands, while it breaks
     or explodes. Measured across seven recordings, not assumed: for damage 0
     and 2 the despawn follows the hit by 0.25-0.40s (20 game frames), sharply
     peaked, against a flat background; for damage 7 it is 1-2s, the longer
     explosion.

Each object is also tied back to the throw that created it, by matching its
spawn to the owner's item going empty. That is read from the held-item field,
which has nothing to do with either the damage field or the pools, so an
agreement between them is a real check.

Run (no sudo):
  mk/bin/python3 -m analysis.name_hit_items [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

import numpy as np

from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import (read as read_damage, spans, DAMAGE,
                                      N_PLAYERS)
from analysis.cross_check_damage import read_held, uses, ITEM_NAMES

ITEM_DIRECTOR = 0x809C3618
POOL_TABLE = 0x48
POOL_STRIDE = 0x24
OFF_POOL_TYPE = 0x00
OFF_POOL_ARRAY = 0x04
OFF_POOL_CAP = 0x08
OFF_POOL_LIVE = 0x10
OFF_OBJECT_OWNER = 0x6C
N_OBJECT_TYPES = 15

OBJECTS = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "type 3",
           4: "Star", 5: "Blue Shell", 6: "type 6", 7: "Fake Item Box",
           8: "type 8", 9: "Bob-omb", 12: "Golden Mushroom"}

# damage type -> the object types whose getDamageType can return it
CAN_CAUSE = {0: {2, 5, 9}, 2: {0, 1, 7}, 7: {5, 9}}

# damage type -> (earliest, latest) the object may despawn after the hit
LAG = {0: (0.20, 0.45), 2: (0.20, 0.45), 7: (0.60, 2.50)}

# object type -> the held-item ids that produce it, for the spawn cross-check
FROM_ITEM = {0: {0, 16}, 1: {1, 17}, 2: {2, 18}, 5: {7}, 7: {3}, 9: {6}}
SPAWN_WINDOW = 1.0


def is_heap(a):
    return a is not None and 0x80900000 <= a < 0x81800000


def live_objects(s, i):
    """{object address: (type, owner)} for one frame, or None."""
    director = s.u32(i, ITEM_DIRECTOR)
    if not is_heap(director):
        return None
    out = {}
    for t in range(N_OBJECT_TYPES):
        e = director + POOL_TABLE + t * POOL_STRIDE
        if s.u32(i, e + OFF_POOL_TYPE) != t:
            return None
        arr = s.u32(i, e + OFF_POOL_ARRAY)
        cap = s.u32(i, e + OFF_POOL_CAP)
        live = s.u32(i, e + OFF_POOL_LIVE)
        if not is_heap(arr) or not cap or cap > 64:
            return None
        if live is None or live > cap:
            return None
        for k in range(live):
            obj = s.u32(i, arr + k * 4)
            if is_heap(obj):
                out[obj] = (t, s.u8(i, obj + OFF_OBJECT_OWNER))
    return out


def track(s):
    """[{object address: (type, owner)}] per frame."""
    objs = [None] * len(s)
    for i, _ in s.frames():
        if s.index[i]["position"] is None:
            continue
        objs[i] = live_objects(s, i)
    return objs


def transitions(t, objs):
    """(spawns, despawns), each (time, address, type, owner)."""
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


def label_spawns(spawns, used):
    """{object address: (spawn time, item id)} where the throw is unambiguous."""
    out = {}
    for when, addr, typ, owner in spawns:
        cand = [u for u in used if u[1] == owner
                and 0.0 <= when - u[0] <= SPAWN_WINDOW]
        out[addr] = (when, cand[0][2] if len(cand) == 1 else None)
    return out


def name_hits(t, dmg, spawns, despawns, used):
    """[(hit time, victim, damage, object type, owners, item id or None)]."""
    born = label_spawns(spawns, used)
    out = []
    for k in range(N_PLAYERS):
        for st, _, v in spans(t, dmg[:, k]):
            if v not in CAN_CAUSE:
                continue
            lo, hi = LAG[v]
            cand = [x for x in despawns
                    if x[2] in CAN_CAUSE[v] and lo <= x[0] - st <= hi]
            # you do not normally break your own shell, but you can drive into
            # your own banana, so only prefer other racers' objects
            pick = [x for x in cand if x[3] != k] or cand
            kinds = {x[2] for x in pick}
            if len(kinds) != 1:
                out.append((st, k, v, None, sorted(kinds), None))
                continue
            typ = pick[0][2]
            items = {born.get(x[1], (0, None))[1] for x in pick}
            items.discard(None)
            out.append((st, k, v, typ, sorted({x[3] for x in pick}),
                        items.pop() if len(items) == 1 else None))
    out.sort()
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    by_item = Counter()
    agree = disagree = no_throw = 0
    named = total = 0
    for d in dirs:
        s = Session(d)
        t, dmg, _, _ = read_damage(s)
        if np.all(np.isnan(t)):
            continue
        spawns, despawns = transitions(t, track(s))
        used = uses(t, read_held(s))
        hits = name_hits(t, dmg, spawns, despawns, used)
        t0 = np.nanmin(t)

        print("=== %s" % os.path.basename(d))
        for st, k, v, typ, owners, item in hits:
            total += 1
            if typ is None:
                print("   %6.1fs slot %-2d  %-22s  unresolved%s"
                      % (st - t0, k, DAMAGE[v][1],
                         " (%s)" % ", ".join(OBJECTS.get(x, x) for x in owners)
                         if owners else ""))
                continue
            named += 1
            by_item[OBJECTS.get(typ, typ)] += 1
            note = ""
            if item is None:
                no_throw += 1
            elif item in FROM_ITEM.get(typ, set()):
                agree += 1
                note = "  [thrown as %s]" % ITEM_NAMES.get(item, item)
            else:
                disagree += 1
                note = "  [MISMATCH: thrown as %s]" % ITEM_NAMES.get(item, item)
            print("   %6.1fs slot %-2d  %-22s  %s, slot %s%s"
                  % (st - t0, k, DAMAGE[v][1], OBJECTS.get(typ, typ),
                     ", ".join(map(str, owners)), note))
        print()

    print("named %d of %d item-caused hits (%.0f%%)"
          % (named, total, 100.0 * named / max(total, 1)))
    print("by item: %s" % dict(by_item.most_common()))
    checked = agree + disagree
    print("of those, %d could be traced back to the throw that spawned them: "
          "%d agree, %d disagree; %d had no unambiguous throw"
          % (checked, agree, disagree, no_throw))


if __name__ == "__main__":
    main()
