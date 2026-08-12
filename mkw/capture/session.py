#!/usr/bin/env python3
"""
Replay a recorded session offline, and verify one is usable.

As a library:
    from replay import Session
    s = Session("recordings/20260811-...-race1")
    s.u8(frame_i, 0x809c2800)          # read any address at any frame
    for i, img in s.frames():          # walk the whole race
        ...

As a script it verifies the most recent recording: reconstruction integrity,
achieved rate, and - the important one - that the reconstructed image agrees
with the live anchor reads taken during capture. If that check passes, the
recording is a faithful copy of what the game had in memory and every later
experiment can run against it instead of against a live race.

Run (from repo root, no sudo needed):
  mk/bin/python3 -m mkw.capture.session
"""

import glob
import json
import os
import struct

import numpy as np
import zstandard as zstd

from mkw.capture import format as capfmt
from mkw.capture.format import PAGE_SIZE

RECORDINGS = os.environ.get("MKW_RECORDINGS", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "recordings"))


class Session:
    def __init__(self, path):
        self.path = path
        with open(os.path.join(path, "meta.json")) as f:
            self.meta = json.load(f)
        self.regions = [(s, n) for s, n in self.meta["regions"]]
        self.index = []
        with open(os.path.join(path, "index.jsonl")) as f:
            for line in f:
                if line.strip():
                    self.index.append(json.loads(line))
        self.n_pages = capfmt.page_count(self.regions)
        self._blob = open(os.path.join(path, "frames.zst"), "rb")
        self._dctx = zstd.ZstdDecompressor()
        self._image = np.zeros(capfmt.image_size(self.regions), dtype=np.uint8)
        self._at = None

    def __len__(self):
        return len(self.index)

    def _raw(self, i):
        e = self.index[i]
        self._blob.seek(e["off"])
        return self._dctx.decompress(self._blob.read(e["clen"]))

    def _keyframe_at_or_before(self, i):
        for j in range(i, -1, -1):
            if self.index[j]["kind"] == "key":
                return j
        raise ValueError("no keyframe at or before frame %d" % i)

    def frame(self, i):
        """Flat uint8 image at frame i. Sequential access is cheap."""
        if self._at == i:
            return self._image
        if self._at is None or i < self._at:
            start = self._keyframe_at_or_before(i)
        else:
            key = self._keyframe_at_or_before(i)
            start = self._at + 1 if key <= self._at else key
        for j in range(start, i + 1):
            capfmt.decode_frame_into(self._raw(j), self._image, self.n_pages)
        self._at = i
        return self._image

    def frames(self, start=0, stop=None, step=1):
        for i in range(start, stop if stop is not None else len(self), step):
            yield i, self.frame(i)

    def read(self, i, addr, size):
        idx = capfmt.addr_to_index(addr, self.regions)
        if idx is None or capfmt.addr_to_index(addr + size - 1, self.regions) is None:
            return None
        return self.frame(i)[idx:idx + size].tobytes()

    def u8(self, i, addr):
        b = self.read(i, addr, 1)
        return None if b is None else b[0]

    def u32(self, i, addr):
        b = self.read(i, addr, 4)
        return None if b is None else struct.unpack(">I", b)[0]

    def anchors(self, i):
        """Anchor values recorded live; no decompression needed."""
        e = self.index[i]
        return {"block": e["block"], "position": e["position"], "course": e["course"]}


def latest_recording():
    dirs = sorted(glob.glob(os.path.join(RECORDINGS, "*")))
    dirs = [d for d in dirs if os.path.isfile(os.path.join(d, "meta.json"))]
    return dirs[-1] if dirs else None


def verify(path, sample=40):
    s = Session(path)
    m = s.meta
    print("recording: %s" % os.path.basename(path))
    print("  notes:   %s" % (m.get("notes") or "-"))
    print("  frames:  %d over %.1fs (%.1f Hz target %d, %d late)" % (
        len(s), m.get("duration_s", 0), m.get("achieved_hz", 0),
        m["rate_hz"], m.get("late_frames", 0)))
    print("  size:    %.2f GB" % (m.get("bytes", 0) / (1024 ** 3)))
    if not len(s):
        print("  EMPTY -> nothing recorded")
        return False

    problems = []

    dropped = sum(e.get("failed_chunks", 0) for e in s.index)
    if dropped:
        problems.append("%d chunk reads failed during capture" % dropped)

    achieved = m.get("achieved_hz", 0)
    if achieved < m["rate_hz"] * 0.9:
        problems.append("achieved %.1f Hz against a %d Hz target"
                        % (achieved, m["rate_hz"]))

    deltas = [e["npages"] for e in s.index if e["kind"] == "delta"]
    if deltas:
        print("  churn:   %.0f pages/frame median, %d max (of %d)" % (
            float(np.median(deltas)), max(deltas), s.n_pages))

    positions = [e["position"] for e in s.index if e["position"] is not None]
    courses = {e["course"] for e in s.index if e["course"] is not None}
    print("  anchors: %d/%d frames had a valid position, values %s"
          % (len(positions), len(s), sorted(set(positions))))
    print("  course:  %s" % sorted(hex(c) for c in courses))
    if not positions:
        problems.append("no valid position anchor in any frame")
    elif len(set(positions)) == 1:
        problems.append("position never changed; was this a real race?")

    # The load-bearing check: does the stored image agree with what the live
    # reads saw at capture time?
    checked = 0
    mismatched = 0
    unmapped = 0
    step = max(1, len(s) // sample)
    for i in range(0, len(s), step):
        e = s.index[i]
        if e["block"] is None or e["position"] is None:
            continue
        block = s.u32(i, capfmt.ANCHOR_PTR)
        if block is None:
            unmapped += 1
            continue
        pos = s.u8(i, block + capfmt.ANCHOR_POSITION_OFF)
        crs = s.u8(i, block + capfmt.ANCHOR_COURSE_OFF)
        if pos is None or crs is None:
            unmapped += 1
            continue
        checked += 1
        if block != e["block"] or pos != e["position"] or crs != e["course"]:
            mismatched += 1
    print("  fidelity: %d/%d sampled frames reproduce the live anchor reads"
          % (checked - mismatched, checked))
    if unmapped:
        problems.append(
            "%d sampled frames put the anchors outside the recorded regions; "
            "widen capfmt.REGIONS" % unmapped)
    if checked == 0:
        problems.append("could not check fidelity on any frame")
    elif mismatched:
        problems.append("%d sampled frames disagree with the live reads" % mismatched)

    if problems:
        print("\nNOT USABLE:")
        for p in problems:
            print("  - %s" % p)
        return False
    print("\nUSABLE: offline reads reproduce live reads; go ahead and use it as evidence.")
    return True


def main(which=None):
    """Verify one recording. Defaults to the most recent."""
    import glob, os, sys
    which = which if which is not None else (sys.argv[1] if len(sys.argv) > 1 else None)
    if which:
        hits = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
                if which in d and os.path.isfile(os.path.join(d, "meta.json"))]
        path = hits[0] if hits else None
    else:
        path = latest_recording()
    if path is None:
        print("no recording matching %r in %s" % (which, RECORDINGS))
        return False
    return verify(path)


if __name__ == "__main__":
    main()
