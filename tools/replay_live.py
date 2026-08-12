#!/usr/bin/env python3
"""Drive the live reader from a recording instead of from Dolphin.

Nothing goes to a live test until it has been run against something smaller
first. This swaps the four accessors in `mkw.reader` for reads out of a
recorded frame, so the real read() and the real Race code run unmodified and
the event stream printed here is exactly what the live view would print.

    python3 -m tools.replay_live [recording-substring] [--save]

`--save` writes the race out as an event log, the same way the live tool does,
which is how the storage path gets tested without a live race.
"""

import glob
import os
import struct
import sys

from mkw import reader
from mkw import racelog
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    save = "--save" in sys.argv[1:]
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = args[0] if args else ""
    if which:
        dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r in %s" % (which, RECORDINGS))
        return
    s = Session(dirs[0])
    name = os.path.basename(dirs[0])

    written = []

    def store(race):
        written.append(racelog.save(
            race, source="replay:%s" % name,
            notes=s.meta.get("notes") or None))

    state = {"img": None}
    install(s, state)
    race = Race(on_end=store if save else None)
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
    race.end()                      # hits still inside their despawn window

    print("%s" % name)
    print("%d events\n" % len(race.events))
    for e in race.events:
        print("  %9s  %s" % (fmt(e["t"]), race.text(e)))

    if last is not None:
        print("\nfinal standings:")
        for st in race.standings():
            print("  P%-3d %-16s laps %-26s total %-10s leading %5.1fs"
                  % (st["position"], race.who(st["slot"]),
                     " ".join("%.3f" % x for x in st["laps"]) or "-",
                     fmt(st["time"]) if st["finished"] else "(racing)",
                     st["leading"]))

    for path in written:
        print("\nsaved -> %s (%.1f kB)" % (path, os.path.getsize(path) / 1024.0))


if __name__ == "__main__":
    main()
