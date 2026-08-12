#!/usr/bin/env python3
"""
Offline: score every byte against "carrying a committed item".

score_held_global.py used "item box drawn" as the target and topped out at HUD
animation floats. That target was wrong. Extracted frames show the box is drawn
throughout the roulette as well - it cycles through random icons for ~3.5s
before settling - and during that spin the inventory is still empty. So the
real field disagrees with "box drawn" on roughly a quarter of the race and
lands below the noise floor.

The correct target is: box drawn AND the roulette has finished. The roulette is
known exactly from the item array's +0x004, which is non-empty precisely while
the spin is running. Frames inside the spin are dropped entirely rather than
labelled, so nothing hinges on when exactly the commit happens.

Requires ffmpeg. Run (no sudo):
  mk/bin/python3 -m lab.items.score_held_committed [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.items.find_item_from_video import extract, held_series, FPS, VIDEO_OFFSET

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
OFF_ANNOUNCE = 0x004
EMPTY = 20
STEP = 3
GUARD = 0.8
TOP = 50


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

    trans = np.zeros(len(held), dtype=bool)
    g = int(GUARD * FPS)
    for e in np.nonzero(np.diff(held.astype(np.int8)) != 0)[0]:
        trans[max(0, e - g):min(len(held), e + g + 1)] = True

    s = Session(path)
    ip = capfmt.addr_to_index(ITEM_PTR, s.regions)

    # Pass 1: label each memory frame carrying / empty / drop.
    label = {}
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, ip) + ITEM_DELTA, s.regions)
        if bi is None:
            continue
        ann = int(img[bi + OFF_ANNOUNCE])
        if ann != EMPTY:
            continue                       # roulette spinning: drop the frame
        vf = int(round((s.index[i]["mono"] - VIDEO_OFFSET) * FPS))
        if not (0 <= vf < len(held)) or trans[vf]:
            continue
        if i % STEP == 0:
            label[i] = bool(held[vf])
    n_hold = sum(1 for v in label.values() if v)
    print("labels: %d carrying, %d empty (roulette frames dropped)"
          % (n_hold, len(label) - n_hold), flush=True)
    if n_hold < 15 or len(label) - n_hold < 15:
        print("not enough labelled frames")
        return

    n = capfmt.image_size(s.regions)
    rest = None
    agree = np.zeros(n, dtype=np.uint16)
    done = 0
    for i, img in s.frames(stop=max(label) + 1):
        st = label.get(i)
        if st is None:
            continue
        if rest is None:
            if st:
                continue
            rest = img.copy()
        ne = img != rest
        agree += ne if st else ~ne
        done += 1
        if done % 200 == 0:
            print("   %d/%d" % (done, len(label)), flush=True)

    frac = agree.astype(np.float32) / done
    order = np.argsort(-frac)[:TOP]
    print("\n%-12s %-8s %s" % ("address", "agree", "resting value"))
    for j in order:
        print("%-12s %6.1f%%   %d"
              % (hex(capfmt.index_to_addr(int(j), s.regions)),
                 100 * frac[j], int(rest[j])))
    np.save(os.path.join(cache, "committed_agreement.npy"), frac)
    print("\nsaved to %s" % os.path.join(cache, "committed_agreement.npy"))


if __name__ == "__main__":
    main()
