#!/usr/bin/env python3
"""Start this, play, stop it. Every race in between is stored.

    sudo mk/bin/python3 -m tools.track                 # a session called "session"
    sudo mk/bin/python3 -m tools.track versus-night    # give it a name
    sudo mk/bin/python3 -m tools.track versus-night --quiet

Needs sudo because reading another process's memory does.

Leave it running across a whole VS sequence. Each race is written the moment
it ends, into one session directory, so ctrl-c at any point costs at most the
race you are in the middle of. Read it back afterwards with `tools/report.py`,
which needs neither Dolphin nor sudo.

`--quiet` prints one line per event instead of redrawing the live table, which
is what you want if you are going to scroll back through it.
"""

import datetime
import json
import os
import sys
import time

from mkw import addresses as A
from mkw import reader
from mkw import session as sess
from mkw.events import Race, fmt, readable, DROPOUT
from mkw.names import course_name, ITEMS, DAMAGE_TYPES, VEHICLES

REFRESH = 0.05
EVENTS_SHOWN = 14


class LiveStatus:
    """Keep <session>/live.json saying what race is being recorded right now.

    The dashboard polls for this file. It exists only while a race is in
    progress; a failure to write it must never touch the recording, so every
    filesystem call is allowed to fail quietly.
    """

    def __init__(self, rec):
        self.rec = rec
        self.wrote = None               # (race number, course) last written

    def path(self):
        return os.path.join(self.rec.dir, "live.json")

    def update(self, race):
        try:
            if not race.started:
                return self.clear()
            now = (len(self.rec) + 1, race.course)
            if now == self.wrote:
                return
            os.makedirs(self.rec.dir, exist_ok=True)
            with open(self.path(), "w") as f:
                json.dump({"race": now[0], "course": now[1],
                           "started": datetime.datetime.now()
                           .isoformat(timespec="seconds")}, f)
            self.wrote = now
        except OSError:
            pass

    def clear(self):
        if self.wrote is None:
            return
        try:
            os.remove(self.path())
        except OSError:
            pass
        self.wrote = None


def racer(r, slot):
    return next((x for x in (r.get("racers") or []) if x["slot"] == slot), None)


def header(race, rec):
    """One line saying where the session is up to, above everything else."""
    return "session %s   %d race%s stored   %s" % (
        rec.name, len(rec), "" if len(rec) == 1 else "s",
        "recording race %d" % (len(rec) + 1) if race.started
        else "waiting for the lights")


def render(r, race, rec):
    if r is None:
        return header(race, rec) + "\n\nwaiting for a race..."
    # `race.course`, not this frame's read: `read_course` returns None while
    # the pointer is being rebuilt between races, which is precisely when the
    # next race is starting.
    code = r["course_code"] if r["course_code"] is not None else race.course
    # `race.local_slot`, not the constant: which racer is the human is
    # read from RaceConfig, so a second person on the couch does not make this
    # view describe somebody else's race.
    me = next(p for p in r["players"] if p["slot"] == race.local_slot)
    mine = racer(r, race.local_slot)
    # The race clock, which is zero until GO. The per-racer counter at +0x2C
    # starts 412 frames earlier at the intro camera, which is why this view
    # used to show a clock ticking over the track flyover before the countdown.
    clock = r.get("race_time")
    head = ("%-22s  %s   P%d  lap %d   holding: %s%s"
            % (course_name(code),
               fmt(clock) if race.started else "-- countdown --",
               me["position"],
               min(me["lap"], me["lap_reached"]),
               ITEMS.get(me.get("item"), "?"),
               "   (spinning: %s)" % ITEMS.get(me.get("roulette"))
               if me.get("roulette") not in (None, A.EMPTY_ITEM) else ""))
    if mine is not None:
        head = ("you are %s on the %s\n" % (
            race.field.name(race.local_slot),
            VEHICLES.get(mine["vehicle"], "vehicle %d" % mine["vehicle"]))
        ) + head
    if (me.get("damage") or -1) >= 0:
        kind, cause = DAMAGE_TYPES.get(me["damage"], ("Hit", "something"))
        head += "   *** %s - %s ***" % (kind.upper(), cause)

    out = [header(race, rec), "", head, "",
           "%-4s %-18s %-5s %-5s %-9s %-20s %-24s %s"
           % ("pos", "racer", "slot", "lap", "progress", "holding",
              "lap splits", "")]
    for p in sorted(r["players"], key=lambda x: x["position"]):
        sp = reader.splits_of(p["cumulative"])
        who = racer(r, p["slot"])
        out.append("%-4d %-18s %-5d %-5s %-9.4f %-20s %-24s %s"
                   % (p["position"],
                      "%s%s" % (race.names.get(p["slot"], "slot %d" % p["slot"]),
                                " (CPU)" if who and who["cpu"] else ""),
                      p["slot"],
                      "%d" % min(p["lap"], p["lap_reached"]),
                      p["completion"],
                      ITEMS.get(p.get("item"), "?"),
                      " ".join("%.3f" % x for x in sp) or "-",
                      "<- you" if p["slot"] == race.local_slot else
                      ("done %s" % fmt(p["finish"]) if p["finished"] else "")))
    out.append("")
    for e in readable(race.events)[-EVENTS_SHOWN:]:
        out.append("  %9s  %s" % (fmt(e["t"]), race.text(e)))
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv[1:]
    if not reader.hook():
        print("not hooked to Dolphin - is the emulator running?")
        return 1

    rec = sess.Recorder(name=args[0] if args else None)
    print("session -> %s" % rec.dir)
    print("play as many races as you like; ctrl-c when you are done.")
    print("nothing is written until a race actually finishes.\n")

    saved = []

    def store(race):
        try:
            saved.append(rec.add(race))
            print("\n>> race %d stored: %s\n" % (len(rec), saved[-1]))
        except Exception as exc:        # never lose the session for a bad write
            print("\n>> FAILED to store race %d: %s\n" % (len(rec) + 1, exc))

    race = Race(on_end=store)
    live = LiveStatus(rec)
    shown = 0
    problems = 0
    last = None
    if not quiet:
        print("\033[?25l", end="")            # hide cursor
    try:
        while True:
            try:
                r = reader.read()
            except Exception:
                r = None
            race.update(r)
            live.update(race)
            if r is not None:
                last = r
            elif race.missed >= DROPOUT:
                last = None
            # Drawing the screen is not what this is for. A bug in it must
            # never take down a session that is recording correctly - James
            # lost one to `read_course` returning None between races, which is
            # a value it is entitled to return.
            try:
                if quiet:
                    lines = readable(race.events)
                    if len(lines) < shown:      # a new race reset the log
                        shown = 0
                    for e in lines[shown:]:
                        print("  %9s  %s" % (fmt(e["t"]), race.text(e)),
                              flush=True)
                    shown = len(lines)
                else:
                    print("\033[H\033[J" + render(last, race, rec)
                          + "\n\n(ctrl-c to stop)", end="", flush=True)
            except Exception as exc:
                problems += 1
                print("\033[H\033[J%s\n\nstill recording; the display "
                      "failed %d time%s, latest: %r"
                      % (header(race, rec), problems,
                         "" if problems == 1 else "s", exc),
                      end="", flush=True)
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        pass
    finally:
        # Whatever happened, put the cursor back and keep the race in progress.
        if not quiet:
            print("\033[?25h")
        race.end()
        live.clear()
        rec.write_index()

    if not len(rec):
        print("\nno races were played, so nothing was written.")
        return 0
    print("\nsession %s: %d race%s"
          % (rec.dir, len(rec), "" if len(rec) == 1 else "s"))
    for row in rec.meta["races"]:
        print("  %2d  %-22s  you finished P%s"
              % (row["n"], course_name(row["course"]),
                 row["your_position"]))
    print("\nread it back with:  mk/bin/python3 -m tools.report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
