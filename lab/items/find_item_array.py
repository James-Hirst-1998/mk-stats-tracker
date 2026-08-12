#!/usr/bin/env python3
"""
Offline: find the per-player held-item array without needing any labels.

find_object_arrays.py only finds arrays of objects carrying a vtable; an item
inventory is plain data, so this works from behaviour instead.

  1. one pass accumulating, for every byte: value on the starting grid, max,
     how many times it changed, and how often it sat at its grid value
  2. keep bytes that behave like a held item - never exceed 20 (Tockdom ids,
     20 = empty), change occasionally rather than constantly, and spend a good
     part of the race back at the grid value (holding nothing)
  3. among survivors, find runs of 12 in arithmetic progression that also share
     the same grid value - the shape of a 12-player inventory

Stage 3 gathers on the survivor set rather than scanning the image per stride,
so all strides from 1 upward are cheap. Stride 1 matters: a plain array of 12
item bytes is the most likely layout.

Run (no sudo):
  mk/bin/python3 -m lab.items.find_item_array
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

N_PLAYERS = 12
ITEM_MAX = 20
SAMPLE_STEP = 5
MIN_CHANGES = 10
MAX_CHANGES = 400
IDLE_MIN, IDLE_MAX = 0.15, 0.95    # fraction of frames back at the grid value
STRIDES = list(range(1, 0x200))
TRACE_FRAMES = 14


def scan(s):
    grid = vmax = nch = eq = prev = None
    n = 0
    for i, img in s.frames(step=SAMPLE_STEP):
        if s.index[i]["position"] is None:
            continue
        if grid is None:
            grid = img.copy()
            vmax = img.copy()
            nch = np.zeros(img.size, dtype=np.uint16)
            eq = np.zeros(img.size, dtype=np.uint16)
        else:
            np.maximum(vmax, img, out=vmax)
            nch += (img != prev)
        eq += (img == grid)
        prev = img.copy()
        n += 1
        if n % 100 == 0:
            print("    ...%d frames" % n, flush=True)
    return grid, vmax, nch, eq, n


def runs_of_twelve(mask, grid, size):
    cand = np.nonzero(mask)[0].astype(np.int64)
    print("  %d candidate bytes" % cand.size, flush=True)
    if not cand.size:
        return []
    found = []
    for stride in STRIDES:
        last = cand + (N_PLAYERS - 1) * stride
        keep = last < size
        c = cand[keep]
        if not c.size:
            continue
        acc = np.ones(c.size, dtype=bool)
        g0 = grid[c]
        for k in range(1, N_PLAYERS):
            o = c + k * stride
            acc &= mask[o]
            acc &= grid[o] == g0
            if not acc.any():
                break
        for base in c[acc]:
            found.append((int(base), stride, int(grid[base])))
    return found


def trace(s, base, stride, count=TRACE_FRAMES):
    step = max(1, len(s) // count)
    rows = []
    for i, img in s.frames(step=step):
        rows.append((i, [int(img[base + p * stride]) for p in range(N_PLAYERS)]))
    return rows


def analyse(path):
    s = Session(path)
    print("=" * 78)
    print(os.path.basename(path), flush=True)

    grid, vmax, nch, eq, n = scan(s)
    print("  scanned %d in-race frames" % n, flush=True)

    idle = eq.astype(np.float32) / max(n, 1)
    mask = ((vmax <= ITEM_MAX) & (nch >= MIN_CHANGES) & (nch <= MAX_CHANGES)
            & (idle >= IDLE_MIN) & (idle <= IDLE_MAX))

    hits = runs_of_twelve(mask, grid, grid.size)
    print("  %d twelve-slot arrays" % len(hits), flush=True)

    seen = set()
    for base, stride, gridval in sorted(hits, key=lambda h: (h[1], h[0])):
        addr = capfmt.index_to_addr(base, s.regions)
        key = (addr // 0x40, stride)
        if key in seen:
            continue
        seen.add(key)
        print("\n  first %s  stride 0x%x  grid value %d"
              % (hex(addr), stride, gridval), flush=True)
        for i, vals in trace(s, base, stride):
            print("    f%-5d %s" % (i, vals), flush=True)
        if len(seen) >= 12:
            print("\n  (stopping after 12 distinct candidates)")
            break
    return hits


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs.sort(key=lambda d: "frantic" not in d)
    which = sys.argv[1] if len(sys.argv) > 1 else None
    if which:
        dirs = [d for d in dirs if which in d]
    analyse(dirs[0])


if __name__ == "__main__":
    main()
