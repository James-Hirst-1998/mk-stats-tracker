#!/usr/bin/env python3
"""Offline: can a Blue Shell be told from a Bob-omb?

Both write damage type 7, so the damage field alone says "launched" and no
more. The item field can settle it: a Blue Shell is item 7 and a Bob-omb is
item 6, and the two behave differently in flight - a Blue Shell takes several
seconds to reach the leader and only ever hits the racer in first, while a
Bob-omb goes off near whoever dropped it.

This checks, for every damage-7 event across every recording, which of the two
was used beforehand and how long the gap was, so the naming rule is measured
rather than assumed.

Run (no sudo):
  mk/bin/python3 -m analysis.name_blue_shell
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from analysis.validate_damage import read, spans, N_PLAYERS
from analysis.cross_check_damage import read_held, uses

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x120
PLAYER_STRIDE = 0xC4
OFF_POSITION = 0x20
BLUE, BOMB = 7, 6
LAUNCHED = 7
WINDOW = 15.0


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def read_positions(s):
    pos = np.zeros((len(s), N_PLAYERS), dtype=np.int16)
    pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
        if bi is None:
            continue
        p = [int(img[bi + k * PLAYER_STRIDE + OFF_POSITION])
             for k in range(N_PLAYERS)]
        if sorted(p) == list(range(1, N_PLAYERS + 1)):
            pos[i] = p
    return pos


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]

    rows = []
    for d in dirs:
        s = Session(d)
        t, dmg, last, prio = read(s)
        if np.all(np.isnan(t)):
            continue
        used = uses(t, read_held(s))
        pos = read_positions(s)
        t0 = np.nanmin(t)
        for k in range(N_PLAYERS):
            for st, dur, v in spans(t, dmg[:, k]):
                if v != LAUNCHED:
                    continue
                i = int(np.nanargmin(np.abs(t - st)))
                cand = [(st - u[0], u[1], u[2]) for u in used
                        if u[2] in (BLUE, BOMB) and st - WINDOW <= u[0] <= st + 0.5]
                rows.append((os.path.basename(d), st - t0, k, int(pos[i, k]),
                             dur, cand))

    print("%d 'launched' hits across %d recordings\n" % (len(rows), len(dirs)))
    print("%-38s %7s %5s %4s %5s  %s"
          % ("recording", "at", "slot", "pos", "dur", "blue/bomb used before"))
    for name, at, k, p, dur, cand in rows:
        txt = ", ".join("%s %.1fs ago by slot %d"
                        % ("BLUE" if it == BLUE else "bomb", gap, who)
                        for gap, who, it in cand[:3]) or "-"
        print("%-38s %6.1fs %5d %4d %5.1f  %s"
              % (name[:38], at, k, p, dur, txt))

    # How well does "in P1 and a Blue Shell went off 3-12s ago" work?
    blue = [r for r in rows if r[3] == 1
            and any(3.0 <= g <= 12.0 and it == BLUE for g, _, it in r[5])]
    bomb = [r for r in rows
            if any(g <= 3.0 and it == BOMB for g, _, it in r[5])]
    print("\n%d of %d launched hits look like a Blue Shell (victim in P1, a "
          "Blue Shell used 3-12s earlier)" % (len(blue), len(rows)))
    print("%d look like a Bob-omb (a Bob-omb used within 3s)" % len(bomb))


if __name__ == "__main__":
    main()
