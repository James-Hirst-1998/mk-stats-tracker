"""Turn per-frame snapshots into a stream of race events.

Everything here is derived from `mkw.reader` output only. The one piece of
inference left is `name_launched`, which is marked as such and is now only a
fallback.
"""

import bisect
from collections import Counter

from mkw import addresses as A
from mkw.names import (COURSES, ITEMS, DAMAGE_TYPES, BY_ITEM, OBJECT_TYPES,
                       DAMAGE_FROM_OBJECT, CHARACTERS, VEHICLES)

EMPTY = A.EMPTY_ITEM
BLUE_SHELL, BOB_OMB = 7, 6
LAUNCHED = 7

# The object that hit you is destroyed a fixed delay later, while it breaks or
# explodes. Measured across seven recordings, not assumed: for a shell, banana
# or box the despawn follows the hit by 0.25-0.40s - 20 game frames, sharply
# peaked against a flat background - and for an explosion by 1-2s. A hit is
# therefore held back until its window has passed and then reported with the
# item named, rather than reported twice.
LAG = {0: (0.20, 0.45), 2: (0.20, 0.45), 7: (0.60, 2.50)}
SPAWN_WINDOW = 1.0              # a thrown item appears within this of the throw
KEEP = 6.0                      # seconds of despawn history worth holding

# Live, a snapshot is ~300 separate reads of a game still running at 60Hz, so
# now and then one lands mid-update and `read_players` sees two racers in the
# same position. It correctly refuses to guess and returns None. Treating that
# single frame as "the race ended" wiped the log and restarted it from 0:00,
# which is what James was seeing. A real race ending gives an unbroken run of
# them, so wait for one. Offline this never fires: 0 dropouts in 21,926 frames
# across seven recordings, because a recording is one consistent image.
DROPOUT = 20                    # unreadable frames in a row before giving up


def fmt(sec):
    if sec is None:
        return "-"
    return "%d:%06.3f" % (int(sec // 60), sec % 60)


def ordinal(n):
    if n is None:
        return "?"
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10, "th")
    return "%d%s" % (n, suffix)


class Race:
    """Consumes snapshots, emits (clock, text) events."""

    def __init__(self, local_slot=A.LOCAL_SLOT):
        self.local_slot = local_slot
        self.reset()

    def reset(self):
        self.prev = {}
        self.events = []
        self.uses = []              # (clock, slot, item id)
        self.pending = []           # hits waiting for their object to despawn
        self.despawns = []          # (clock, object type, owner, thrown as)
        self.world = None           # {object address: (type, owner)}
        self.born = {}              # object address -> the item id thrown
        self.clock = 0.0
        self.course = None
        self.started = False
        self.missed = 0
        self.racers = None
        self.names = {}

    # --- who is driving ----------------------------------------------------

    def name_racers(self, racers):
        """Build a display name per slot. Falls back to the slot number.

        Characters are unique in every race seen so far, so the character name
        on its own identifies a racer. It is not guaranteed - Miis and online
        races can repeat one - so a repeat gets a number rather than two racers
        sharing a name.
        """
        if racers is None or racers == self.racers:
            return
        self.racers = racers
        repeated = Counter(r["character"] for r in racers)
        used = Counter()
        self.names = {}
        for r in racers:
            c = r["character"]
            name = CHARACTERS.get(c, "Mii" if c > max(CHARACTERS) else "?%d" % c)
            if repeated[c] > 1:
                used[c] += 1
                name = "%s #%d" % (name, used[c])
            self.names[r["slot"]] = name

    def who(self, slot):
        if slot == self.local_slot:
            return "you"
        return self.names.get(slot, "slot %d" % slot)

    def whose(self, slot):
        if slot == self.local_slot:
            return "yours"
        name = self.names.get(slot, "slot %d" % slot)
        return name + ("'" if name.endswith("s") else "'s")

    def log_field(self):
        """One line naming everyone, so the log says who the CPUs were."""
        if not self.racers:
            return
        me = next((r for r in self.racers if r["slot"] == self.local_slot), None)
        if me is not None:
            self.log(0.0, "you are %s on the %s, starting %s"
                     % (self.names.get(me["slot"], "?"),
                        VEHICLES.get(me["vehicle"], "vehicle %d" % me["vehicle"]),
                        ordinal(me["grid"])))
        for cpu in (False, True):
            who = [self.names[r["slot"]] for r in self.racers
                   if r["cpu"] == cpu and r["slot"] != self.local_slot]
            if who:
                self.log(0.0, "%d %s: %s"
                         % (len(who), "CPU" if cpu else "human", ", ".join(who)))

    def log(self, t, text):
        """Insert in race order; a hit is logged after later events arrive."""
        i = bisect.bisect_right([e[0] for e in self.events], t)
        self.events.insert(i, (t, text))
        del self.events[:-300]

    # --- items in the world ------------------------------------------------

    def spawned_by(self, now, owner):
        """The item id whose use produced this object, if that is unambiguous."""
        cand = [u for u in self.uses
                if u[1] == owner and 0.0 <= now - u[0] <= SPAWN_WINDOW]
        return cand[0][2] if len(cand) == 1 else None

    def watch_items(self, now, world):
        """Keep a short log of items that left the world, and why they existed."""
        if world is None:
            return
        if self.world is not None:
            for a, v in world.items():
                if a not in self.world:
                    self.born[a] = self.spawned_by(now, v[1])
            for a, v in self.world.items():
                if a not in world:
                    self.despawns.append((now, v[0], v[1],
                                          self.born.pop(a, None)))
        self.world = world
        self.despawns = [d for d in self.despawns if now - d[0] <= KEEP]

    # --- hits --------------------------------------------------------------

    def name_hit(self, t, slot, damage):
        """Which item did it, from the object destroyed by the hit.

        Only object types whose `getDamageType` can return this damage type are
        considered - that mapping is read out of the game's code, not guessed -
        so a green shell, a red shell and a fake item box are told apart by
        which pool lost an entry.
        """
        types = DAMAGE_FROM_OBJECT.get(damage)
        if not types:
            return None
        lo, hi = LAG[damage]
        cand = [d for d in self.despawns
                if d[1] in types and lo <= d[0] - t <= hi]
        # your own shell will not break on you, but you can drive into a banana
        # you dropped yourself, so only prefer other racers' objects
        pick = [d for d in cand if d[2] != slot] or cand
        if len({d[1] for d in pick}) != 1:
            return None
        owners = sorted({d[2] for d in pick})
        return "%s (%s)" % (OBJECT_TYPES.get(pick[0][1], "item %d" % pick[0][1]),
                            " and ".join(self.whose(o) for o in owners))

    def name_launched(self, t):
        """Fallback for a launch whose object was missed.

        A Bob-omb and a Blue Shell both write damage type 7, so the damage field
        alone says only "launched". Measured across seven recordings, 21 of 23
        launched hits follow a Blue Shell use by 3.9-6.8s, and a Bob-omb goes off
        within about 2s of being dropped. Named only when exactly one fits.
        """
        blue = [u for u in self.uses
                if u[2] == BLUE_SHELL and 3.5 <= t - u[0] <= 7.0]
        bomb = [u for u in self.uses if u[2] == BOB_OMB and t - u[0] <= 3.0]
        if blue and not bomb:
            return "Blue Shell (slot %d's)" % blue[-1][1]
        if bomb and not blue:
            return "Bob-omb (slot %d's)" % bomb[-1][1]
        return None

    def log_hit(self, t, slot, damage):
        kind, cause = DAMAGE_TYPES.get(damage, ("Hit", "something"))
        named = self.name_hit(t, slot, damage)
        if named is None and damage == LAUNCHED:
            named = self.name_launched(t)
        self.log(t, "%s hit - %s (%s)%s"
                 % ("you were" if slot == self.local_slot
                    else "%s was" % self.who(slot),
                    named or cause, kind.lower(),
                    "" if damage in BY_ITEM else ", not an item"))

    def settle(self, now, force=False):
        """Report any hit whose object has had time to despawn."""
        keep = []
        for t, slot, damage in self.pending:
            if not force and now < t + LAG.get(damage, (0.0, 0.0))[1]:
                keep.append((t, slot, damage))
            else:
                self.log_hit(t, slot, damage)
        self.pending = keep

    def flush(self):
        """Report everything still waiting; for the end of a race."""
        self.settle(self.clock, force=True)

    # --- the snapshot loop -------------------------------------------------

    def update(self, r):
        if r is None:
            # One unreadable frame is a torn read, not the end of the race.
            self.missed += 1
            if self.prev and self.missed >= DROPOUT:
                self.flush()
                self.reset()
            return
        self.missed = 0
        if self.course is None:
            self.course = r["course_code"]
        elif r["course_code"] != self.course:
            self.flush()
            self.reset()
            self.course = r["course_code"]

        self.clock = max(p["clock"] for p in r["players"])
        self.name_racers(r.get("racers"))

        for p in r["players"]:
            s = p["slot"]
            old = self.prev.get(s)
            self.prev[s] = dict(p)
            if old is None:
                continue
            t = p["clock"]

            if not self.started and p["completion"] > old["completion"] + 1e-4:
                self.started = True
                self.log(0.0, "race start - %s"
                         % COURSES.get(self.course,
                                       "course 0x%02x" % (self.course or 0)))
                self.log_field()

            if p["lap"] > old["lap"]:
                sp = splits(p["cumulative"])
                done = old["lap"]
                if p["finished"]:
                    self.log(p["finish"] if p["finish"] is not None else t,
                             "%s FINISHED P%d in %s"
                             % (self.who(s), p["position"], fmt(p["finish"])))
                elif 0 < done <= len(sp):
                    self.log(t, "%s completed lap %d in %s"
                             % (self.who(s), done, fmt(sp[done - 1])))

            a, b = old.get("roulette"), p.get("roulette")
            if a == EMPTY and b not in (None, EMPTY):
                self.log(t, "%s hit a box - roulette will land on %s"
                         % (self.who(s), ITEMS.get(b, b)))

            a, b = old.get("damage"), p.get("damage")
            if a is not None and b is not None and a != b and b >= 0:
                self.pending.append((t, s, b))

            a, b = old.get("item"), p.get("item")
            if a is not None and b is not None and a != b:
                if a == EMPTY:
                    self.log(t, "%s now holding %s"
                             % (self.who(s), ITEMS.get(b, b)))
                elif b == EMPTY:
                    self.uses.append((t, s, a))
                    self.uses = [u for u in self.uses if t - u[0] <= 20.0]
                    self.log(t, "%s used %s" % (self.who(s), ITEMS.get(a, a)))
                else:
                    self.log(t, "%s %s -> %s"
                             % (self.who(s), ITEMS.get(a, a), ITEMS.get(b, b)))

        # After the item uses above, so an object that appears in the same
        # frame as the throw can still be tied to it.
        self.watch_items(self.clock, r.get("world_items"))
        self.settle(self.clock)


def splits(cumulative):
    out, prev = [], 0.0
    for c in cumulative:
        if c is None:
            break
        out.append(c - prev)
        prev = c
    return out
