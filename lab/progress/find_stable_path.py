#!/usr/bin/env python3
"""
Offline: find a pointer address that reaches the per-player array in EVERY
recording, so the array can be located without a per-race hunt.

The array itself is heap-allocated and moves between races. But something has
to hold a pointer to it. This scans every 4-byte-aligned word in each recording
for a value within +/-0x200 of the array base, then intersects the results
across all recordings on (holder address, delta). A pair that survives the
intersection is a path that works in any race:

    array_base = u32(holder) + delta

Recordings must come from separate Dolphin launches for this to prove anything.

Run (no sudo):
  mk/bin/python3 -m lab.progress.find_stable_path
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.progress.mine_player_struct import locate_array, N_PLAYERS

SEARCH_DELTA = 0x200          # how far before/after the array a pointer may land
MID = 0.6                     # frame to scan, as a fraction of the race
VTABLE_OFFSETS = (0x54, 0x60, 0x6C, 0x88, 0xA4)


def holders(img, regions, array_first):
    """(holder_addr, delta) for every aligned word pointing near the array."""
    n = (img.size // 4) * 4
    words = np.frombuffer(img[:n].tobytes(), dtype=">u4").astype(np.int64)
    delta = array_first - words
    hit = np.nonzero((delta >= -SEARCH_DELTA) & (delta <= SEARCH_DELTA))[0]
    out = {}
    for w in hit:
        addr = capfmt.index_to_addr(int(w) * 4, regions)
        if addr is not None:
            out[addr] = int(delta[w])
    return out


def main():
    root = RECORDINGS
    per_recording = {}
    vtables = {}

    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        name = os.path.basename(d)
        s = Session(d)
        anchor, stride, local = locate_array(s)
        if anchor is None:
            print("%s: no array, skipping" % name)
            continue
        array_first = capfmt.index_to_addr(
            capfmt.addr_to_index(anchor, s.regions) - local * stride, s.regions)

        target = int(len(s) * MID)
        img = None
        for i, frame in s.frames(stop=target + 1):
            if i == target:
                img = frame
        found = holders(img, s.regions, array_first)
        per_recording[name] = {"array": array_first, "stride": stride,
                               "holders": found}
        base_i = capfmt.addr_to_index(array_first, s.regions)
        vtables[name] = {
            off: int(np.frombuffer(img[base_i + off:base_i + off + 4].tobytes(),
                                   dtype=">u4")[0])
            for off in VTABLE_OFFSETS
        }
        print("%-42s array=%s  %d candidate holders"
              % (name, hex(array_first), len(found)))

    if len(per_recording) < 2:
        print("\nneed at least two recordings")
        return

    print("\n-- intersecting (holder, delta) across all recordings --")
    common = None
    for name, r in per_recording.items():
        pairs = set(r["holders"].items())
        common = pairs if common is None else (common & pairs)
    common = sorted(common or [])

    if common:
        print("  %d holder/delta pairs work in EVERY recording:" % len(common))
        for addr, delta in common:
            # delta was computed as array_first - u32(addr), so it adds back on.
            print("    array_base = u32(%s) %s 0x%x"
                  % (hex(addr), "+" if delta >= 0 else "-", abs(delta)))
    else:
        print("  none. Checking whether any holder ADDRESS is common with a")
        print("  differing delta (would mean a parent struct that also moves):")
        addr_sets = [set(r["holders"]) for r in per_recording.values()]
        shared = set.intersection(*addr_sets)
        for addr in sorted(shared)[:20]:
            print("    %s deltas %s" % (
                hex(addr),
                [hex(r["holders"][addr]) for r in per_recording.values()]))
        if not shared:
            print("    no shared holder addresses either")

    print("\n-- vtable pointers inside the struct (static addresses) --")
    for off in VTABLE_OFFSETS:
        vals = {v[off] for v in vtables.values()}
        flag = "SAME in all recordings" if len(vals) == 1 else "differs"
        print("  +0x%03x  %s  <- %s" % (off, sorted(hex(v) for v in vals), flag))
    print("\n  A vtable that is identical across recordings is a static address,")
    print("  so scanning for it locates the array in any race without a pointer path.")


if __name__ == "__main__":
    main()
