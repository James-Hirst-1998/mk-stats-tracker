#!/usr/bin/env python3
"""
Offline: characterise every byte of the corrected 0xc4 player struct.

Now that the array base is known to be u32(0x809bd730) + 0x12c, dump the whole
struct for every racer over a race and describe each offset: how often it
changes, its alphabet, and whether it reads as a plausible timer or counter.
This is how lap splits and finish times get found without guessing.

Run (no sudo):
  mk/bin/python3 -m lab.progress.dump_player_struct [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x12C
STRIDE = 0xC4
N_PLAYERS = 12
OFF_POSITION = 0x014
OFF_LAP = 0x01A
STEP = 5


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


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
    pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)

    rows = []
    times = []
    laps = []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
        if bi is None:
            continue
        blk = img[bi:bi + STRIDE * N_PLAYERS]
        pos = [int(blk[p * STRIDE + OFF_POSITION]) for p in range(N_PLAYERS)]
        if sorted(pos) != list(range(1, N_PLAYERS + 1)):
            continue
        rows.append(blk.copy())
        times.append(s.index[i]["mono"])
        laps.append([int(blk[p * STRIDE + OFF_LAP]) for p in range(N_PLAYERS)])

    if not rows:
        print("no usable frames")
        return
    a = np.stack(rows)                       # (frames, 12*0xc4)
    t = np.array(times) - times[0]
    laps = np.array(laps)
    print("%s: %d frames over %.1fs\n" % (os.path.basename(dirs[0]), len(a), t[-1]))

    print("%-7s %-8s %-26s %s" % ("offset", "changes", "alphabet (slot 0)", "note"))
    for o in range(STRIDE):
        col = a[:, o]
        vals = np.unique(col)
        ch = int((np.diff(col.astype(np.int16)) != 0).sum())
        if ch == 0:
            continue
        note = ""
        if o % 4 == 0 and o + 4 <= STRIDE:
            w = np.frombuffer(np.ascontiguousarray(
                a[:, o:o + 4]).tobytes(), dtype=">u4")
            f = np.frombuffer(np.ascontiguousarray(
                a[:, o:o + 4]).tobytes(), dtype=">f4")
            d = np.diff(w.astype(np.int64))
            if len(d) and (d > 0).mean() > 0.95 and d.max() < 64:
                note = "u32 counter +%.2f/frame" % d.mean()
            elif np.isfinite(f).all() and 0 <= np.nanmin(f) and np.nanmax(f) < 1e4:
                fd = np.diff(f)
                if (fd >= -1e-4).mean() > 0.95:
                    note = "f32 rising %.3f..%.3f" % (f.min(), f.max())
        show = vals[:12]
        print("+0x%03x %-8d %-26s %s"
              % (o, ch, " ".join("%d" % v for v in show)
                 + (" ..." if vals.size > 12 else ""), note))

    lap_change = np.nonzero(np.diff(laps[:, 0]) != 0)[0] + 1
    print("\nslot 0 lap changes at frames %s (t=%s)"
          % (list(lap_change), ["%.1f" % t[k] for k in lap_change]))


if __name__ == "__main__":
    main()
