#!/usr/bin/env python3
"""
Offline: first cut at "who hit who with what", from fields already proven.

No new memory hunting. Getting hit has a signature in raceCompletion: a racer
who is spun out, squashed or struck stops advancing for a beat, so their
progress rate collapses relative to their own normal pace. That gives victims
and timestamps.

Attackers come from the item array. Every use of an offensive item is already a
clean event (held id -> empty), so a stall shortly after someone throws
something offensive has a named suspect. Where exactly one suspect fits, the
hit is attributed; where several do, it is reported as ambiguous rather than
guessed at.

This is an inference, not a read. It is here to be checked against the video
before any of it goes near source/.

Run (no sudo):
  mk/bin/python3 -m lab.progress.find_hits [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x120
PLAYER_STRIDE = 0xC4
OFF_COMPLETION = 0x0C
OFF_POSITION = 0x20
N_PLAYERS = 12

ITEM_PTR = 0x809C3648
ITEM_DELTA = -0x227D
ITEM_STRIDE = 0x248
OFF_HELD = 0x01C
EMPTY = 20

STALL_RATIO = 0.25          # fraction of a racer's own median pace
MIN_STALL = 0.4             # seconds
MAX_STALL = 4.0             # longer than this is a lap-boundary artefact
SMOOTH = 5                  # frames, ~0.25s
LOOKBACK = 3.5              # seconds before the stall to look for a throw
LOOKAHEAD = 0.4

OFFENSIVE = {0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
             6: "Bob-omb", 7: "Blue Shell", 8: "Lightning", 12: "Blooper",
             13: "POW Block", 14: "Thunder Cloud", 16: "Triple Green Shells",
             17: "Triple Red Shells", 18: "Triple Bananas"}
NAMES = dict(OFFENSIVE)
NAMES.update({4: "Mushroom", 5: "Triple Mushrooms", 9: "Star",
              10: "Golden Mushroom", 11: "Mega Mushroom", 15: "Bullet Bill",
              19: "?", 20: "-"})
# Items that hit everyone at once rather than one victim.
BROADCAST = {8, 13}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def load(s):
    comp = np.full((len(s), N_PLAYERS), np.nan, dtype=np.float64)
    held = np.full((len(s), N_PLAYERS), -1, dtype=np.int16)
    pos = np.zeros((len(s), N_PLAYERS), dtype=np.int16)
    t = np.full(len(s), np.nan)
    pi = capfmt.addr_to_index(PLAYER_PTR, s.regions)
    ii = capfmt.addr_to_index(ITEM_PTR, s.regions)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        bi = capfmt.addr_to_index(be_u32(img, pi) + PLAYER_DELTA, s.regions)
        ib = capfmt.addr_to_index(be_u32(img, ii) + ITEM_DELTA, s.regions)
        if bi is None:
            continue
        p = [int(img[bi + k * PLAYER_STRIDE + OFF_POSITION]) for k in range(N_PLAYERS)]
        if sorted(p) != list(range(1, N_PLAYERS + 1)):
            continue
        t[i] = s.index[i]["mono"]
        pos[i] = p
        for k in range(N_PLAYERS):
            o = bi + k * PLAYER_STRIDE + OFF_COMPLETION
            comp[i, k] = float(np.frombuffer(img[o:o + 4].tobytes(), dtype=">f4")[0])
            if ib is not None:
                held[i, k] = int(img[ib + k * ITEM_STRIDE + OFF_HELD])
    return t, comp, held, pos


def stalls(t, comp, k):
    ok = ~np.isnan(t) & ~np.isnan(comp[:, k])
    idx = np.nonzero(ok)[0]
    if idx.size < 50:
        return []
    tt, cc = t[idx], comp[idx, k]
    rate = np.gradient(cc, tt)
    kern = np.ones(SMOOTH) / SMOOTH
    rate = np.convolve(rate, kern, mode="same")
    med = np.median(rate[rate > 0]) if (rate > 0).any() else 0
    if med <= 0:
        return []
    slow = rate < med * STALL_RATIO
    out, start = [], None
    for j in range(len(slow) + 1):
        v = slow[j] if j < len(slow) else False
        if v and start is None:
            start = j
        elif not v and start is not None:
            dur = tt[min(j, len(tt) - 1)] - tt[start]
            if MIN_STALL <= dur <= MAX_STALL:
                out.append((tt[start], dur))
            start = None
    return out


def race_start(t, comp):
    """First moment anyone actually advances - before this everyone is idle."""
    ok = np.nonzero(~np.isnan(t))[0]
    for a, b in zip(ok, ok[1:]):
        if np.nanmax(comp[b] - comp[a]) > 1e-4:
            return t[b]
    return t[ok[0]] if ok.size else 0.0


def lost_ground(t, comp, k, lo=0.02, hi=0.5):
    """Race completion reset backward - the racer was put back down the track.

    Drops of about 1.0 are the lap counter wrapping, not a setback, so `hi`
    excludes them. `lo` comes from checking all five of the local player's
    reversals in the Mushroom Gorge recording against the video.

    This does NOT isolate falling off. Of those five, three are falls (two into
    the void, one ending in the rescue white-out) and two are item hits with
    sparks visible round the kart. The magnitudes overlap across the two causes
    - 0.024 is a fall here while 0.025 was normal driving in Yoshi Falls - so
    size alone cannot separate them. Treat this as "lost ground", and use the
    hit detector alongside it.
    """
    ok = np.nonzero(~np.isnan(t) & ~np.isnan(comp[:, k]))[0]
    if ok.size < 10:
        return []
    tt, cc = t[ok], comp[ok, k]
    d = np.diff(cc)
    out, last = [], -1e9
    for j in np.nonzero((d < -lo) & (d > -hi))[0]:
        if tt[j] - last > 2.0:
            out.append((tt[j], float(-d[j])))
        last = tt[j]
    return out


def throws(t, held):
    out = []
    for k in range(N_PLAYERS):
        prev = None
        for i in range(len(t)):
            v = held[i, k]
            if v < 0 or np.isnan(t[i]):
                continue
            if prev is not None and prev != EMPTY and v == EMPTY:
                out.append((t[i], k, int(prev)))
            prev = v
    out.sort()
    return out


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else "frantic"
    dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return
    s = Session(dirs[0])
    t, comp, held, pos = load(s)
    thr = throws(t, held)
    t0 = np.nanmin(t)
    print("%s: %d item uses across all racers\n"
          % (os.path.basename(dirs[0]), len(thr)), flush=True)

    attributed = ambiguous = unexplained = 0
    for k in range(N_PLAYERS):
        ev = stalls(t, comp, k)
        for when, dur in ev:
            suspects = [(tt, who, item) for tt, who, item in thr
                        if who != k and item in OFFENSIVE
                        and when - LOOKBACK <= tt <= when + LOOKAHEAD]
            label = "slot %d" % k
            if len(suspects) == 1:
                tt, who, item = suspects[0]
                attributed += 1
                print("  %6.1fs  %-8s hit by slot %-2d %-20s (%.1fs stall, "
                      "%.1fs after the throw)"
                      % (when - t0, label, who, OFFENSIVE[item], dur, when - tt))
            elif suspects:
                ambiguous += 1
                print("  %6.1fs  %-8s stalled %.1fs - %d possible: %s"
                      % (when - t0, label, dur, len(suspects),
                         ", ".join("slot %d %s" % (w, OFFENSIVE[i])
                                   for _, w, i in suspects[:4])))
            else:
                unexplained += 1
    print("\n%d attributed to one suspect, %d ambiguous, %d stalls with no "
          "offensive item thrown nearby (track, wall, or a hazard)"
          % (attributed, ambiguous, unexplained))


if __name__ == "__main__":
    main()
