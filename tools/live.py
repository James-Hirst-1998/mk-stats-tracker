#!/usr/bin/env python3
"""Live race view in the terminal. Updates 20x a second until ctrl-c.

    sudo python3 -m tools.live

Needs sudo because reading another process's memory does.
"""

import time

from mkw import addresses as A
from mkw import reader
from mkw.events import Race, fmt, DROPOUT
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
    head = ("%-22s  %s   P%d  lap %d/%d   holding: %s%s"
            % (COURSES.get(code, "course 0x%02x" % code),
               fmt(me["clock"]), me["position"],
               min(me["lap"], me["max_lap"]), me["max_lap"],
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
           "%-4s %-16s %-5s %-5s %-9s %-20s %-24s %s"
           % ("pos", "racer", "slot", "lap", "progress", "holding",
              "lap splits", "")]
    for p in sorted(r["players"], key=lambda x: x["position"]):
        sp = reader.splits_of(p["cumulative"])
        who = racer(r, p["slot"])
        out.append("%-4d %-16s %-5d %-5s %-9.4f %-20s %-24s %s"
                   % (p["position"],
                      "%s%s" % (race.names.get(p["slot"], "slot %d" % p["slot"]),
                                " (CPU)" if who and who["cpu"] else ""),
                      p["slot"],
                      "%d/%d" % (min(p["lap"], p["max_lap"]), p["max_lap"]),
                      p["completion"],
                      ITEMS.get(p.get("item"), "?"),
                      " ".join("%.3f" % x for x in sp) or "-",
                      "<- you" if p["slot"] == A.LOCAL_SLOT else
                      ("done %s" % fmt(p["finish"]) if p["finished"] else "")))
    out.append("")
    for t, text in race.events[-EVENTS_SHOWN:]:
        out.append("  %9s  %s" % (fmt(t), text))
    return "\n".join(out)


def main():
    if not reader.hook():
        print("not hooked to Dolphin - is the emulator running?")
        return
    race = Race()
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
            print("\033[H\033[J" + render(last, race) + "\n\n(ctrl-c to stop)",
                  end="", flush=True)
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h")                # show cursor


if __name__ == "__main__":
    main()
