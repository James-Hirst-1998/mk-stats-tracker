#!/usr/bin/env python3
"""Print a stored race back out. No Dolphin, no recording, no sudo.

    python3 -m tools.report                 the most recent race
    python3 -m tools.report peach           the first one matching
    python3 -m tools.report --list          what is stored
    python3 -m tools.report peach --all     including the position swaps

Everything printed here is rebuilt from the events file. If a number cannot
be produced from it, the event stream is missing something - which is the
check this tool exists to make.
"""

import os
import sys

from mkw import racelog
from mkw.report import render


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    paths = racelog.find(which=args[0] if args else "")

    if "--list" in flags or not paths:
        if not paths:
            print("no stored races in %s" % racelog.RACES)
            return
        for p in paths:
            log = racelog.RaceLog(p)
            print("%-44s %-22s %4d events  %5.1f kB"
                  % (os.path.basename(p), log.course_name, len(log),
                     os.path.getsize(p) / 1024.0))
        return

    log = racelog.RaceLog(paths[-1] if not args else paths[0])
    print(render(log, quiet="--all" not in flags))


if __name__ == "__main__":
    main()
