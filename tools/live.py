#!/usr/bin/env python3
"""Live race view in the terminal. Updates 20x a second until ctrl-c.

    sudo python3 -m tools.live

Needs sudo because reading another process's memory does.

Every race that actually starts is written out to `races/` as an event log
when it ends - a course change, the game leaving the race, or ctrl-c. That
file is a few tens of kB and everything in `tools/report.py` is rebuilt from
it, so the gigabyte recordings are only needed for finding new things.
"""

import time

from mkw import addresses as A
from mkw import racelog
from mkw import reader
from mkw.events import Race, fmt, readable, DROPOUT
from mkw.names import COURSES, ITEMS, DAMAGE_TYPES, VEHICLES

REFRESH = 0.05
EVENTS_SHOWN = 14


def racer(r, slot):
    return next((x for x in (r.get("racers") or []) if x["slot"] == slot), None)


def render(r, race):
    if r is None:
        return "waiting for a race..."
    code = r["course_code"]
    me = next(p for p in r["players"] if p["slot"] == A.LOCAL_SLOT)
    mine = racer(r, A.LOCAL_SLOT)
    # The race clock, which is zero until GO. The per-racer counter at +0x2C
    # starts 412 frames earlier at the intro camera, which is why this view
    # used to show a clock ticking over the track flyover before the countdown.
    clock = r.get("race_time")
    head = ("%-22s  %s   P%d  lap %d   holding: %s%s"
            % (COURSES.get(code, "course 0x%02x" % code),
               fmt(clock) if race.started else "-- countdown --",
               me["position"],
               min(me["lap"], me["lap_reached"]),
               ITEMS.get(me.get("item"), "?"),
               "   (spinning: %s)" % ITEMS.get(me.get("roulette"))
               if me.get("roulette") not in (None, A.EMPTY_ITEM) else ""))
    if mine is not None:
        head = ("you are %s on the %s\n" % (
            race.names.get(A.LOCAL_SLOT, "?"),
            VEHICLES.get(mine["vehicle"], "vehicle %d" % mine["vehicle"]))
        ) + head
    if (me.get("damage") or -1) >= 0:
        kind, cause = DAMAGE_TYPES.get(me["damage"], ("Hit", "something"))
        head += "   *** %s - %s ***" % (kind.upper(), cause)

    out = [head, "",
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
                      "<- you" if p["slot"] == A.LOCAL_SLOT else
                      ("done %s" % fmt(p["finish"]) if p["finished"] else "")))
    out.append("")
    for e in readable(race.events)[-EVENTS_SHOWN:]:
        out.append("  %9s  %s" % (fmt(e["t"]), race.text(e)))
    return "\n".join(out)


def main():
    if not reader.hook():
        print("not hooked to Dolphin - is the emulator running?")
        return
    saved = []

    def store(race):
        try:
            saved.append(racelog.save(race, source="live"))
        except Exception as exc:            # never lose the race for a bad write
            saved.append("FAILED to save: %s" % exc)

    race = Race(on_end=store)
    last = None
    print("\033[?25l", end="")            # hide cursor
    try:
        while True:
            try:
                r = reader.read()
            except Exception:
                r = None
            race.update(r)
            # Hold the last good frame through a torn read rather than
            # flashing "waiting for a race" for one refresh.
            if r is not None:
                last = r
            elif race.missed >= DROPOUT:
                last = None
            print("\033[H\033[J" + render(last, race)
                  + "\n\n(ctrl-c to stop; %d race%s saved)"
                  % (len(saved), "" if len(saved) == 1 else "s"),
                  end="", flush=True)
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h")                # show cursor
        race.end()
        for path in saved:
            print("saved -> %s" % path)


if __name__ == "__main__":
    main()
