#!/usr/bin/env python3
"""Offline: dump ItemDirector and follow anything that looks like a pool.

The item objects are not one array. `find_item_pool.py` shows a separate
constant-stride pool per item class - green shells at stride 0x1FC, red shells
at 0x310, bananas at 0x1B4 - so an object's address alone names its type. That
only covers the classes seen so far; the rest have to come from whatever table
ItemDirector keeps.

Run (no sudo):
  mk/bin/python3 -m lab.items.dump_item_director [recording-substring]
"""

import glob
import os
import sys

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import is_heap

ITEM_DIRECTOR = 0x809C3618


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    i = len(s) // 2
    director = s.u32(i, ITEM_DIRECTOR)
    print("%s\nItemDirector 0x%08x\n" % (os.path.basename(dirs[0]), director))

    print("%-8s %-10s %s" % ("offset", "word", "what it points at"))
    for off in range(0, 0x280, 4):
        v = s.u32(i, director + off)
        note = ""
        if is_heap(v):
            # A per-class manager should carry its own vtable and, a few words
            # in, the base of its pool.
            head = [s.u32(i, v + k * 4) for k in range(8)]
            note = "-> " + " ".join("%08x" % (h or 0) for h in head)
        elif v is not None and 0x80000000 <= v < 0x80900000:
            note = "(static)"
        print("+0x%03x   %08x   %s" % (off, v or 0, note))


if __name__ == "__main__":
    main()
