#!/usr/bin/env python3
"""Offline: does picking a dropped item up off the road show in the fields we read?

James picked a Star up off the floor in a stored race and the log has no `hold`
for it. Across 13 stored races there is not one `hold` that was not preceded by
a `box` for the same racer, so either it never happened in any of them or the
held field does not move the way we think when the item comes from the road
rather than from a roulette.

This reads every frame of a recording through the real `mkw.reader` accessors
and asks three things:

  1. every held-field 20 -> item transition, and whether that racer's roulette
     field was non-empty in the ROULETTE seconds before it. A floor pickup would
     be one with no roulette.
  2. every `lost` (held goes empty while the damage field reads a DROPS_ITEM
     type), and what happens in the FOLLOW seconds after: any no-roulette
     pickup by anyone, and every world object that appears or disappears.
  3. every world-object spawn by type, and whether a use or a loss by its
     owner sits just before it - so a dropped item's object type, if it has
     one, names itself.

Run (no sudo):
  mk/bin/python3 -m analysis.floor_pickups [recording-substring]
"""

import glob
import os
import sys
from collections import Counter, defaultdict

from mkw import reader
from mkw.addresses import EMPTY_ITEM as EMPTY, N_PLAYERS
from mkw.capture.session import Session, RECORDINGS
from mkw.names import DROPS_ITEM, ITEMS, OBJECT_TYPES
from tools.replay_live import install

ROULETTE = 6.0      # a roulette runs 3.55s for the human, 1.15s for an AI
FOLLOW = 20.0
SPAWN = 0.6         # a used item's object appears within this of the use


def item(v):
    return ITEMS.get(v, str(v))


def obj(t):
    return OBJECT_TYPES.get(t, "type %d" % t)


def read_all(s):
    """One row per readable in-race frame: (t, held, roulette, damage, world)."""
    state = {"img": None}
    install(s, state)
    rows = []
    unreadable = 0      # race running, item fields not readable this frame
    for i, img in s.frames():
        state["img"] = img
        try:
            r = reader.read()
        except Exception:
            r = None
        if r is None or r["race_time"] is None or r["race_time"] <= 0:
            continue
        held = [p["item"] for p in r["players"]]
        roul = [p["roulette"] for p in r["players"]]
        dmg = [p["damage"] for p in r["players"]]
        if None in held or None in roul or None in dmg:
            # `read_items` fails closed on any byte above 20, so a pickup that
            # wrote an odd value here would hide a whole hold from the reader.
            unreadable += 1
            continue
        rows.append((r["race_time"], held, roul, dmg, r["world_items"]))
    print("in-race frames with item fields unreadable: %d" % unreadable)
    return rows


def transitions(rows):
    """holds: (t, slot, item, roulette_seen); clears: (t, slot, item, damage)."""
    holds, clears = [], []
    for k in range(N_PLAYERS):
        prev = None
        for j, (t, held, roul, dmg, _) in enumerate(rows):
            v = held[k]
            if prev is not None and prev != v:
                if prev == EMPTY:
                    # was the roulette for this racer live at any sample in the
                    # window before the item landed in their hands?
                    seen = any(rows[m][2][k] != EMPTY for m in range(j - 1, -1, -1)
                               if t - rows[m][0] <= ROULETTE)
                    holds.append((t, k, v, seen))
                elif v == EMPTY:
                    clears.append((t, k, prev, dmg[k]))
            prev = v
    holds.sort()
    clears.sort()
    return holds, clears


def object_lives(rows):
    """{address: [(type, owner, born_t, died_t or None), ...]}."""
    lives = defaultdict(list)
    prev = None
    for t, _, _, _, world in rows:
        if world is None:
            continue
        if prev is not None:
            for a, v in world.items():
                if a not in prev:
                    lives[a].append([v[0], v[1], t, None])
            for a in prev:
                if a not in world and lives[a] and lives[a][-1][3] is None:
                    lives[a][-1][3] = t
        prev = world
    out = []
    for a, runs in lives.items():
        for ty, owner, born, died in runs:
            out.append((born, died, ty, owner, a))
    out.sort(key=lambda x: x[0])
    return out


def main():
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]

    spawn_after = Counter()     # object type -> what preceded the spawn
    for d in dirs:
        s = Session(d)
        rows = read_all(s)
        name = os.path.basename(d)
        print("=" * 72)
        print("%s: %d readable in-race frames, %.1fs" % (
            name, len(rows), rows[-1][0] - rows[0][0] if rows else 0))
        if not rows:
            continue
        holds, clears = transitions(rows)
        lost = [c for c in clears if c[3] in DROPS_ITEM]
        used = [c for c in clears if c[3] not in DROPS_ITEM]
        lives = object_lives(rows)

        no_roul = [h for h in holds if not h[3]]
        print("\nheld 20 -> item: %d, of which without a roulette in the %.0fs "
              "before: %d" % (len(holds), ROULETTE, len(no_roul)))
        for t, k, v, _ in no_roul:
            print("  %8.3f  slot %2d  %-20s  NO ROULETTE" % (t, k, item(v)))

        print("\nheld -> 20 while damage in DROPS_ITEM (`lost`): %d" % len(lost))
        for t, k, v, dm in lost:
            print("  %8.3f  slot %2d  %-20s  damage %d" % (t, k, item(v), dm))
            # anyone getting that item, or anything, with no roulette after
            for ht, hk, hv, seen in holds:
                if t < ht <= t + FOLLOW and not seen:
                    print("      %8.3f  slot %2d  picks up %-16s NO ROULETTE"
                          % (ht, hk, item(hv)))
            for ht, hk, hv, seen in holds:
                if t < ht <= t + FOLLOW and seen and hv == v:
                    print("      %8.3f  slot %2d  gets %-16s from a roulette"
                          % (ht, hk, item(hv)))
            # world objects around the loss
            for born, died, ty, owner, a in lives:
                if t - 0.5 <= born <= t + FOLLOW:
                    print("      %8.3f  object %-16s owner %2d  born%s"
                          % (born, obj(ty), owner,
                             "" if died is None else ", gone %.3f (%.2fs)"
                             % (died, died - born)))

        # what precedes each spawn, by object type
        print("\nworld-object spawns by type, and what the owner did just before:")
        per = defaultdict(Counter)
        for born, died, ty, owner, a in lives:
            u = [c for c in used if c[1] == owner and 0 <= born - c[0] <= SPAWN]
            l = [c for c in lost if c[1] == owner and 0 <= born - c[0] <= SPAWN]
            if l:
                tag = "after a loss of %s" % item(l[-1][2])
            elif u:
                tag = "after a use of %s" % item(u[-1][2])
            else:
                tag = "nothing within %.1fs" % SPAWN
            per[ty][tag] += 1
            spawn_after[(ty, tag.split(" of ")[0])] += 1
        for ty in sorted(per):
            print("  %-16s %s" % (obj(ty), dict(per[ty])))

    print("\n" + "=" * 72)
    print("all recordings, spawns by (object type, cause):")
    for (ty, tag), n in sorted(spawn_after.items()):
        print("  %-16s %-28s %d" % (obj(ty), tag, n))


if __name__ == "__main__":
    main()
