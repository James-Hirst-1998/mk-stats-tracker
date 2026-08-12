#!/usr/bin/env python3
"""
Offline: find the per-player position array in a recording.

Method, all against a recording, no live race needed:
  1. take the local player's position trace (recorded live per frame)
  2. find every address whose byte trace equals it for the whole race
  3. around each of those, look for a stride where 12 consecutive slots hold a
     permutation of 1..12 in every sampled frame

Step 3 is the load-bearing test: twelve slots that are always a permutation of
1..12 is a per-racer position array, not a coincidence.

Run (no sudo):
  mk/bin/python3 -m lab.progress.find_player_array
"""

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, latest_recording

TRACE_SAMPLES = 45            # frames used to match the position trace
ARRAY_CHECK_FRAMES = 5        # frames the 12-slot permutation must hold in
MAX_STRIDE = 0x2000


def settled_frames(pos, limit):
    """Frames where position has been stable for 2 ticks, one per new value."""
    picks, last = [], None
    for i in range(2, len(pos)):
        if pos[i] != pos[i - 1] or pos[i - 1] != pos[i - 2]:
            continue
        if last is None or pos[i] != pos[last]:
            picks.append(i)
            last = i
        if len(picks) >= limit:
            break
    return picks


def trace_matches(s, pos, picks):
    """Addresses whose value equals the local position at every sampled frame."""
    mask = None
    want = set(picks)
    for i, img in s.frames(stop=max(picks) + 1):
        if i not in want:
            continue
        eq = img == np.uint8(pos[i])
        mask = eq.copy() if mask is None else (mask & eq)
    return np.nonzero(mask)[0]


def find_array(s, anchor_index, images, check_frames):
    """Stride at which 12 slots around anchor are a permutation of 1..12."""
    target = set(range(1, 13))
    for stride in range(4, MAX_STRIDE, 4):
        slot, ok = None, 0
        for i in check_frames:
            js = np.arange(-11, 12)
            offs = anchor_index + js * stride
            valid = (offs >= 0) & (offs < images[i].size)
            if valid.sum() < 12:
                break
            vals = np.full(23, -1, dtype=np.int64)
            vals[valid] = images[i][offs[valid]]
            hit = next((st for st in range(12)
                        if set(vals[st:st + 12].tolist()) == target), None)
            if hit is None:
                break
            slot, ok = hit, ok + 1
        if ok == len(check_frames):
            return stride, -11 + slot
    return None, None


def main():
    path = latest_recording()
    if path is None:
        print("no recordings found")
        return
    s = Session(path)
    pos = np.array([e["position"] for e in s.index])
    if np.any(pos == None):  # noqa: E711 - object array from JSON nulls
        print("recording has frames without a position anchor; using them as-is")

    picks = settled_frames(pos, TRACE_SAMPLES)
    print("recording: %s" % path.split("/")[-1])
    print("matching against %d frames, positions %s"
          % (len(picks), [int(pos[i]) for i in picks]))

    surv = trace_matches(s, pos, picks)
    addrs = [capfmt.index_to_addr(int(i), s.regions) for i in surv]
    print("\n%d addresses track the local position all race:" % len(addrs))
    for a in addrs:
        print("   ", hex(a))

    check = [int(f) for f in np.linspace(len(s) * 0.3, len(s) * 0.9,
                                         ARRAY_CHECK_FRAMES)]
    images = {}
    for i, img in s.frames(stop=max(check) + 1):
        if i in check:
            images[i] = img.copy()

    print("\nper-player array search (frames %s):" % check)
    for a in addrs:
        base = capfmt.addr_to_index(a, s.regions)
        stride, j0 = find_array(s, base, images, check)
        if stride is None:
            continue
        first = capfmt.index_to_addr(base + j0 * stride, s.regions)
        vals = [int(images[check[0]][base + (j0 + k) * stride]) for k in range(12)]
        print("  HIT anchor=%s stride=0x%x first=%s local_slot=%d"
              % (hex(a), stride, hex(first), -j0))
        print("      positions at frame %d: %s" % (check[0], vals))
        print("\n  tracking it across the race:")
        for i, img in s.frames(step=max(1, len(s) // 12)):
            b = capfmt.addr_to_index(a, s.regions)
            vals = [int(img[b + (j0 + k) * stride]) for k in range(12)]
            print("    f%-5d local=%-3s all=%s" % (i, s.index[i]["position"], vals))
        return
    print("  none found")


if __name__ == "__main__":
    main()
