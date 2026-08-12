#!/usr/bin/env python3
"""Offline: disassemble the item collision loop out of a recording.

`docs/MEMORY_MAP.md` says the live item objects hang off `ItemDirector + 0x264`
and that at most three were ever seen alive at once, which is low enough to
suspect the array shape is wrong. The game's own loop settles it.

Run (no sudo):
  mk/bin/python3 -m lab.items.read_collision_code [recording-substring] [addr]
"""

import glob
import os
import sys

from lab import ppc
from mkw.capture.session import Session, RECORDINGS

COLLISION_LOOP = 0x805725E8


def pick(which=""):
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    return dirs[0] if dirs else None


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    start = int(sys.argv[2], 16) if len(sys.argv) > 2 else COLLISION_LOOP - 0x80
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 96
    path = pick(which)
    if path is None:
        print("no recording matching %r" % which)
        return
    s = Session(path)
    print("%s\n" % os.path.basename(path))
    ppc.show(ppc.from_session(s), start, count, mark={COLLISION_LOOP})


if __name__ == "__main__":
    main()
