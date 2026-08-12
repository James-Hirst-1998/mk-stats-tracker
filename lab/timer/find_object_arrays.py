#!/usr/bin/env python3
"""
Offline: find every 12-element object array in a recording, by looking for a
static (non-heap) pointer repeated 12 times at a constant stride.

The per-player race struct was found this way after the fact: its vtable
0x808b2d44 sits at +0x54 of each of 12 entries spaced 0xc4 apart. Any other
per-player object - item inventory, kart physics, damage state - has the same
shape, so this enumerates them all in one pass without needing labels.

For each array found it then reports which byte offsets look like item IDs:
values within 0..20, identical for every player on the starting grid, and
changing several times during the race.

Run (no sudo):
  mk/bin/python3 -m lab.timer.find_object_arrays
"""

import glob
import os
from collections import Counter

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

N_PLAYERS = 12
HEAP_START = 0x81000000       # below this is static code/data on this build
MIN_COUNT, MAX_COUNT = N_PLAYERS, 200
MID = 0.6
SAMPLE_STEP = 10
ITEM_MAX = 20                 # Tockdom item ids run 0..20, 20 = empty


def aligned_words(img):
    n = (img.size // 4) * 4
    return np.frombuffer(img[:n].tobytes(), dtype=">u4")


def find_arrays(img, regions):
    """[(vtable, stride, first_addr, slot_offset)] for 12-element arrays."""
    words = aligned_words(img)
    static = (words >= 0x80000000) & (words < HEAP_START)
    idx = np.nonzero(static)[0]
    vals = words[idx]

    counts = Counter(vals.tolist())
    out = []
    for v, c in counts.items():
        if not (MIN_COUNT <= c <= MAX_COUNT):
            continue
        positions = np.sort(idx[vals == v]) * 4
        diffs = np.diff(positions)
        if diffs.size == 0:
            continue
        for stride in {int(d) for d in diffs if 4 <= d <= 0x4000}:
            run, start = 1, 0
            for i in range(len(positions) - 1):
                if positions[i + 1] - positions[i] == stride:
                    run += 1
                    if run >= N_PLAYERS:
                        break
                else:
                    run, start = 1, i + 1
            if run >= N_PLAYERS:
                first = int(positions[start])
                out.append((int(v), stride, first))
                break
    return out


def item_like(s, first_index, stride, frames_data, start_block):
    """Byte offsets that behave like a held-item id."""
    hits = []
    n = frames_data.shape[0]
    for off in range(stride):
        col = frames_data[:, :, off].astype(np.int64)
        if col.max() > ITEM_MAX:
            continue
        if len(set(start_block[:, off].tolist())) != 1:
            continue                       # all players equal on the grid
        changes = int((np.diff(col, axis=0) != 0).sum())
        if changes < N_PLAYERS:
            continue
        hits.append((off, int(start_block[0, off]), changes,
                     sorted(set(col.ravel().tolist()))))
    return hits


def analyse(path):
    s = Session(path)
    name = os.path.basename(path)
    target = int(len(s) * MID)

    img = None
    for i, frame in s.frames(stop=target + 1):
        if i == target:
            img = frame.copy()

    arrays = find_arrays(img, s.regions)
    print("=" * 78)
    print("%s: %d twelve-element object arrays" % (name, len(arrays)))

    # Collect the whole race once, for every array at once.
    spans = []
    for vt, stride, first in arrays:
        base = first - (first % 4)
        spans.append((vt, stride, base))

    collected = {k: [] for k in range(len(spans))}
    start_blocks = {}
    for i, frame in s.frames(step=SAMPLE_STEP):
        for k, (vt, stride, base) in enumerate(spans):
            end = base + N_PLAYERS * stride
            if end > frame.size:
                continue
            blk = frame[base:end].reshape(N_PLAYERS, stride)
            collected[k].append(blk.copy())
            if i == 0:
                start_blocks[k] = blk.copy()

    for k, (vt, stride, base) in enumerate(spans):
        if k not in start_blocks or not collected[k]:
            continue
        data = np.stack(collected[k])
        addr = capfmt.index_to_addr(base, s.regions)
        hits = item_like(s, base, stride, data, start_blocks[k])
        marker = "  <- player race struct" if stride == 0xC4 else ""
        print("\n  vtable 0x%08x  stride 0x%-5x first %s%s"
              % (vt, stride, hex(addr), marker))
        if not hits:
            print("      no item-like offsets")
            continue
        for off, grid, changes, values in hits[:8]:
            print("      +0x%03x  grid=%-3d changes=%-5d values=%s"
                  % (off, grid, changes, values[:24]))
    return arrays


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    # The frantic race has the most item activity; do it first.
    dirs.sort(key=lambda d: "frantic" not in d)
    for d in dirs[:2]:
        analyse(d)


if __name__ == "__main__":
    main()
