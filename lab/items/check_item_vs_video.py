#!/usr/bin/env python3
"""
Offline: put item-struct +0x004 next to the video and find where they disagree.

+0x004 (12 x 0x248, same array as the pickup register) is piecewise constant
with an item-id alphabet and its transitions line up with pickups. But it reads
non-empty only ~22% of the race while the item-box detector says the box is up
~48%. Exactly one of those is wrong, and guessing which has already cost time
on this project, so this dumps real frames at the disagreements to look at.

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.check_item_vs_video [recording-substring]
"""

import glob
import os
import subprocess
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, FPS, VIDEO_OFFSET

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
STRIDE = 0x248
OFF_HELD = 0x004
EMPTY = 20
STEP = 2
N_SHOTS = 12

NAMES = {0: "Green", 1: "Red", 2: "Banana", 3: "FakeBox", 4: "Mush",
         5: "3xMush", 6: "Bomb", 7: "Blue", 8: "Lightning", 9: "Star",
         10: "GoldMush", 11: "Mega", 12: "Blooper", 13: "POW", 14: "Cloud",
         15: "Bullet", 16: "3xGreen", 17: "3xRed", 18: "3xBanana",
         19: "?", 20: "-"}


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
    path = dirs[0]
    cache = os.path.join(os.path.dirname(__file__), "cache", os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    movs = glob.glob(os.path.join(path, "*.mov"))
    extract(movs[0], os.path.join(cache, "itembox.raw"))
    held = held_series(os.path.join(cache, "itembox.raw"))

    s = Session(path)
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)
    vt, val = [], []
    for i, img in s.frames(step=STEP):
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
        if bi is None:
            continue
        vt.append(s.index[i]["mono"] - VIDEO_OFFSET)      # in video seconds
        val.append(int(img[bi + OFF_HELD]))
    vt = np.array(vt)
    val = np.array(val)
    print("%s: %d memory samples, video seconds %.1f..%.1f"
          % (os.path.basename(path), len(vt), vt[0], vt[-1]))

    vf = np.round(vt * FPS).astype(int)
    ok = (vf >= 0) & (vf < len(held))
    vt, val, vf = vt[ok], val[ok], vf[ok]
    box = held[vf]
    mem = val != EMPTY

    print("memory says holding %4.1f%% of the time" % (100 * mem.mean()))
    print("video  says box up  %4.1f%% of the time" % (100 * box.mean()))
    print("they agree on       %4.1f%% of samples" % (100 * (mem == box).mean()))
    print("  box up,  memory empty: %4.1f%%" % (100 * (box & ~mem).mean()))
    print("  box down, memory item: %4.1f%%" % (100 * (~box & mem).mean()))

    # Longest stretches of "box up but memory says empty".
    bad = box & ~mem
    spans, start = [], None
    for i, b in enumerate(bad):
        if b and start is None:
            start = i
        elif not b and start is not None:
            spans.append((vt[i - 1] - vt[start], vt[start], vt[i - 1]))
            start = None
    spans.sort(reverse=True)
    print("\nlongest 'box up, memory empty' stretches (video seconds):")
    for d, a, b in spans[:8]:
        print("   %.1fs   %.1f -> %.1f" % (d, a, b))

    shots = os.path.join(cache, "disagree")
    os.makedirs(shots, exist_ok=True)
    picks = [(a + b) / 2 for d, a, b in spans[:N_SHOTS] if d > 1.0]
    for k, ts in enumerate(picks):
        out = os.path.join(shots, "t%06.1f.png" % ts)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.2f" % ts, "-i", movs[0],
             "-frames:v", "1", "-y", out], check=True,
            env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ["PATH"]})
    if picks:
        sheet = os.path.join(cache, "disagree_sheet.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-pattern_type", "glob", "-i",
             os.path.join(shots, "*.png"), "-filter_complex",
             "scale=480:-1,tile=3x%d" % ((len(picks) + 2) // 3), "-y", sheet],
            check=True,
            env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ["PATH"]})
        print("\ncontact sheet: %s" % sheet)


if __name__ == "__main__":
    main()
