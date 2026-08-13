#!/usr/bin/env python3
"""Is the Thunder Cloud a world object, and does its owner follow the carrier?

The held item field never carries a cloud - it activates the moment it is won,
so nobody is ever "holding" one - which is why passing it on is invisible from
the item side. But pool type 14 is live while a cloud is in play, and every
item object names its owner at +0x6C. If that owner changes as the cloud moves,
a pass is a read rather than an inference.

Run (no sudo):
  mk/bin/python3 -m lab.events.cloud [recording-substring]
"""

import sys

from lab.events.snapshots import recordings, racing

CLOUD = 14


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    for d in recordings(which):
        name, frames = racing(d)
        if not frames:
            continue
        print("=== %s" % name)
        prev = {}
        alive = 0
        for t, r in frames:
            world = r.get("world_items")
            if world is None:
                continue
            now = {a: o for a, (kind, o) in world.items() if kind == CLOUD}
            alive += len(now)
            for a, o in now.items():
                if a not in prev:
                    print("   %6.1fs  cloud %08x appears, owner slot %d"
                          % (t, a, o))
                elif prev[a] != o:
                    print("   %6.1fs  cloud %08x passed, slot %d -> %d"
                          % (t, a, prev[a], o))
            for a in prev:
                if a not in now:
                    print("   %6.1fs  cloud %08x gone (owner was slot %d)"
                          % (t, a, prev[a]))
            prev = now
        for t, s, v in [(t, p["slot"], p["damage"]) for t, r in frames
                        for p in r["players"] if p.get("damage") == 17]:
            pass
        struck = []
        was = {}
        for t, r in frames:
            for p in r["players"]:
                d = p.get("damage")
                if d is not None and was.get(p["slot"]) != d and d == 17:
                    struck.append((t, p["slot"]))
                if d is not None:
                    was[p["slot"]] = d
        for t, s in struck:
            print("   %6.1fs  slot %d struck" % (t, s))
        print("   %d cloud-frames\n" % alive)


if __name__ == "__main__":
    main()
