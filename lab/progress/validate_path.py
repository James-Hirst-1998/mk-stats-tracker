#!/usr/bin/env python3
"""
Offline: validate the candidate stable path to the per-player array against
every frame of every recording, and dump the fields it reaches.

Candidate path (from find_stable_path.py):
    array_base = u32(0x809bd730) + 0x140
    12 players, stride 0xc4, local player at slot 0

A frame passes if the 12 position bytes are a permutation of 1..12 AND slot 0
matches the position that was read live at capture time. Frames before the race
starts are expected to fail and are reported separately, not counted against it.

Run (no sudo):
  mk/bin/python3 -m lab.progress.validate_path
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PATH_PTR = 0x809BD730
PATH_DELTA = 0x140
STRIDE = 0xC4
N_PLAYERS = 12
LOCAL_SLOT = 0
STEP = 25

OFF_POSITION = 0x000
OFF_LAP = 0x006
OFF_PROGRESS = 0x0B0          # float, laps completed
OFF_LAP_FRAC = 0x0BC          # float, fraction through current lap


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def be_f32(img, i):
    return float(np.frombuffer(img[i:i + 4].tobytes(), dtype=">f4")[0])


def check(path):
    s = Session(path)
    name = os.path.basename(path)
    ptr_i = capfmt.addr_to_index(PATH_PTR, s.regions)
    if ptr_i is None:
        print("%s: %s not inside recorded regions" % (name, hex(PATH_PTR)))
        return None

    target = set(range(1, N_PLAYERS + 1))
    in_race = ok = bad = pre_race = 0
    bases = set()
    timeline = []

    for i, img in s.frames(step=STEP):
        live_pos = s.index[i]["position"]
        base = be_u32(img, ptr_i) + PATH_DELTA
        bi = capfmt.addr_to_index(base, s.regions)
        if bi is None or bi + N_PLAYERS * STRIDE > img.size:
            if live_pos is None:
                pre_race += 1
            else:
                bad += 1
            continue

        block = img[bi:bi + N_PLAYERS * STRIDE].reshape(N_PLAYERS, STRIDE)
        pos = [int(v) for v in block[:, OFF_POSITION]]
        valid = set(pos) == target and pos[LOCAL_SLOT] == live_pos

        if live_pos is None:
            pre_race += 1
            continue
        in_race += 1
        if valid:
            ok += 1
            bases.add(base)
        else:
            bad += 1

        if len(timeline) < 14 and i % (STEP * 8) == 0:
            laps = [int(v) for v in block[:, OFF_LAP]]
            prog = [round(be_f32(img, bi + p * STRIDE + OFF_PROGRESS), 2)
                    for p in range(N_PLAYERS)]
            timeline.append((i, pos, laps, prog))

    print("=" * 78)
    print("%s (course 0x%02x)" % (name, s.index[0]["course"]))
    print("  in-race frames checked: %d, passed %d, failed %d (pre-race skipped: %d)"
          % (in_race, ok, bad, pre_race))
    print("  array base resolved to: %s" % sorted(hex(b) for b in bases))
    for i, pos, laps, prog in timeline[:6]:
        print("    f%-5d pos=%s" % (i, pos))
        print("           lap=%s" % laps)
        print("           progress=%s" % prog)
    return ok, bad, in_race


def main():
    root = RECORDINGS
    total_ok = total_bad = 0
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        r = check(d)
        if r:
            total_ok += r[0]
            total_bad += r[1]
    print("=" * 78)
    print("TOTAL: %d/%d in-race frames pass across all recordings"
          % (total_ok, total_ok + total_bad))
    if total_bad == 0 and total_ok:
        print("Path holds everywhere:  array = u32(0x809bd730) + 0x140")
    else:
        print("Path fails on %d frames; not ready to promote." % total_bad)


if __name__ == "__main__":
    main()
