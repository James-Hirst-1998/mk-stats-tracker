#!/usr/bin/env python3
"""
Offline: show when each candidate hit timer fires, so they can be named.

find_countdown_timers.py turns up twelve separately-allocated player objects,
each carrying the same five countdown fields at +0, +4, +0x38, +0x78, +0x7a
from the cluster start. Which is shock, ink, crush, mega or out-of-bounds is a
question about when they fire, not what shape they are.

The Lightning at 174.8s in the frantic recording is the test that settles it:
it strikes every racer at once, so whichever field fires for all twelve at that
moment is the shock timer. The rest are named by elimination and duration.

Run (no sudo):
  mk/bin/python3 -m lab.damage.trace_timers [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

CLUSTERS = [0x81139C84, 0x81149698, 0x81157F74, 0x811672F8, 0x811788D8,
            0x81188668, 0x8119733C, 0x811A4A0C, 0x811B3E90, 0x811C27F8,
            0x811D1548, 0x811EF486]
OFFSETS = [0x00, 0x04, 0x38, 0x78, 0x7A]
STEP = 2
MIN_FIRE = 0.3


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "frantic"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])

    addrs = [(c, o, c + o) for c in CLUSTERS for o in OFFSETS]
    idx = [capfmt.addr_to_index(a, s.regions) for _, _, a in addrs]
    rows, times = [], []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        rows.append([
            int(np.frombuffer(img[j:j + 2].tobytes(), dtype=">u2")[0])
            if j is not None else -1 for j in idx])
        times.append(s.index[i]["mono"])
    a = np.stack(rows)
    t = np.array(times)
    print("%s: %d samples over %.0fs\n"
          % (os.path.basename(dirs[0]), len(a), t[-1] - t[0]))

    for oi, off in enumerate(OFFSETS):
        print("=== +0x%02x ===" % off)
        fires_by_cluster = []
        for ci, c in enumerate(CLUSTERS):
            col = a[:, ci * len(OFFSETS) + oi]
            on = col > 0
            spans, start = [], None
            for k, v in enumerate(on):
                if v and start is None:
                    start = k
                elif not v and start is not None:
                    dur = t[k - 1] - t[start]
                    if dur >= MIN_FIRE:
                        spans.append((t[start] - t[0], dur, int(col[start])))
                    start = None
            fires_by_cluster.append(spans)
            print("  cluster %-2d %s x%-3d  %s"
                  % (ci, hex(c), len(spans),
                     "  ".join("%.0fs(%.1fs,v%d)" % x for x in spans[:8])))
        starts = [set(round(x[0]) for x in sp) for sp in fires_by_cluster]
        common = set.intersection(*starts) if all(starts) else set()
        print("  fires for ALL twelve at: %s\n" % (sorted(common) or "never"))


if __name__ == "__main__":
    main()
