#!/usr/bin/env python3
"""Offline: find the game's own reads of RaceConfig, to label the fields.

Two columns in the per-player struct look like ids and the data alone cannot
say which is the character: both are byte-sized, fixed for the race and mostly
distinct between racers. The game's code can say, so find it.

`*(0x809BD728)` is loaded as `lis rA,0x809c; lwz rD,-10456(rA)`, and -10456 is
0xD728, so every read of it is an `lwz` with that immediate. Each hit gets
disassembled with its neighbours; the ones that go on to `mulli rX,rY,240` are
indexing the player array, and the offset they load next names the field.

Run (no sudo):
  mk/bin/python3 -m lab.players.find_config_readers [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from lab import ppc
from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

CODE = (0x80004000, 0x80800000)
CONFIG_LOW = 0xD728             # low half of 0x809BD728, as an lwz immediate
BEFORE, AFTER = 3, 14


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    frame = len(s) // 2
    read = ppc.from_session(s, frame)
    img = s.frame(frame)

    a0 = capfmt.addr_to_index(CODE[0], s.regions)
    a1 = capfmt.addr_to_index(CODE[1], s.regions)
    words = img[a0:a1].view(">u4")
    # lwz is primary opcode 32, so the top 6 bits are 0b100000
    hit = ((words >> 26) == 32) & ((words & 0xFFFF) == CONFIG_LOW)
    sites = CODE[0] + np.nonzero(hit)[0] * 4
    print("%s\n%d reads of *(0x809BD728) in code\n"
          % (os.path.basename(dirs[0]), len(sites)))

    for addr in sites:
        addr = int(addr)
        block = ppc.block(read, addr - BEFORE * 4, BEFORE + AFTER)
        text = [t for _, _, t in block]
        if not any("mulli" in t and t.rstrip().endswith("240") for t in text):
            continue
        print("--- 0x%08x" % addr)
        for a, w, t in block:
            print("    %s0x%08x  %08x  %s"
                  % ("*" if a == addr else " ", a, w, t))
        print()


if __name__ == "__main__":
    main()
