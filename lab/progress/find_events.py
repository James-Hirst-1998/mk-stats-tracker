#!/usr/bin/env python3
"""
Offline: detect hits, blue shells and field-wide items, from proven fields only.

No new memory hunting. A racer who is struck stops advancing, so raceCompletion
rate collapses relative to their own normal pace. Three predicted hits were
checked frame by frame against the video and all three are real: a lightning
bolt flattening the kart, a white-out, and a spin-out with stars.

Two item types can be named without knowing who threw anything, which is all
James asked for:

  Lost ground  race completion reset backward. Covers both a Lakitu rescue
              and a bad item hit - video checking of all five of the local
              player's reversals in the Mushroom Gorge recording gives three
              falls and two hits, with overlapping magnitudes. Reported as
              "lost ground" rather than claimed as a fall.

  Blue Shell  always goes for the leader, and takes several seconds to get
              there. Rule: a blue shell leaves someone's hands, and whoever is
              in P1 has their first stall 4-10s later. Verified on video in the
              frantic recording - the shell dives in at video 57.2s, the screen
              whites out at 57.9s, the kart is thrown into the air at 58.6s,
              and the stall detector fires at exactly that moment, 5.6s after
              the throw. The first version of this script missed it because its
              lookback was 3.5s.

  Lightning / POW  hit everyone at once. Rule: an item leaves someone's hands
              and most of the field stalls within a couple of seconds.

Everything else is reported as a hit with no item named. Attribution beyond
that needs a purpose-made recording.

This is inference over proven reads, so it lives in lab/, not mkw/.

Run (no sudo):
  mk/bin/python3 -m lab.progress.find_events [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS
from lab.progress.find_hits import (PLAYER_PTR, PLAYER_DELTA, PLAYER_STRIDE, OFF_COMPLETION,
                       OFF_POSITION, ITEM_PTR, ITEM_DELTA, ITEM_STRIDE,
                       OFF_HELD, N_PLAYERS, EMPTY, be_u32, load, stalls, throws,
                       lost_ground, race_start)

BLUE = 7
BROADCAST = {8: "Lightning", 13: "POW Block"}
BLUE_FLIGHT = (4.0, 10.0)   # measured: 5.6s from throw to impact on video
BROADCAST_FLIGHT = (0.0, 3.0)
BROADCAST_MIN_VICTIMS = 7
TOGETHER = 2.0


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

    start = race_start(t, comp)
    hits = []
    drops = []
    for k in range(N_PLAYERS):
        for when, dur in stalls(t, comp, k):
            if when < start + 1.0:
                continue                  # the grid is stationary on the line
            hits.append({"t": when, "dur": dur, "slot": k, "kind": None})
        for when, size in lost_ground(t, comp, k):
            drops.append({"t": when, "size": size, "slot": k})
    hits.sort(key=lambda h: h["t"])
    drops.sort(key=lambda h: h["t"])
    # A rescue also stalls the racer; label that stall rather than double-count.
    for f in drops:
        for h in hits:
            if h["kind"] is None and h["slot"] == f["slot"] \
                    and abs(h["t"] - f["t"]) < 6.0:
                h["kind"] = "lost ground"
                break

    def leader_at(when):
        j = int(np.nanargmin(np.abs(np.where(np.isnan(t), 1e9, t) - when)))
        row = pos[j]
        return int(np.argmin(np.where(row == 0, 99, row)))

    # Field-wide items: most of the grid stalls together just after a throw.
    for tt, who, item in thr:
        if item not in BROADCAST:
            continue
        victims = [h for h in hits
                   if h["kind"] is None
                   and tt + BROADCAST_FLIGHT[0] <= h["t"] <= tt + BROADCAST_FLIGHT[1]]
        if len({h["slot"] for h in victims}) >= BROADCAST_MIN_VICTIMS:
            for h in victims:
                h["kind"] = BROADCAST[item]
                h["by"] = who

    # Blue shell: the leader, several seconds after it is thrown.
    for tt, who, item in thr:
        if item != BLUE:
            continue
        lead = leader_at(tt + 4.0)
        cand = [h for h in hits
                if h["kind"] is None and h["slot"] == lead
                and tt + BLUE_FLIGHT[0] <= h["t"] <= tt + BLUE_FLIGHT[1]]
        if cand:
            h = min(cand, key=lambda x: x["t"])          # the shell arrives once
            h["kind"] = "Blue Shell"
            h["by"] = who

    print("%s\n" % os.path.basename(dirs[0]))
    named = [h for h in hits if h["kind"]]
    print("named events:")
    seen = set()
    for h in named:
        key = (h["kind"], round(h["t"], 0))
        if h["kind"] in BROADCAST.values():
            if key in seen:
                continue
            seen.add(key)
            who = sorted({x["slot"] for x in named
                          if x["kind"] == h["kind"]
                          and abs(x["t"] - h["t"]) < TOGETHER})
            print("  %6.1fs  %-12s hit %d racers%s"
                  % (h["t"] - t0, h["kind"], len(who),
                     " (including you)" if 0 in who else ""))
        else:
            print("  %6.1fs  %-12s hit %s (%.1fs lost)"
                  % (h["t"] - t0, h["kind"],
                     "you" if h["slot"] == 0 else "slot %d" % h["slot"],
                     h["dur"]))

    print("\nlost ground (put back down the track - a fall OR a hit):")
    for f in drops:
        print("  %6.1fs  %s put back %.3f of a lap"
              % (f["t"] - t0, "you" if f["slot"] == 0 else "slot %d" % f["slot"],
                 f["size"]))
    if not drops:
        print("  none")

    print("\nyour hits (slot 0):")
    for h in hits:
        if h["slot"] != 0:
            continue
        print("  %6.1fs  %-12s %.1fs lost"
              % (h["t"] - t0, h["kind"] or "hit", h["dur"]))
    mine = [h for h in hits if h["slot"] == 0]
    print("\n%d hits total, %.1fs lost, %d named"
          % (len(mine), sum(h["dur"] for h in mine),
             sum(1 for h in mine if h["kind"])))


if __name__ == "__main__":
    main()
