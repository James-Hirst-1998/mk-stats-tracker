#!/usr/bin/env python3
"""Read a stored session back. No Dolphin, no recording, no sudo.

    python3 -m tools.report                  the last session: every race, and
                                             the standings across them
    python3 -m tools.report --list           what is stored
    python3 -m tools.report versus           that session
    python3 -m tools.report versus 2         race 2 of it, in full
    python3 -m tools.report versus 2 --all   ... including the position swaps
    python3 -m tools.report versus 2 --replay  ... as a second-by-second replay

Everything printed here is rebuilt from the files. If a number cannot be
produced from them, the stored events are missing something - which is the
check this tool exists to make.
"""

import os
import sys

from mkw import racelog
from mkw import session as sess
from mkw.report import render, render_session, render_replay


def listing():
    dirs = sess.find()
    loose = racelog.find()
    if not dirs and not loose:
        print("nothing stored in %s" % racelog.RACES)
        print("record some with:  sudo mk/bin/python3 -m tools.track")
        return
    for d in dirs:
        s = sess.Session(d)
        print("%-36s %2d races  %s" % (os.path.basename(d), len(s),
                                       s.meta.get("started", "")))
        for race, row in zip(s.races, s.meta.get("races", [])):
            print("     %2d  %-22s %4d events  %6.1f kB  you P%s"
                  % (row["n"], race.course_name, len(race),
                     os.path.getsize(race.path) / 1024.0,
                     row.get("your_position")))
    for p in loose:
        log = racelog.RaceLog(p)
        print("%-36s %-22s %4d events  %6.1f kB"
              % (os.path.basename(p), log.course_name, len(log),
                 os.path.getsize(p) / 1024.0))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if "--list" in flags:
        return listing()

    which = args[0] if args else ""
    dirs = sess.find(which=which)
    if not dirs:
        # fall back to a loose race file, which is what `replay_live --save`
        # writes when there is no session
        loose = racelog.find(which=which)
        if not loose:
            return listing()
        print(render(racelog.RaceLog(loose[-1] if not which else loose[0]),
                     quiet="--all" not in flags))
        return

    s = sess.Session(dirs[-1] if not which else dirs[0])
    if len(args) < 2:
        print(render_session(s))
        return

    n = int(args[1])
    race = next((r, row) for r, row in zip(s.races, s.meta["races"])
                if row["n"] == n)[0]
    if "--replay" in flags:
        print(render_replay(race))
    else:
        print(render(race, quiet="--all" not in flags))


if __name__ == "__main__":
    main()
