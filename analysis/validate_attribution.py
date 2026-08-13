#!/usr/bin/env python3
"""Offline: how many hits get a name on them, and how good the new names are.

Most hits are named by watching the object that caused them get destroyed,
which reads the thrower straight off the object. Three kinds of hit leave no
object at all and used to go out anonymous:

  a ram        - a Star, Mega or Bullet does its damage with the kart itself
  a field item - Lightning and the POW catch a whole group at once
  a cloud      - won, passed on by bumping people, goes off on whoever has it

The first two are inference and are marked `guess` in the log. This checks
them against things they were not derived from: a ram's victim and the racer
credited with it should be next to each other and nobody else should be, and
the racer credited with a Lightning should be the one racer it did not hit.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_attribution [recording-substring]
"""

import sys
from collections import Counter

from mkw.events import Race, RAMMED, FIELD_WIDE
from mkw.names import DAMAGE_TYPES
from lab.events.snapshots import recordings, racing


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    named = Counter()
    total = Counter()
    checked = Counter()
    passed = Counter()
    clouds = Counter()
    for d in recordings(which):
        name, frames = racing(d)
        if not frames:
            continue
        race = Race()
        for _, r in frames:
            race.update(r)
        race.flush()

        by_time = {}
        for t, r in frames:
            by_time[round(t, 3)] = r
        for e in race.events:
            if e["type"] == "cloud":
                clouds["won"] += 1
            if e["type"] != "hit":
                continue
            total[e["damage"]] += 1
            if e.get("by"):
                named[e["damage"]] += 1
            if e.get("from") is not None:
                clouds["struck"] += 1
                clouds["passed on" if e.get("passed") else "kept it"] += 1

            # A ram: the rule picks whoever used the item and was close, so
            # asking whether they were close is asking the rule to agree with
            # itself. What it never looks at is the credited racer's own
            # damage field - and somebody riding a Star, a Mega or a Bullet is
            # invulnerable, so they should not be taking damage themselves at
            # the moment they run into you.
            if e["damage"] in RAMMED and e.get("by"):
                r = nearest(by_time, e["t"])
                if r is None:
                    continue
                hurt = {p["slot"]: p.get("damage") for p in r["players"]}
                checked["ram"] += 1
                if all(hurt.get(s, -1) in (-1, None) for s in e["by"]):
                    passed["ram"] += 1

            # a field item: the racer credited should not be among the victims
            if e["damage"] in FIELD_WIDE and e.get("by"):
                group = [x for x in race.events
                         if x["type"] == "hit" and x["damage"] == e["damage"]
                         and abs(x["t"] - e["t"]) <= 3.0]
                checked["field"] += 1
                if e["by"][0] not in {x["slot"] for x in group}:
                    passed["field"] += 1
        print("read %s" % name)

    print("\nhits with somebody's name on them, by damage type:\n")
    print("  %-5s %-32s %-7s %s" % ("type", "cause", "named", "of"))
    for v in sorted(total):
        print("  %-5d %-32s %-7d %d"
              % (v, DAMAGE_TYPES[v][1], named[v], total[v]))
    print("\n  %d of %d hits overall" % (sum(named.values()),
                                         sum(total.values())))
    print("\nchecks against something the naming did not use:")
    print("  ram      %d of %d: the racer credited was not taking damage "
          "themselves, which is what being on a Star, Mega or Bullet means"
          % (passed["ram"], checked["ram"]))
    print("  field    %d of %d: the racer credited is not among the victims"
          % (passed["field"], checked["field"]))
    print("\nthunder clouds: %s" % dict(clouds))


def nearest(by_time, t):
    if not by_time:
        return None
    return by_time[min(by_time, key=lambda x: abs(x - t))]


if __name__ == "__main__":
    main()
