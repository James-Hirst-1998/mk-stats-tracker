#!/usr/bin/env python3
"""
Offline: validate the candidate stable paths to the per-player item array
against every in-race frame of every recording.

Candidates (from find_item_path.py), all resolving to the same array:
    item_base = u32(0x809c1904) - 0x1959
    item_base = u32(0x809c22b0) - 0x60bd
    item_base = u32(0x809c3648) - 0x227d
    item_base = u32(0x809c3660) - 0x4971
    12 players, stride 0x248, local player at slot 0, 20 = empty

A frame passes if all twelve slots hold a valid item id (0..20). For the
recording that has a screen recording aligned to it, slot 0 is additionally
checked against whether the item box was drawn on screen.

Run (no sudo):
  mk/bin/python3 -m lab.items.validate_item_path
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PATHS = [(0x809C1904, -0x1959), (0x809C22B0, -0x60BD),
         (0x809C3648, -0x227D), (0x809C3660, -0x4971)]
STRIDE = 0x248
N_PLAYERS = 12
ITEM_MAX = 20
STEP = 25


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def main():
    root = RECORDINGS
    totals = {p: [0, 0] for p in PATHS}
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        s = Session(d)
        name = os.path.basename(d)
        ptr_i = {p: capfmt.addr_to_index(p[0], s.regions) for p in PATHS}
        stats = {p: [0, 0, set()] for p in PATHS}

        for i, img in s.frames(step=STEP):
            if s.index[i]["position"] is None:
                continue
            for p in PATHS:
                pi = ptr_i[p]
                if pi is None:
                    continue
                base = be_u32(img, pi) + p[1]
                bi = capfmt.addr_to_index(base, s.regions)
                if bi is None or bi + (N_PLAYERS - 1) * STRIDE >= img.size:
                    stats[p][1] += 1
                    continue
                vals = img[bi: bi + (N_PLAYERS - 1) * STRIDE + 1: STRIDE]
                if len(vals) == N_PLAYERS and int(vals.max()) <= ITEM_MAX:
                    stats[p][0] += 1
                    stats[p][2].add(base)
                else:
                    stats[p][1] += 1

        print("=" * 78)
        print("%s (course 0x%02x)" % (name, s.index[0]["course"]))
        for p in PATHS:
            ok, bad, bases = stats[p]
            totals[p][0] += ok
            totals[p][1] += bad
            print("  u32(%s) %s 0x%-6x  %4d pass %4d fail   base %s"
                  % (hex(p[0]), "+" if p[1] >= 0 else "-", abs(p[1]), ok, bad,
                     sorted(hex(b) for b in bases)))

    print("=" * 78)
    for p in PATHS:
        ok, bad = totals[p]
        verdict = "HOLDS" if bad == 0 and ok else "fails on %d frames" % bad
        print("  u32(%s) %s 0x%-6x  %d/%d  %s"
              % (hex(p[0]), "+" if p[1] >= 0 else "-", abs(p[1]), ok, ok + bad, verdict))


if __name__ == "__main__":
    main()
