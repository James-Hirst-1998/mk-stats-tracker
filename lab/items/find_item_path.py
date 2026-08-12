#!/usr/bin/env python3
"""
Offline: locate the per-player item array in every recording by its shape, then
find a pointer path that reaches it in all of them.

The shape came from find_item_from_video.py, which identified the local
player's held-item byte against icons read off the screen recording:

    12 slots, stride 0x248, local player at slot 0, values 0..20 (20 = empty)

That is specific enough to find without labels, so the other recordings need no
video at all. Then the same intersection used for the position array:

    item_base = u32(holder) + delta,  holding in every recording

Run (no sudo):
  mk/bin/python3 -m lab.items.find_item_path
"""

import glob
import os

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

STRIDE = 0x248
N_PLAYERS = 12
ITEM_MAX = 20
MIN_VARYING = 8
SAMPLE_STEP = 25
SEARCH_DELTA = 0x20000
MID = 0.6
# Base verified against the screen recording in find_item_from_video.py.
VERIFIED_BASE_IN = ("frantic", 0x8124c3db)

NAMES = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
         4: "Mushroom", 5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell",
         8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
         12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
         16: "Triple Green", 17: "Triple Red", 18: "Triple Bananas",
         19: "(unused)", 20: "empty"}


def scan(s):
    vmax = nch = prev = None
    n = 0
    for i, img in s.frames(step=SAMPLE_STEP):
        if s.index[i]["position"] is None:
            continue
        if vmax is None:
            vmax = img.copy()
            nch = np.zeros(img.size, dtype=np.uint16)
        else:
            np.maximum(vmax, img, out=vmax)
            nch += (img != prev)
        prev = img.copy()
        n += 1
    return vmax, nch, n


def find_array(vmax, nch, size):
    """Bases where 12 slots at STRIDE all stay <=20 and enough of them vary."""
    ok = vmax <= ITEM_MAX
    span = (N_PLAYERS - 1) * STRIDE
    cand = np.nonzero(ok[:size - span])[0].astype(np.int64)
    if not cand.size:
        return []
    acc = np.ones(cand.size, dtype=bool)
    varying = (nch[cand] > 2).astype(np.int16)
    for k in range(1, N_PLAYERS):
        o = cand + k * STRIDE
        acc &= ok[o]
        varying += (nch[o] > 2).astype(np.int16)
        if not acc.any():
            return []
    acc &= varying >= MIN_VARYING
    return cand[acc].tolist()


def holders(img, regions, base_addr):
    n = (img.size // 4) * 4
    words = np.frombuffer(img[:n].tobytes(), dtype=">u4").astype(np.int64)
    delta = base_addr - words
    hit = np.nonzero((delta >= -SEARCH_DELTA) & (delta <= SEARCH_DELTA))[0]
    out = {}
    for w in hit:
        a = capfmt.index_to_addr(int(w) * 4, regions)
        if a is not None:
            out[a] = int(delta[w])
    return out


def main():
    root = RECORDINGS
    per = {}
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        name = os.path.basename(d)
        s = Session(d)
        vmax, nch, n = scan(s)
        bases = find_array(vmax, nch, vmax.size)
        if not bases:
            print("%-42s no item array found" % name)
            continue
        # Neighbouring bytes in the same per-player struct also satisfy the
        # shape, so keep every candidate and let the cross-recording
        # intersection decide which one is the real base.
        if VERIFIED_BASE_IN and VERIFIED_BASE_IN[0] in name:
            want = capfmt.addr_to_index(VERIFIED_BASE_IN[1], s.regions)
            bases = [b for b in bases if b == want] or bases
        addrs = [capfmt.index_to_addr(b, s.regions) for b in bases]
        print("%-42s %d candidate bases, e.g. %s"
              % (name, len(bases), ", ".join(hex(a) for a in addrs[:3])))

        target = int(len(s) * MID)
        img = None
        for i, frame in s.frames(stop=target + 1):
            if i == target:
                img = frame
        vals = [int(img[bases[0] + k * STRIDE]) for k in range(N_PLAYERS)]
        print("      at f%d: %s" % (target, [NAMES.get(v, v) for v in vals]))

        merged = {}
        for a in addrs:
            for holder, delta in holders(img, s.regions, a).items():
                merged.setdefault((holder, delta), set()).add(a)
        per[name] = {"addrs": addrs, "holders": merged}

    if len(per) < 2:
        print("\nneed at least two recordings with the array")
        return

    print("\n-- intersecting (holder, delta) across recordings --")
    common = None
    for r in per.values():
        pairs = set(r["holders"])
        common = pairs if common is None else (common & pairs)
    common = sorted(common or [])
    if common:
        for holder, delta in common:
            print("  item_base = u32(%s) %s 0x%x"
                  % (hex(holder), "+" if delta >= 0 else "-", abs(delta)))
            for name, r in per.items():
                print("      %-42s -> %s" % (
                    name, ", ".join(hex(a) for a in sorted(r["holders"][(holder, delta)]))))
    else:
        print("  no holder/delta pair works in every recording")


if __name__ == "__main__":
    main()
