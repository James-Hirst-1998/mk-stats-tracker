#!/usr/bin/env python3
"""Offline: what damage type does each item object type produce?

The collision loop computes the damage type from the OBJECT type:

    lwz r0,4(r31)          object type
    mulli r0,r0,12
    add r12,r27,r0         r27 = 0x808B5468
    bl 0x80021450          member-pointer call -> damage type in r3

so disassembling each table entry's function says exactly which object types
can produce a given damage type. That turns "knockback" into a short list -
which shells, which box - without a single byte being scored.

Run (no sudo):
  mk/bin/python3 -m lab.items.read_damage_handlers [recording-substring]
"""

import glob
import os
import sys

from lab import ppc
from mkw.capture.session import Session, RECORDINGS

HANDLER_TABLE = 0x808B5468
STRIDE = 0x0C
N_TYPES = 15


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    read = ppc.from_session(s, len(s) // 2)
    print("%s\n" % os.path.basename(dirs[0]))

    for t in range(N_TYPES):
        e = HANDLER_TABLE + t * STRIDE
        delta, voff, func = read(e), read(e + 4), read(e + 8)
        print("type %-2d  descriptor %08x %08x %08x" % (t, delta, voff, func))
        if not (0x80000000 <= func < 0x81800000):
            print("        (not a direct function pointer)")
            continue
        for addr, word, text in ppc.block(read, func, 12):
            print("        0x%08x  %08x  %s" % (addr, word, text))
            if text.startswith("blr"):
                break
        print()


if __name__ == "__main__":
    main()
