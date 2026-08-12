#!/usr/bin/env python3
"""
Offline: locate the per-player array in every recording and characterise what
each offset in the per-player struct holds.

For each recording it finds the array (see find_player_array.py), then samples
the whole race and classifies every offset by how it behaves across the 12
players and across time:

  RANK      a permutation of 1..12 every frame -> race position
  ID        constant all race, differs between players -> identity field
  CONST     constant all race and identical for every player
  COUNTER   never decreases per player, small range -> lap / checkpoint
  PTR       aligned u32 that is always a MEM1 pointer
  FLOAT     aligned u32 that is always a plausible float
  DYNAMIC   changes, none of the above

Run (no sudo):
  mk/bin/python3 -m lab.progress.mine_player_struct
"""

import glob
import os
import struct as _struct

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PREFIX_FRAMES = 800           # frames used to locate the array
SAMPLE_STEP = 20              # frame step when characterising
TRACE_SAMPLES = 45
ARRAY_CHECK = 5
MAX_STRIDE = 0x2000
N_PLAYERS = 12


def settled_frames(pos, limit, max_frame):
    picks, last = [], None
    for i in range(2, min(len(pos), max_frame)):
        if pos[i] != pos[i - 1] or pos[i - 1] != pos[i - 2]:
            continue
        if last is None or pos[i] != pos[last]:
            picks.append(i)
            last = i
        if len(picks) >= limit:
            break
    return picks


def locate_array(s):
    """Return (anchor_addr, stride, local_slot) or (None, None, None)."""
    pos = np.array([e["position"] for e in s.index])
    picks = settled_frames(pos, TRACE_SAMPLES, PREFIX_FRAMES)
    if len(picks) < 6:
        return None, None, None

    mask, want = None, set(picks)
    keep = {}
    for i, img in s.frames(stop=max(picks) + 1):
        if i not in want:
            continue
        eq = img == np.uint8(pos[i])
        mask = eq.copy() if mask is None else (mask & eq)
        keep[i] = img.copy() if len(keep) < ARRAY_CHECK else None
    surv = np.nonzero(mask)[0]
    check = [i for i in picks if keep.get(i) is not None][:ARRAY_CHECK]
    target = set(range(1, N_PLAYERS + 1))

    for idx in surv:
        for stride in range(4, MAX_STRIDE, 4):
            slot, ok = None, 0
            for i in check:
                js = np.arange(-(N_PLAYERS - 1), N_PLAYERS)
                offs = idx + js * stride
                valid = (offs >= 0) & (offs < keep[i].size)
                if valid.sum() < N_PLAYERS:
                    break
                vals = np.full(js.size, -1, dtype=np.int64)
                vals[valid] = keep[i][offs[valid]]
                hit = next((st for st in range(N_PLAYERS)
                            if set(vals[st:st + N_PLAYERS].tolist()) == target), None)
                if hit is None:
                    break
                slot, ok = hit, ok + 1
            if ok == len(check):
                local = N_PLAYERS - 1 - slot
                return capfmt.index_to_addr(int(idx), s.regions), stride, local
    return None, None, None


def collect(s, anchor_addr, stride, local_slot):
    """Sample the whole race: array[frame, player, byte]."""
    first_index = capfmt.addr_to_index(anchor_addr, s.regions) - local_slot * stride
    frames, blocks = [], []
    for i, img in s.frames(step=SAMPLE_STEP):
        blocks.append(img[first_index:first_index + N_PLAYERS * stride]
                      .reshape(N_PLAYERS, stride).copy())
        frames.append(i)
    return np.array(frames), np.stack(blocks), first_index


def u32_view(data, off):
    """data[frame, player, byte] -> big-endian u32 at byte offset off."""
    raw = data[:, :, off:off + 4]
    return (raw[:, :, 0].astype(np.uint32) << 24 | raw[:, :, 1].astype(np.uint32) << 16
            | raw[:, :, 2].astype(np.uint32) << 8 | raw[:, :, 3].astype(np.uint32))


def classify(data, stride):
    """Label each byte offset in the struct."""
    out = {}
    target = set(range(1, N_PLAYERS + 1))
    for off in range(stride):
        col = data[:, :, off].astype(np.int64)
        per_player_const = bool((col.max(axis=0) == col.min(axis=0)).all())
        all_same = bool(col.max() == col.min())

        if all_same:
            out[off] = ("CONST", "0x%02x" % col[0, 0])
            continue
        if per_player_const:
            out[off] = ("ID", str([int(v) for v in col[0]]))
            continue
        if all(set(row.tolist()) == target for row in col):
            out[off] = ("RANK", "permutation of 1..12")
            continue
        if bool((np.diff(col, axis=0) >= 0).all()) and int(col.max()) <= 64:
            out[off] = ("COUNTER", "%d..%d" % (col.min(), col.max()))
            continue
        out[off] = ("DYNAMIC", "%d..%d" % (col.min(), col.max()))

    for off in range(0, stride - 3, 4):
        v = u32_view(data, off)
        if bool(((v >= 0x80000000) & (v < 0x81800000)).all()):
            out[off] = ("PTR", "0x%08x .." % int(v[0, 0]))
            continue
        f = v.view(np.float32) if v.dtype == np.uint32 else None
        if f is not None:
            fv = np.frombuffer(v.astype(">u4").tobytes(), dtype=">f4")
            finite = np.isfinite(fv)
            if finite.all() and np.abs(fv).max() < 1e7 and np.abs(fv).max() > 1e-6:
                if out[off][0] in ("DYNAMIC",):
                    out[off] = ("FLOAT", "%.3f .. %.3f" % (fv.min(), fv.max()))
    return out


def report(name, s, anchor, stride, local, frames, data, first_index):
    print("=" * 78)
    print(name)
    print("  course 0x%02x, %d frames, array first slot %s, stride 0x%x, you are slot %d"
          % (s.index[0]["course"], len(s),
             hex(capfmt.index_to_addr(first_index, s.regions)), stride, local))

    labels = classify(data, stride)
    groups = {}
    for off, (kind, detail) in labels.items():
        groups.setdefault(kind, []).append((off, detail))

    for kind in ("RANK", "COUNTER", "ID", "PTR", "FLOAT", "DYNAMIC", "CONST"):
        items = groups.get(kind, [])
        if not items:
            continue
        print("  %-8s %d offsets" % (kind, len(items)))
        if kind in ("RANK", "COUNTER", "ID", "PTR", "FLOAT"):
            for off, detail in items[:14]:
                print("      +0x%03x  %s" % (off, detail))
            if len(items) > 14:
                print("      ... %d more" % (len(items) - 14))
    return labels


def main():
    root = RECORDINGS
    results = {}
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        s = Session(d)
        anchor, stride, local = locate_array(s)
        name = os.path.basename(d)
        if anchor is None:
            print("=" * 78)
            print("%s\n  NO ARRAY FOUND" % name)
            continue
        frames, data, first_index = collect(s, anchor, stride, local)
        labels = report(name, s, anchor, stride, local, frames, data, first_index)
        results[name] = {
            "first": capfmt.index_to_addr(first_index, s.regions),
            "stride": stride, "local": local, "labels": labels,
            "course": s.index[0]["course"],
        }

    print("=" * 78)
    print("CROSS-RECORDING")
    for name, r in results.items():
        print("  %-42s first=%s stride=0x%x slot=%d"
              % (name, hex(r["first"]), r["stride"], r["local"]))
    firsts = {r["first"] for r in results.values()}
    strides = {r["stride"] for r in results.values()}
    print("  distinct array addresses: %s" % sorted(hex(f) for f in firsts))
    print("  distinct strides:         %s" % sorted(hex(x) for x in strides))
    if len(firsts) == 1:
        print("  -> array address is STABLE across all recordings")
    else:
        print("  -> array address MOVES between recordings; needs a pointer path")

    if len(results) > 1:
        common = None
        for r in results.values():
            kinds = {off: k for off, (k, _) in r["labels"].items()}
            common = kinds if common is None else {
                o: k for o, k in kinds.items() if common.get(o) == k}
        print("\n  offsets classified identically in every recording:")
        for kind in ("RANK", "COUNTER", "ID", "PTR", "FLOAT"):
            offs = [o for o, k in sorted(common.items()) if k == kind]
            if offs:
                print("    %-8s %s" % (kind, ", ".join("+0x%03x" % o for o in offs[:20])))


if __name__ == "__main__":
    main()
