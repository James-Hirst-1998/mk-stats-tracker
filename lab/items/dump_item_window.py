#!/usr/bin/env python3
"""Frame-by-frame held / roulette / damage and world objects over a time window.

For looking at one moment closely after `analysis/floor_pickups.py` has pointed
at it: every sample between t0 and t1 on the race clock, for the racers whose
item fields move in that window, plus every world object born or gone.

Run (no sudo):
  mk/bin/python3 -m lab.items.dump_item_window <recording-substring> <t0> <t1>
"""

import glob
import os
import sys

from mkw import reader
from mkw.addresses import EMPTY_ITEM as EMPTY, N_PLAYERS
from mkw.capture.session import Session, RECORDINGS
from mkw.names import ITEMS, OBJECT_TYPES
from tools.replay_live import install


def main():
    which, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if which in d and os.path.isfile(os.path.join(d, "meta.json"))]
    s = Session(dirs[0])
    state = {"img": None}
    install(s, state)
    rows = []
    for i, img in s.frames():
        state["img"] = img
        try:
            r = reader.read()
        except Exception:
            continue
        if r is None or r["race_time"] is None:
            continue
        t = r["race_time"]
        if t > t1 + 1.0:
            break
        if t < t0:
            continue
        rows.append((i, t, r))

    moving = set()
    for _, _, r in rows:
        for p in r["players"]:
            if p["item"] not in (None, EMPTY) or p["roulette"] not in (None, EMPTY):
                moving.add(p["slot"])
    moving = sorted(moving)
    print("slots with a non-empty item or roulette field in [%.1f, %.1f]: %s"
          % (t0, t1, moving))
    print("columns: held/roulette/damage per slot; 20 = empty, - = unreadable")

    prev_world = None
    for i, t, r in rows:
        cells = []
        for p in r["players"]:
            if p["slot"] not in moving:
                continue
            h, ro, dm = p["item"], p["roulette"], p["damage"]
            cells.append("s%d:%s/%s/%s" % (
                p["slot"],
                "-" if h is None else h, "-" if ro is None else ro,
                "-" if dm is None else dm))
        world = r["world_items"]
        notes = []
        if world is not None and prev_world is not None:
            for a, v in world.items():
                if a not in prev_world:
                    notes.append("+%s(owner %d)@%x" % (
                        OBJECT_TYPES.get(v[0], "type%d" % v[0]), v[1], a))
            for a, v in prev_world.items():
                if a not in world:
                    notes.append("-%s(owner %d)@%x" % (
                        OBJECT_TYPES.get(v[0], "type%d" % v[0]), v[1], a))
        if world is not None:
            prev_world = world
        print("%5d %8.3f  %s  %s" % (i, t, "  ".join(cells), " ".join(notes)))

    print("\nitem ids: %s" % ", ".join("%d=%s" % kv for kv in sorted(ITEMS.items())))


if __name__ == "__main__":
    main()
