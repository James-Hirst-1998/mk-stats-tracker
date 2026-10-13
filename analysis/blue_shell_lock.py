#!/usr/bin/env python3
"""Offline: when does a Blue Shell decide who it is going for?

The shell flies towards whoever is leading and, close to the end, locks on to
whoever is in first and stops changing its mind (as played: "about three
seconds"). So the racer it was aimed at is the leader some time before it went
off - not at the throw, and not at the instant of the hit, when the leader can
already have been passed by somebody caught in the blast.

This measures that time from the stored race logs. Every launched hit whose
object was read as a Blue Shell goes to the owner's latest shell thrown before
it, which gives each shell its blast. For each candidate lock time L it then
counts the blasts where the leader at max(throw, first hit - L) - leaders
counted among racers who had not finished - is one of the victims.

For a shell that hit nobody there is no hit to count back from, so it also
measures when the lock falls after the throw, and lists those shells with who
led from the throw on.

For a launch whose object was not read, it measures how long after the drop
and how far from the dropper the read Bob-omb hits were, and lists the unread
launches with the Blue Shells and Bob-ombs used in the 20s before them.

Run (no sudo), from the repo root:
  mk/bin/python3 -m analysis.blue_shell_lock
"""

import glob
import os
import statistics

from mkw.racelog import RACES, RaceLog

BLUE_ITEM, BOMB_ITEM = 7, 6
BLUE_OBJECT, BOMB_OBJECT = 5, 9
LAUNCHED = 7
LOCKS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]


def leader_at(log):
    swaps = sorted(log.of_type("pos"), key=lambda e: e["t"])
    finishes = log.of_type("finish")
    start = {}
    for e in swaps:
        start.setdefault(e["slot"], e["from"])
    for r in log.meta.get("racers", []):
        start.setdefault(r["slot"], r["grid"])

    def at(t):
        pos = dict(start)
        for e in swaps:
            if e["t"] > t:
                break
            pos[e["slot"]] = e["to"]
        done = {f["slot"] for f in finishes if f["t"] <= t}
        live = [s for s in pos if s not in done]
        return min(live, key=lambda s: pos[s]) if live else None
    return at


def blasts(log):
    """{(throw time, thrower): [hits]} for every Blue Shell thrown."""
    uses = sorted((e for e in log.of_type("use")
                   if e.get("item") == BLUE_ITEM and "slot" in e),
                  key=lambda e: e["t"])
    out = {(u["t"], u["slot"]): [] for u in uses}
    for h in log.of_type("hit"):
        if h.get("damage") != LAUNCHED or h.get("object") != BLUE_OBJECT \
                or h.get("guess"):
            continue
        owner = [u for u in uses
                 if u["slot"] in (h.get("by") or []) and u["t"] <= h["t"]]
        if owner:
            out[(owner[-1]["t"], owner[-1]["slot"])].append(h)
    return out


def main():
    paths = sorted(glob.glob(os.path.join(RACES, "**", "*.jsonl"),
                             recursive=True))
    found = {L: 0 for L in LOCKS}
    multi = {L: 0 for L in LOCKS}
    logger_multi = logger_n = 0
    adjusted = adjusted_multi = 0
    landed = n_multi = 0
    flights = []
    locks = []
    fuses = []
    reach = []
    missed = []
    unread = []
    for p in paths:
        log = RaceLog(p)
        lead = leader_at(log)
        finished = {f["slot"]: f["t"] for f in log.of_type("finish")}
        name = os.path.relpath(p, RACES)
        for (t, thrower), hits in blasts(log).items():
            if not hits:
                order = [lead(t)]
                for k in range(1, 61):
                    who = lead(t + k * 0.25)
                    if who != order[-1]:
                        order.append(who)
                missed.append((name, t, thrower, order))
                continue
            landed += 1
            first = min(h["t"] for h in hits)
            flights.append(first - t)
            locks.append(max(0.0, first - 2.0 - t))
            victims = {h["slot"] for h in hits}
            many = len(victims) > 1
            n_multi += many
            if many and sum(h.get("place") == 1 for h in hits) == 1:
                aimed = next(h["slot"] for h in hits if h.get("place") == 1)
                logger_n += 1
                logger_multi += aimed == lead(max(t, first - 2.0))
            # The rule the dashboard uses: the leader at L=2.0, or when that
            # leader crossed the line before it went off, the leader at the
            # hit. Replacing them outright loses the shells that followed a
            # leader over the line and got them there.
            who = [lead(max(t, first - 2.0))]
            if who[0] is not None and finished.get(who[0], float("inf")) <= first:
                who.append(lead(first))
            got = any(w in victims for w in who)
            adjusted += got
            adjusted_multi += got and many
            for L in LOCKS:
                hit = lead(max(t, first - L)) in victims
                found[L] += hit
                multi[L] += hit and many
        uses = [e for e in log.of_type("use") if "slot" in e]
        for h in log.of_type("hit"):
            if h.get("damage") != LAUNCHED or h.get("object") != BOMB_OBJECT \
                    or h.get("guess"):
                continue
            drops = [u for u in uses if u.get("item") == BOMB_ITEM
                     and u["slot"] in (h.get("by") or []) and u["t"] <= h["t"]]
            if drops:
                fuses.append(h["t"] - drops[-1]["t"])
                at = log.progress_at(h["t"])
                if h["slot"] in at and drops[-1]["slot"] in at:
                    reach.append(abs(at[h["slot"]] - at[drops[-1]["slot"]]))
        for h in log.of_type("hit"):
            if h.get("damage") == LAUNCHED and h.get("object") is None:
                before = [(round(h["t"] - u["t"], 1), u["item"], u["slot"])
                          for u in uses
                          if u.get("item") in (BLUE_ITEM, BOMB_ITEM)
                          and 0 <= h["t"] - u["t"] <= 20]
                unread.append((name, h["t"], h["slot"], before))

    print("%d race logs, %d shells landed, %d blasts with more than one victim"
          % (len(paths), landed, n_multi))
    print("flight to first hit: %.1f-%.1fs, median %.1f"
          % (min(flights), max(flights), statistics.median(flights)))
    print()
    print("lock L   leader at max(throw, hit-L) among victims   (of the multi-victim blasts)")
    for L in LOCKS:
        print("  %.1fs   %3d of %d   (%d of %d)"
              % (L, found[L], landed, multi[L], n_multi))
    print("  2.0s, or the leader at the hit when that one had crossed the line:"
          " %d of %d   (%d of %d)" % (adjusted, landed, adjusted_multi, n_multi))
    print("  the logger's one victim in 1st is that leader in %d of the %d multi-victim"
          " blasts that have one" % (logger_multi, logger_n))
    print("lock at L=2.0 falls 1-6s after the throw for %d of %d"
          % (sum(1.0 <= x <= 6.0 for x in locks), len(locks)))
    print()
    print("read Bob-omb hits with the drop found: %d" % len(fuses))
    print("  went off %.1f-%.1fs after the drop, median %.1f; within 3s: %d"
          % (min(fuses), max(fuses), statistics.median(fuses),
             sum(f <= 3.0 for f in fuses)))
    print("  victim to dropper at the hit: at most %.3f laps (%d measured)"
          % (max(reach), len(reach)))
    print()
    print("shells that hit nobody (leader from the throw, every change in the next 15s):")
    for name, t, thrower, order in missed:
        print("  %-60s %7.2f thrower %2d  leaders %s" % (name, t, thrower, order))
    print()
    print("launches with no object read (item 7 Blue, 6 Bob-omb; seconds before, item, slot):")
    for name, t, slot, before in unread:
        print("  %-60s %7.2f victim %2d  %s" % (name, t, slot, before))


if __name__ == "__main__":
    main()
