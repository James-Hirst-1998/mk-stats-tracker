#!/usr/bin/env python3
"""Offline: check that a stored race log is a faithful replacement for the race.

A race log is only worth having if nothing is lost by throwing the recording
away. Two checks per recording, both against the recording itself:

  1. round trip. Replay the recording, write the log, read it back, and render
     every event from the file. Every line must be identical to the line the
     live view produced. If naming, ids or ordering were lost in the write,
     this catches it.

  2. positions rebuild. Time spent in first place is reconstructed from the
     stored position swaps and compared against `+0x30`, the game's own
     frames-in-first counter, which the reconstruction never sees. They should
     agree to within one 20 Hz sample per crossing into or out of first.

Also prints what a race costs to keep.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_race_log [recording-substring]
"""

import glob
import os
import struct
import sys
import tempfile

from mkw import addresses as A
from mkw import racelog, reader
from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from mkw.events import Race, describe
from mkw.report import positions

SAMPLE = 1.0 / 20                   # the recorder's interval, and the tolerance


def replay(path):
    s = Session(path)
    state = {"img": None}

    def raw(addr, size):
        i = capfmt.addr_to_index(addr, s.regions)
        if i is None or capfmt.addr_to_index(addr + size - 1, s.regions) is None:
            raise ValueError(hex(addr))
        return state["img"][i:i + size].tobytes()

    reader.u8 = lambda a: raw(a, 1)[0]
    reader.u16 = lambda a: struct.unpack(">H", raw(a, 2))[0]
    reader.u32 = lambda a: struct.unpack(">I", raw(a, 4))[0]
    reader.f32 = lambda a: struct.unpack(">f", raw(a, 4))[0]

    race = Race()
    for i, img in s.frames():
        state["img"] = img
        try:
            r = reader.read()
        except Exception:
            r = None
        race.update(r)
    race.flush()
    return race


def run(path, root):
    race = replay(path)
    print(os.path.basename(path))
    if not race.worth_keeping():
        print("  no race started in this recording")
        return False

    live = [(e["t"], race.text(e)) for e in race.events]
    out = racelog.save(race, source="validate", root=root)
    log = racelog.RaceLog(out)
    stored = [(e["t"], describe(e, log.field)) for e in log.events]

    ok = live == stored
    print("  %s round trip: %d events, %d lines identical"
          % ("PASS" if ok else "FAIL", len(live),
             sum(1 for a, b in zip(live, stored) if a == b)))
    if not ok:
        for a, b in zip(live, stored):
            if a != b:
                print("     live   %s" % (a,))
                print("     stored %s" % (b,))
                break

    rebuilt = positions(log)
    grid = {r["slot"]: r["grid"] for r in log.meta.get("racers", [])}
    swaps = log.of_type("pos")
    margin, worst, worst_slot, worst_tol = None, 0.0, None, 0.0
    for st in log.standings:
        s = st["slot"]
        counter = st["leading"] or 0.0
        # +0x30 runs from the intro, so the racer on pole is credited the whole
        # countdown as time in first. Measured, not assumed: it is the same 412
        # frames the two clocks differ by.
        if grid.get(s) == 1:
            counter -= A.COUNTDOWN_FRAMES / 60.0
        # Every crossing into or out of first is seen up to one sample late, so
        # the error a racer can accumulate is one sample per crossing - plus
        # anything before `begins`, which was never seen at all.
        crossings = sum(1 for e in swaps if e["slot"] == s
                        and 1 in (e["from"], e["to"]))
        tol = SAMPLE * max(crossings, 1) + (log.meta.get("begins") or 0.0)
        d = abs(rebuilt.get(s, {}).get(1, 0.0) - max(counter, 0.0))
        if margin is None or d - tol > margin:
            margin, worst, worst_slot, worst_tol = d - tol, d, s, tol
    good = worst <= worst_tol
    ok &= good
    print("  %s time in P1 rebuilt from the position events matches the game's "
          "own counter for all 12, worst %.3fs against %.2fs allowed (%s)"
          % ("PASS" if good else "FAIL", worst, worst_tol,
             log.field.name(worst_slot) if worst_slot is not None else "-"))

    kb = os.path.getsize(out) / 1024.0
    secs = max((e["t"] for e in log.events), default=0.0)
    print("  %.1f kB for %.0fs of racing, %d events - %.0f bytes per event, "
          "%.2f kB per racing second" % (kb, secs, len(log.events),
                                         kb * 1024 / max(len(log.events), 1),
                                         kb / max(secs, 1)))
    return ok


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json")) and which in d]
    if not dirs:
        print("no recording matching %r in %s" % (which, RECORDINGS))
        return
    with tempfile.TemporaryDirectory() as root:
        results = [run(d, root) for d in dirs]
        sizes = [os.path.getsize(p) for p in glob.glob(os.path.join(root, "*"))]
    print("\n%d of %d recordings pass" % (sum(1 for r in results if r),
                                          len(results)))
    if sizes:
        print("a race costs %.0f-%.0f kB, %.0f kB on average; a gigabyte holds "
              "about %d of them" % (min(sizes) / 1024, max(sizes) / 1024,
                                    sum(sizes) / len(sizes) / 1024,
                                    1024 ** 3 // (sum(sizes) // len(sizes))))


if __name__ == "__main__":
    main()
