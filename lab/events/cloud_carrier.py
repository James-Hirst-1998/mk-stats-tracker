#!/usr/bin/env python3
"""Find the field on a Thunder Cloud object that says who is carrying it now.

`+0x6C` is the owner every item object has, and for a cloud that is whoever won
it - it does not move when the cloud is passed on. But each cloud gives two
labelled moments for free: the racer it belongs to when it appears, and the
racer it strikes when it goes off, which are different in 5 of the 9 clouds in
the recordings. A byte that reads the first at the start and the second at the
end is the carrier.

Scores every byte offset rather than intersecting, because one frame of
disagreement should not kill the right answer.

Run (no sudo):
  mk/bin/python3 -m lab.events.cloud_carrier [recording-substring]
"""

import sys
from collections import Counter

from mkw import reader
from mkw.capture.session import Session
from tools.replay_live import install
from lab.events.snapshots import recordings

CLOUD = 14
SIZE = 0x400
N_PLAYERS = 12


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    start_hit, end_hit = Counter(), Counter()
    clouds = 0
    for d in recordings(which):
        s = Session(d)
        state = {"img": None}
        install(s, state)
        live = {}                  # address -> (owner at spawn, bytes at spawn)
        pending = []               # clouds waiting for a strike
        was = {}
        for i, img in s.frames():
            state["img"] = img
            try:
                r = reader.read()
            except Exception:
                r = None
            if r is None or not r.get("race_time"):
                continue
            now = {a: o for a, (kind, o) in
                   (r.get("world_items") or {}).items() if kind == CLOUD}
            for a, o in now.items():
                if a not in live:
                    live[a] = (o, dump(a))
            for a in list(live):
                if a not in now:
                    pending.append(live.pop(a))
            for p in r["players"]:
                dmg = p.get("damage")
                if dmg is None:
                    continue
                if was.get(p["slot"]) != dmg and dmg == 17:
                    # a strike: the cloud is still alive, so read it now
                    for a, (owner, first) in live.items():
                        if owner == p["slot"]:
                            continue        # never passed on, labels nothing
                        clouds += 1
                        last = dump(a)
                        for off in range(SIZE):
                            if first[off] == owner:
                                start_hit[off] += 1
                            if last[off] == p["slot"]:
                                end_hit[off] += 1
                was[p["slot"]] = dmg
        print("read %s" % d.split("/")[-1])

    print("\n%d clouds that were passed on before they went off" % clouds)
    print("offsets reading the winner when it appeared AND the victim when it "
          "struck:")
    both = [(off, start_hit[off], end_hit[off]) for off in range(SIZE)
            if start_hit[off] and end_hit[off]]
    both.sort(key=lambda x: -(x[1] + x[2]))
    for off, a, b in both[:14]:
        print("   +0x%03X  winner %d/%d, victim %d/%d" % (off, a, clouds,
                                                          b, clouds))
    if not both:
        print("   none")


def dump(addr):
    out = []
    for off in range(SIZE):
        try:
            out.append(reader.u8(addr + off))
        except Exception:
            out.append(-1)
    return out


if __name__ == "__main__":
    main()
