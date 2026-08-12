#!/usr/bin/env python3
"""Drive the live reader from a recording instead of from Dolphin.

Nothing goes to a live test until it has been run against something smaller
first. This swaps the four accessors in `mkw.reader` for reads out of a
recorded frame, so the real read() and the real Race code run unmodified and
the event stream printed here is exactly what the live view would print.

    python3 -m tools.replay_live [recording-substring]
"""

import glob
import os
import struct
import sys

from mkw import reader
from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from mkw.events import Race, fmt


class Unmapped(Exception):
    pass


def install(session, state):
    def raw(addr, size):
        i = capfmt.addr_to_index(addr, session.regions)
        if i is None or capfmt.addr_to_index(addr + size - 1,
                                             session.regions) is None:
            raise Unmapped(hex(addr))
        return state["img"][i:i + size].tobytes()

    reader.u8 = lambda a: raw(a, 1)[0]
    reader.u16 = lambda a: struct.unpack(">H", raw(a, 2))[0]
    reader.u32 = lambda a: struct.unpack(">I", raw(a, 4))[0]
    reader.f32 = lambda a: struct.unpack(">f", raw(a, 4))[0]


def main():
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r in %s" % (which, RECORDINGS))
        return
    s = Session(dirs[0])

    state = {"img": None}
    install(s, state)
    race = Race()
    last = None
    for i, img in s.frames():
        state["img"] = img
        try:
            r = reader.read()
        except Exception:
            r = None
        race.update(r)
        if r is not None:
            last = r
    race.flush()                    # hits still inside their despawn window

    print("%s" % os.path.basename(dirs[0]))
    print("%d events\n" % len(race.events))
    for t, text in race.events:
        print("  %9s  %s" % (fmt(t), text))

    if last is None:
        return
    print("\nfinal standings:")
    for p in sorted(last["players"], key=lambda x: x["position"]):
        sp = reader.splits_of(p["cumulative"])
        print("  P%-3d slot %-2d  laps %-26s total %-10s leading %5.1fs"
              % (p["position"], p["slot"],
                 " ".join("%.3f" % x for x in sp) or "-",
                 fmt(p["finish"]) if p["finished"] else "(racing)",
                 p["leading"]))


if __name__ == "__main__":
    main()
