#!/usr/bin/env python3
"""
Offline: find the held-item byte using the screen recording as ground truth.

Label-free searches for items kept returning artefacts, because "holds an item"
has no distinctive shape in memory on its own. The video does have it: Mario
Kart Wii only draws the item box while you are holding something, and the box
has a bright yellow left border at a fixed screen position that is the same
whatever item is inside.

  1. ffmpeg crops the item-box region at the memory capture rate
  2. count yellow pixels in the left border -> item held / not held, per frame
  3. sample memory frames well inside held and not-held runs
  4. keep bytes that equal one constant value on every not-held sample and
     differ from it on every held sample

Step 4 is the same trace-match that cut 48M candidates to 5 for position.

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.find_item_from_video [recording-substring]
"""

import glob
import os
import subprocess
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

# Item box crop in source pixels, and the border strip inside the 96x96 scale.
CROP = "200:200:80:405"
SCALE = 96
BORDER_X = slice(8, 14)
BORDER_Y = slice(10, 79)
BORDER_MIN = 12

FPS = 20
# Recorder elapsed minus video timestamp, read off the terminal visible in the
# recording (99.3s at video t=90, 29.7s at t=20). The status line only updates
# about once a second, so treat this as +/-0.5s and keep a guard band.
VIDEO_OFFSET = 10.2
GUARD = 1.5                    # stay this far inside a run before sampling
N_SAMPLES = 14


def extract(mov, out):
    if os.path.exists(out):
        return
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", mov, "-vf",
         "crop=%s,fps=%d,scale=%d:%d,format=rgb24" % (CROP, FPS, SCALE, SCALE),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-y", out],
        check=True, env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ["PATH"]})


def held_series(raw_path):
    raw = np.fromfile(raw_path, dtype=np.uint8)
    n = raw.size // (SCALE * SCALE * 3)
    x = raw[: n * SCALE * SCALE * 3].reshape(n, SCALE, SCALE, 3).astype(np.int16)
    R, G, B = x[..., 0], x[..., 1], x[..., 2]
    yellow = (R > 150) & (G > 140) & (B < 110) & ((R - B) > 90) & ((G - B) > 80)
    border = yellow[:, BORDER_Y, BORDER_X].reshape(n, -1).sum(axis=1)
    held = border > BORDER_MIN
    # close sub-quarter-second dropouts
    for i in range(1, n - 1):
        if not held[i] and held[max(0, i - 5):i].any() and held[i + 1:i + 6].any():
            held[i] = True
    return held


def runs_of(held):
    out, start = [], 0
    for i in range(1, len(held) + 1):
        if i == len(held) or held[i] != held[start]:
            out.append((bool(held[start]), start / FPS, i / FPS))
            start = i
    return out


def pick_samples(s, held):
    """Memory frame indices deep inside held / not-held video runs."""
    runs = [r for r in runs_of(held) if r[2] - r[1] >= 2 * GUARD + 0.5]
    want = {True: [], False: []}
    for state, a, b in runs:
        want[state].append((a + GUARD, b - GUARD))
    picks = {True: [], False: []}
    for state, spans in want.items():
        if not spans:
            continue
        step = max(1, len(spans) // N_SAMPLES)
        for a, b in spans[::step][:N_SAMPLES]:
            mid_video = (a + b) / 2
            mono = mid_video + VIDEO_OFFSET
            best, bd = None, 1e9
            for i, e in enumerate(s.index):
                if e["position"] is None:
                    continue
                d = abs(e["mono"] - mono)
                if d < bd:
                    best, bd = i, d
            if best is not None and bd < 0.5:
                picks[state].append(best)
    return picks


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

    movs = glob.glob(os.path.join(path, "*.mov"))
    if not movs:
        print("no .mov in %s" % path)
        return
    # Recordings are written under sudo and owned by root, so derived files go
    # in a cache directory we own.
    cache = os.path.join(os.path.dirname(__file__), "cache", os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    raw_path = os.path.join(cache, "itembox.raw")
    print("extracting item box from %s" % os.path.basename(movs[0]), flush=True)
    extract(movs[0], raw_path)

    held = held_series(raw_path)
    rs = [r for r in runs_of(held) if r[2] - r[1] >= 0.5]
    print("video: %d frames, holding an item %.0f%% of the race, %d runs >=0.5s"
          % (len(held), 100 * held.mean(), len(rs)))

    s = Session(path)
    picks = pick_samples(s, held)
    print("memory samples: %d held, %d empty"
          % (len(picks[True]), len(picks[False])), flush=True)
    if len(picks[True]) < 4 or len(picks[False]) < 4:
        print("not enough clean runs to match against")
        return

    order = ([(i, False) for i in picks[False]] + [(i, True) for i in picks[True]])
    order.sort()
    mask = None
    empty_val = None
    for i, img in s.frames(stop=max(o[0] for o in order) + 1):
        states = [st for j, st in order if j == i]
        if not states:
            continue
        state = states[0]
        if not state and empty_val is None:
            empty_val = img.copy()
            mask = np.ones(img.size, dtype=bool)
            continue
        if mask is None:
            continue
        mask &= (img == empty_val) if not state else (img != empty_val)
        print("   after %s sample f%d: %d survivors"
              % ("empty" if not state else "held ", i, int(mask.sum())), flush=True)

    surv = np.nonzero(mask)[0]
    print("\n%d bytes are one fixed value whenever the box is absent and always "
          "something else when it is present:" % surv.size)
    for idx in surv[:60]:
        addr = capfmt.index_to_addr(int(idx), s.regions)
        print("    %s  empty value = %d" % (hex(addr), int(empty_val[idx])))
    if surv.size:
        np.save(os.path.join(cache, "item_candidates.npy"), surv)
        print("\nsaved candidates to %s" % os.path.join(cache, "item_candidates.npy"))


if __name__ == "__main__":
    main()
