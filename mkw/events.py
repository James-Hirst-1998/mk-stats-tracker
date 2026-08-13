"""Turn per-frame snapshots into a stream of race events.

An event is a small dict: a race time `t`, a `type`, and whatever that type
needs. Ids are stored, never names - `mkw.names` turns 7 into "Blue Shell", and
a better name later should not mean re-running a race. The text the live view
prints is produced from the same dicts by `describe`, so what is shown and what
is stored cannot drift apart.

Adding a new event type is: detect it in `update`, give it a name and fields
here, add a line to `describe`, and say what it means in `docs/RACE_LOG.md`.
Readers ignore types they do not know, so old files keep working.

Everything here is derived from `mkw.reader` output only. The one piece of
inference left is `name_launched`, which is marked as such in the event itself
(`"guess": true`) and is only a fallback.
"""

import bisect
from collections import Counter

from mkw import addresses as A
from mkw.names import (course_name, ITEMS, DAMAGE_TYPES, BY_ITEM, OBJECT_TYPES,
                       DAMAGE_FROM_OBJECT, DROPS_ITEM, CHARACTERS, VEHICLES)

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

# The race clock resets to 0 for the next countdown, which is how a second race
# is told from the first even when it is on the same course. One frame of it is
# not trusted for the same reason one unreadable frame is not: a live snapshot
# can tear. Two in a row cannot be a tear, and the countdown lasts 137 frames
# at 20 Hz, so there is no hurry.
RESTART = 3

# How often the racers' progress is sampled, in race seconds. This is what a
# race is replayed from - position and gap at any moment come out of it - and
# it is the only thing here that is not an event. 5 Hz costs about 70 kB in a
# 3-minute race and progress is smooth enough between samples to interpolate.
TRACK_HZ = 5

# Progress is lap plus fraction of a lap and climbs smoothly, EXCEPT at the
# finish, where crossing the line puts it back to the start of the last lap -
# 3.9994 then 3.0002, measured on GCN Peach Beach. Interpolating across that
# gives a value a whole lap out, so a step this big is treated as the jump it
# is and the nearer of the two readings is taken instead.
JUMP = 0.5

# Stored, but not printed. Twelve racers jostling produce a few hundred
# position swaps in a race, most of them in the first two seconds off the grid.
# They are what "who was in front, and when" is rebuilt from, so they are kept;
# they are just not something to read past.
QUIET = ("pos",)


def readable(events):
    return [e for e in events if e["type"] not in QUIET]


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


class Field:
    """Display names for the twelve slots.

    Characters are unique in every race seen so far, so the character name on
    its own identifies a racer. It is not guaranteed - Miis and online races
    can repeat one - so a repeat gets a number rather than two racers sharing
    a name. Built the same way from a live read and from a stored log, so a
    replayed race reads identically to the one that was played.
    """

    def __init__(self, racers=None, local_slot=A.LOCAL_SLOT):
        self.local_slot = local_slot
        self.racers = racers
        self.names = {}
        if racers:
            repeated = Counter(r["character"] for r in racers)
            used = Counter()
            for r in racers:
                c = r["character"]
                name = CHARACTERS.get(
                    c, "Mii" if c > max(CHARACTERS) else "?%d" % c)
                if repeated[c] > 1:
                    used[c] += 1
                    name = "%s #%d" % (name, used[c])
                self.names[r["slot"]] = name

    def who(self, slot):
        if slot == self.local_slot:
            return "you"
        return self.names.get(slot, "slot %d" % slot)

    def name(self, slot):
        return self.names.get(slot, "slot %d" % slot)

    def whose(self, slot):
        if slot == self.local_slot:
            return "yours"
        n = self.name(slot)
        return n + ("'" if n.endswith("s") else "'s")

    def owners(self, slots):
        if not slots:
            return None
        return " and ".join(self.whose(s) for s in slots)

    def me(self):
        return next((r for r in (self.racers or [])
                     if r["slot"] == self.local_slot), None)


def describe(ev, field):
    """One line of English for an event. The live view and the stored log both
    go through here, so they cannot say different things."""
    t, k = ev["type"], ev
    if t == "start":
        return "race start - %s" % course_name(ev.get("course"))
    if t == "field":
        return ev.get("text", "")
    if t == "box":
        return "%s hit a box - roulette will land on %s" % (
            field.who(k["slot"]), ITEMS.get(k["item"], k["item"]))
    if t == "hold":
        return "%s now holding %s" % (field.who(k["slot"]),
                                      ITEMS.get(k["item"], k["item"]))
    if t == "use":
        return "%s used %s" % (field.who(k["slot"]),
                               ITEMS.get(k["item"], k["item"]))
    if t == "lost":
        return "%s lost %s - %s" % (
            field.who(k["slot"]), ITEMS.get(k["item"], k["item"]),
            DAMAGE_TYPES.get(k["damage"], ("hit", "something"))[1])
    if t == "swap":
        return "%s %s -> %s" % (field.who(k["slot"]),
                                ITEMS.get(k["from"], k["from"]),
                                ITEMS.get(k["to"], k["to"]))
    if t == "hit":
        kind, cause = DAMAGE_TYPES.get(k["damage"], ("Hit", "something"))
        named = None
        if k.get("object") is not None:
            named = "%s (%s)" % (
                OBJECT_TYPES.get(k["object"], "item %d" % k["object"]),
                field.owners(k.get("by")) or "unknown")
        return "%s hit - %s (%s)%s%s" % (
            "you were" if k["slot"] == field.local_slot
            else "%s was" % field.who(k["slot"]),
            named or cause, kind.lower(),
            "" if k["damage"] in BY_ITEM else ", not an item",
            "?" if k.get("guess") else "")
    if t == "lap":
        return "%s completed lap %d in %s" % (field.who(k["slot"]), k["lap"],
                                              fmt(k["split"]))
    if t == "finish":
        return "%s FINISHED P%d in %s" % (field.who(k["slot"]), k["position"],
                                          fmt(k["time"]))
    if t == "pos":
        return "%s P%d -> P%d" % (field.who(k["slot"]), k["from"], k["to"])
    return "%s %s" % (t, {a: b for a, b in ev.items()
                          if a not in ("t", "type")})


class Race:
    """Consumes snapshots, emits events. Call `end` when the race is over."""

    def __init__(self, local_slot=A.LOCAL_SLOT, on_end=None):
        self.local_slot = local_slot
        self.on_end = on_end
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
        self.settings = None
        self.started = False
        self.field_logged = False
        self.begins = 0.0           # race time of the first frame actually seen
        self.missed = 0
        self.restarted = 0
        self.peak = 0.0             # highest race clock seen in this race
        self.track = {}             # slot -> progress samples, TRACK_HZ apart
        self.next_sample = 0.0
        self.prev_track = (0.0, {})
        self.last = None            # last readable snapshot, for the standings
        self.field = Field(None, self.local_slot)

    # --- who is driving ----------------------------------------------------

    @property
    def racers(self):
        return self.field.racers

    @property
    def names(self):
        return self.field.names

    def who(self, slot):
        return self.field.who(slot)

    def name_racers(self, racers):
        if racers is None or racers == self.field.racers:
            return
        self.field = Field(racers, self.local_slot)

    def log_field(self):
        """Lines naming everyone, so the log says who the CPUs were.

        RaceConfig can be unreadable at the moment the lights go out - it is a
        separate pointer path in MEM2 and `read_racers` refuses to guess - so
        the race starts without a field and picks the names up on a later
        frame. That is a missing line, not a reason to stop.
        """
        if not self.racers:
            return
        self.field_logged = True
        me = self.field.me()
        if me is not None:
            self.log(self.begins, "field", text="you are %s on the %s, starting %s"
                     % (self.field.name(me["slot"]),
                        VEHICLES.get(me["vehicle"], "vehicle %d" % me["vehicle"]),
                        ordinal(me["grid"])))
        for cpu in (False, True):
            who = [self.field.name(r["slot"]) for r in self.racers
                   if r["cpu"] == cpu and r["slot"] != self.local_slot]
            if who:
                self.log(self.begins, "field", text="%d %s: %s"
                         % (len(who), "CPU" if cpu else "human", ", ".join(who)))

    def log(self, t, type, **fields):
        """Insert in race order; a hit is logged after later events arrive."""
        ev = dict(t=round(t, 3), type=type, **fields)
        i = bisect.bisect_right([e["t"] for e in self.events], ev["t"])
        self.events.insert(i, ev)
        return ev

    def text(self, ev):
        return describe(ev, self.field)

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
        """(object type, owners) for the item that did it, or None.

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
        return pick[0][1], sorted({d[2] for d in pick})

    def name_launched(self, t):
        """Fallback for a launch whose object was missed. Marked as a guess.

        A Bob-omb and a Blue Shell both write damage type 7, so the damage field
        alone says only "launched". Measured across seven recordings, 21 of 23
        launched hits follow a Blue Shell use by 3.9-6.8s, and a Bob-omb goes off
        within about 2s of being dropped. Named only when exactly one fits.
        """
        blue = [u for u in self.uses
                if u[2] == BLUE_SHELL and 3.5 <= t - u[0] <= 7.0]
        bomb = [u for u in self.uses if u[2] == BOB_OMB and t - u[0] <= 3.0]
        if blue and not bomb:
            return 5, [blue[-1][1]]
        if bomb and not blue:
            return 9, [bomb[-1][1]]
        return None

    def log_hit(self, t, slot, damage):
        named = self.name_hit(t, slot, damage)
        guess = False
        if named is None and damage == LAUNCHED:
            named = self.name_launched(t)
            guess = named is not None
        obj, by = named if named else (None, None)
        ev = dict(slot=slot, damage=damage, object=obj, by=by)
        if guess:
            ev["guess"] = True
        self.log(t, "hit", **ev)

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

    # --- progress over time ------------------------------------------------

    def sample(self, r):
        """Every racer's progress, on a fixed grid, for replaying the race.

        The events say what happened; this says where everyone was while it
        happened, which is what a gap, a chase or an overtake is made of. On a
        grid rather than per frame so a sample index is a time and the arrays
        stay the same length - a dropped frame repeats the last value rather
        than shifting everything after it.
        """
        now = {p["slot"]: p["completion"] for p in r["players"]}
        if not self.started:
            self.prev_track = (self.clock, now)
            return
        while self.clock >= self.next_sample:
            for slot, value in now.items():
                self.track.setdefault(slot, []).append(
                    round(between(self.prev_track, (self.clock, now),
                                  slot, self.next_sample), 4))
            self.next_sample += 1.0 / TRACK_HZ
        self.prev_track = (self.clock, now)

    # --- the end of a race -------------------------------------------------

    def standings(self):
        """Final state per racer, straight off the last readable snapshot.

        Stored alongside the events so a report does not have to replay them,
        and so the game's own numbers - lap times, finish time, time spent
        leading - are kept as read rather than re-derived.

        `finish` reads back the *current* race time for a racer still going, so
        it is only kept once they have actually crossed the line.
        """
        if self.last is None:
            return []
        return [{"slot": p["slot"], "position": p["position"],
                 "finished": p["finished"],
                 "time": p["finish"] if p["finished"] else None,
                 "lap_reached": p["lap_reached"],
                 "laps": splits(p["cumulative"]),
                 # +0x30 as read. It starts at the intro, not at GO, so
                 # whoever is on pole is credited the countdown - about 6.87s
                 # they did not spend racing. Kept raw and corrected where it
                 # is used, rather than fudged here.
                 "leading": round(p["leading"], 3),
                 # +0x2C stops when this racer's race ends, so this is how long
                 # they were racing: their finish time, or where they got to
                 # when the race ended around them.
                 "raced": round(p["clock"] - A.COUNTDOWN_FRAMES / 60.0, 3)}
                for p in sorted(self.last["players"],
                                key=lambda x: x["position"])]

    def lap_count(self):
        """How many laps the race was.

        Not a field the game exposes anywhere this repo has found: +0x26 is the
        highest lap a racer has *reached*, not the length of the race. Whoever
        finished reached the last lap, so the maximum over the field is it. A
        race abandoned before anyone finished will under-report.
        """
        return max((s["lap_reached"] for s in self.standings()), default=None)

    def worth_keeping(self):
        """A race that never started is menu noise, not a race."""
        return self.started and any(e["type"] not in ("start", "field")
                                    for e in self.events)

    def end(self):
        """Close the race off and hand it to `on_end`. Safe to call twice."""
        self.flush()
        if self.on_end and self.worth_keeping():
            self.on_end(self)
        self.started = False

    # --- the snapshot loop -------------------------------------------------

    def update(self, r):
        if r is None:
            # One unreadable frame is a torn read, not the end of the race.
            self.missed += 1
            if self.prev and self.missed >= DROPOUT:
                self.end()
                self.reset()
            return
        self.missed = 0

        # A second race on the same course looks identical to the first except
        # that the clock has gone back to the countdown. That, not the course,
        # is what separates the races in a session - the course only changes
        # between them if the next race is somewhere else.
        # Against the highest clock this race has reached, not against the last
        # frame: once one frame has been seen at 0 the last frame is 0 too, so
        # comparing with that makes the second frame look normal and the run of
        # them never reaches RESTART. Two races on the same course then end up
        # in one file, which is the whole thing this is here to prevent.
        course = r["course_code"]
        now = r.get("race_time") or 0.0
        back = self.started and now < self.peak
        self.restarted = self.restarted + 1 if back else 0
        moved = (course is not None and self.course is not None
                 and course != self.course)
        if moved or self.restarted >= RESTART:
            self.end()
            self.reset()
        if course is not None:
            self.course = course
        self.last = r
        if r.get("settings"):
            self.settings = r["settings"]

        # The race clock, not the per-racer frame counter: that one starts at
        # the intro camera 412 frames early and freezes when a racer finishes.
        self.clock = now
        self.peak = max(self.peak, now)
        self.name_racers(r.get("racers"))

        if not self.started and r.get("race_frames"):
            self.started = True
            # Not always 0: a recording, or the tool, can be started after the
            # lights have gone out. Everything before this was never seen, and
            # a reader has to know that rather than assume the grid held.
            self.begins = self.clock
            self.next_sample = self.clock       # anchor the progress grid
            self.log(self.clock, "start", course=self.course)
        if self.started and not self.field_logged:
            self.log_field()
        self.sample(r)

        for p in r["players"]:
            s = p["slot"]
            old = self.prev.get(s)
            self.prev[s] = dict(p)
            if old is None:
                continue
            t = self.clock

            if p["lap"] > old["lap"]:
                sp = splits(p["cumulative"])
                done = old["lap"]
                if p["finished"]:
                    self.log(p["finish"] if p["finish"] is not None else t,
                             "finish", slot=s, position=p["position"],
                             time=p["finish"])
                elif 0 < done <= len(sp):
                    self.log(t, "lap", slot=s, lap=done, split=sp[done - 1],
                             total=p["cumulative"][done - 1])

            if p["position"] != old["position"] and self.started:
                self.log(t, "pos", slot=s, **{"from": old["position"],
                                              "to": p["position"]})

            a, b = old.get("roulette"), p.get("roulette")
            if a == EMPTY and b not in (None, EMPTY):
                self.log(t, "box", slot=s, item=b)

            a, b = old.get("damage"), p.get("damage")
            if a is not None and b is not None and a != b and b >= 0:
                self.pending.append((t, s, b))

            a, b = old.get("item"), p.get("item")
            if a is not None and b is not None and a != b:
                if a == EMPTY:
                    self.log(t, "hold", slot=s, item=b)
                elif b == EMPTY:
                    # An item leaving somebody's hands is a throw unless it
                    # was knocked out of them: being flipped, flattened or
                    # shocked costs you what you were holding, a spin-out or a
                    # knockback does not. Which of the two it was is a state,
                    # not a coincidence in time - the damage field is still
                    # reading the hit at the moment the item goes - so no
                    # window is needed and none is used. A window was tried
                    # first and is worse: it depends on catching the exact
                    # frame the hit began, and a partly unreadable snapshot
                    # moves that by half a second. Being taken off you is not
                    # a throw either, so it stays out of `uses` and cannot be
                    # credited with an object that appears near it.
                    # `analysis/validate_item_loss.py`.
                    hurt = p.get("damage")
                    if hurt in DROPS_ITEM:
                        self.log(t, "lost", slot=s, item=a, damage=hurt)
                    else:
                        self.uses.append((t, s, a))
                        self.uses = [u for u in self.uses if t - u[0] <= 20.0]
                        self.log(t, "use", slot=s, item=a)
                else:
                    self.log(t, "swap", slot=s, **{"from": a, "to": b})

        # After the item uses above, so an object that appears in the same
        # frame as the throw can still be tied to it.
        self.watch_items(self.clock, r.get("world_items"))
        self.settle(self.clock)


def between(before, after, slot, t):
    """One racer's progress at exactly `t`, from the frames either side.

    The sampler is driven by frames arriving at 20 Hz and the grid is 5 Hz, so
    without this a sample would carry the value from up to a frame after the
    time it claims - a quarter of a grid step, and a whole lap out if that
    frame is the one where the racer crossed the line.
    """
    (t0, a), (t1, b) = before, after
    if slot not in a or slot not in b or t1 <= t0:
        return b.get(slot, a.get(slot, 0.0))
    f = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
    if abs(b[slot] - a[slot]) > JUMP:
        return a[slot] if f < 0.5 else b[slot]
    return a[slot] + (b[slot] - a[slot]) * f


def splits(cumulative):
    out, prev = [], 0.0
    for c in cumulative:
        if c is None:
            break
        out.append(round(c - prev, 3))
        prev = c
    return out
