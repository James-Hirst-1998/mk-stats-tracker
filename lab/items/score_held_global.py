#!/usr/bin/env python3
"""
Offline: score EVERY byte in memory against the video, instead of intersecting.

find_item_from_video.py required a byte to match the video at every sampled
frame. One frame off by a fifth of a second kills the true answer, and that is
almost certainly what happened - the strict search survived down to noise while
the real field was eliminated by a single transition-adjacent sample.

So score instead of filter. For each byte, count the fraction of sampled frames
where "differs from its resting value" agrees with "the item box is on screen".
The held item should score near 1.0; nothing else has any reason to.

Frames within GUARD of a box transition are skipped, so small misalignment
between video and memory costs nothing.

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.score_held_global [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, FPS, VIDEO_OFFSET

STEP = 5
GUARD = 0.6            # seconds to stay clear of a box appear/disappear
TOP = 40


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
        print("no .mov alongside %s" % os.path.basename(path))
        return
    cache = os.path.join(os.path.dirname(__file__), "cache", os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    raw = os.path.join(cache, "itembox.raw")
    extract(movs[0], raw)
    held = held_series(raw)

    # Mark frames too close to a transition to trust.
    trans = np.zeros(len(held), dtype=bool)
    edges = np.nonzero(np.diff(held.astype(np.int8)) != 0)[0]
    g = int(GUARD * FPS)
    for e in edges:
        trans[max(0, e - g):min(len(held), e + g + 1)] = True
    print("video: %d frames, box up %.0f%% of the time, %d transitions"
          % (len(held), 100 * held.mean(), len(edges)), flush=True)

    s = Session(path)
    # Map each memory frame to a video frame.
    want = {}
    for i, e in enumerate(s.index):
        if i % STEP or e["position"] is None:
            continue
        vf = int(round((e["mono"] - VIDEO_OFFSET) * FPS))
        if 0 <= vf < len(held) and not trans[vf]:
            want[i] = bool(held[vf])
    n_up = sum(1 for v in want.values() if v)
    print("memory: %d clean frames (%d box-up, %d box-down)"
          % (len(want), n_up, len(want) - n_up), flush=True)
    if n_up < 20 or len(want) - n_up < 20:
        print("not enough clean frames")
        return

    n = capfmt.image_size(s.regions)
    rest = None
    agree = np.zeros(n, dtype=np.uint16)
    done = 0
    for i, img in s.frames(stop=max(want) + 1):
        state = want.get(i)
        if state is None:
            continue
        if rest is None:
            if state:
                continue                      # need a box-down frame first
            rest = img.copy()
        ne = img != rest
        if state:
            agree += ne
        else:
            agree += ~ne
        done += 1
        if done % 100 == 0:
            print("   %d/%d frames scored" % (done, len(want)), flush=True)

    print("%d frames scored" % done, flush=True)
    frac = agree.astype(np.float32) / done
    order = np.argsort(-frac)[:TOP]
    print("\n%-12s %-8s %s" % ("address", "agree", "resting value"))
    for j in order:
        addr = capfmt.index_to_addr(int(j), s.regions)
        print("%-12s %6.1f%%   %d" % (hex(addr), 100 * frac[j], int(rest[j])))
    np.save(os.path.join(cache, "held_agreement.npy"), frac)
    print("\nsaved per-byte scores to %s"
          % os.path.join(cache, "held_agreement.npy"))


if __name__ == "__main__":
    main()
