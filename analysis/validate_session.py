#!/usr/bin/env python3
"""Offline: check that a session of several races records the way a live one will.

There is no multi-race recording, so this makes one: replay several recordings
back to back through a single `Race` and a single session `Recorder`, exactly
as the live tool drives them. That exercises the two things that only happen
between races - noticing the race clock go back to zero, and starting a new
file - without needing James to sit through a VS sequence to find out they are
broken.

Then it checks, on what came out:

  1. one file per race, in order, each a complete race on its own
  2. every race's events survived - same count as the live run produced
  3. the progress stored at 5 Hz, interpolated, reproduces what was actually
     read at 20 Hz. That is the question the progress track exists to answer -
     can a race be replayed from it - and it is about the storage rather than
     about the game, so it is checked against the full-rate reads themselves
     and not against some other field
  4. what a session costs on disk

Run (no sudo):
  mk/bin/python3 -m analysis.validate_session
"""

import glob
import os
import struct
import sys
import tempfile

from mkw import reader
from mkw import session as sess
from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from mkw.events import Race, JUMP


def feed(path, race):
    """Push a whole recording through an existing Race, like the live loop."""
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

    counts = []
    full = []                   # every readable frame, for the 5 Hz comparison
    for i, img in s.frames():
        state["img"] = img
        try:
            r = reader.read()
        except Exception:
            r = None
        race.update(r)
        counts.append(len(race.events))
        if r is not None and race.started:
            full.append((race.clock,
                         {p["slot"]: p["completion"] for p in r["players"]}))
    return (max(counts) if counts else 0), full


def walk_positions(log):
    """Yield (t, {slot: position}) after each position event, in order."""
    at = {}
    swaps = sorted(log.of_type("pos"), key=lambda e: e["t"])
    for e in swaps:
        at.setdefault(e["slot"], e["from"])
    for r in log.meta.get("racers", []):
        at.setdefault(r["slot"], r["grid"])
    yield 0.0, dict(at)
    for e in swaps:
        at[e["slot"]] = e["to"]
        yield e["t"], dict(at)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json")) and which in d]
    if len(dirs) < 2:
        print("need at least two recordings to fake a session")
        return
    ok = True
    with tempfile.TemporaryDirectory() as root:
        rec = sess.Recorder(name="fake-session", root=root)
        race = Race(on_end=rec.add)
        live = []
        for d in dirs:
            n, full = feed(d, race)
            live.append((os.path.basename(d), n, full))
        race.end()

        got = sess.Session(rec.dir)
        good = len(got) == len(dirs)
        ok &= good
        print("%s %d recordings played back to back produced %d races"
              % ("PASS" if good else "FAIL", len(dirs), len(got)))

        for (name, n, _), log in zip(live, got.races):
            same = len(log) == n
            ok &= same
            print("  %s %-46s %4d events live, %4d stored"
                  % ("PASS" if same else "FAIL", name[:46], n, len(log)))

        print()
        for (_, _, full), log in zip(live, got.races):
            errs = []
            ranks = agree = 0
            # Only inside the window the track covers. Feeding recordings
            # straight into each other with no menus between them leaves a
            # few frames either side belonging to the neighbouring race, which
            # is an artefact of faking the session, not of storing it.
            times = log.track_times()
            lo, hi = (times[0], times[-1]) if times else (0.0, -1.0)
            crossings = 0
            for t, live_now in full:
                if not lo <= t <= hi:
                    continue
                got_now = log.progress_at(t)
                order = sorted(got_now, key=lambda s: -got_now[s])
                truth = sorted(live_now, key=lambda s: -live_now[s])
                k = int((t - log.track_t0) * log.track_hz)
                for i, s in enumerate(order):
                    if s not in live_now:
                        continue
                    ranks += 1
                    agree += truth.index(s) == i
                    # Progress goes back to the start of the last lap when a
                    # racer crosses the line. Which side of that a given
                    # instant falls on cannot be recovered from a 5 Hz grid, so
                    # the two samples spanning it are counted, not measured.
                    row = log.track.get(s) or []
                    if k + 1 < len(row) and abs(row[k + 1] - row[k]) > JUMP:
                        crossings += 1
                        continue
                    errs.append(abs(got_now[s] - live_now[s]))
            worst = max(errs) if errs else 0.0
            mid = sorted(errs)[len(errs) // 2] if errs else 0.0
            close = sum(1 for e in errs if e < 0.01) / max(len(errs), 1)
            share = agree / max(ranks, 1)
            # The middle of the distribution is what says the grid is faithful.
            # The tail is not sampling error: a respawn puts a kart back on the
            # track instantly and a mushroom moves it faster than 5 Hz resolves,
            # and neither is something a denser grid would fix.
            good = mid < 0.001 and close > 0.99 and share > 0.98
            ok &= good
            print("  %s %-22s 5 Hz vs the 20 Hz reads: median %.5f laps, "
                  "%.2f%% within 0.01, worst %.4f; same order %.1f%% of %d "
                  "(%d spans of the finish-line wrap not measured)"
                  % ("PASS" if good else "FAIL", log.course_name, mid,
                     close * 100, worst, share * 100, ranks, crossings))

        print()
        files = glob.glob(os.path.join(rec.dir, "*"))
        total = sum(os.path.getsize(f) for f in files)
        races = [f for f in files if f.endswith(".jsonl")]
        print("session on disk: %.0f kB over %d files, %.0f kB per race"
              % (total / 1024, len(files), total / 1024 / max(len(races), 1)))
        print("a gigabyte holds about %d races"
              % (1024 ** 3 // max(total // max(len(races), 1), 1)))
    print("\n%s" % ("all checks pass" if ok else "SOMETHING FAILED"))


if __name__ == "__main__":
    main()
