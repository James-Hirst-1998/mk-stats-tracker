"""Turn per-frame snapshots into a stream of race events.

Everything here is derived from `mkw.reader` output only. The one piece of
inference is `name_launched`, which is marked as such.
"""

from mkw import addresses as A
from mkw.names import COURSES, ITEMS, DAMAGE_TYPES, BY_ITEM

EMPTY = A.EMPTY_ITEM
BLUE_SHELL, BOB_OMB = 7, 6
LAUNCHED = 7


def fmt(sec):
    if sec is None:
        return "-"
    return "%d:%06.3f" % (int(sec // 60), sec % 60)


class Race:
    """Consumes snapshots, emits (clock, text) events."""

    def __init__(self, local_slot=A.LOCAL_SLOT):
        self.local_slot = local_slot
        self.reset()

    def reset(self):
        self.prev = {}
        self.events = []
        self.uses = []                  # (clock, slot, item id)
        self.course = None
        self.started = False

    def who(self, slot):
        return "you" if slot == self.local_slot else "slot %d" % slot

    def log(self, t, text):
        self.events.append((t, text))
        del self.events[:-300]

    def name_launched(self, t):
        """A Bob-omb and a Blue Shell both write damage type 7, so the damage
        field alone says only "launched". The item field separates them.

        Measured, not assumed: across seven recordings, 21 of 23 launched hits
        follow a Blue Shell use by 3.9-6.8s, and one shell catches two or three
        karts within half a second. A Bob-omb goes off next to whoever dropped
        it, inside about 2s. Named only when exactly one of the two fits.
        """
        blue = [u for u in self.uses
                if u[2] == BLUE_SHELL and 3.5 <= t - u[0] <= 7.0]
        bomb = [u for u in self.uses if u[2] == BOB_OMB and t - u[0] <= 3.0]
        if blue and not bomb:
            return "Blue Shell (slot %d's)" % blue[-1][1]
        if bomb and not blue:
            return "Bob-omb (slot %d's)" % bomb[-1][1]
        return None

    def update(self, r):
        if r is None:
            if self.prev:
                self.reset()
            return
        if self.course is None:
            self.course = r["course_code"]
        elif r["course_code"] != self.course:
            self.reset()
            self.course = r["course_code"]

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
                kind, cause = DAMAGE_TYPES.get(b, ("Hit", "something"))
                if b == LAUNCHED:
                    cause = self.name_launched(t) or cause
                self.log(t, "%s hit - %s (%s)%s"
                         % ("you were" if s == self.local_slot
                            else "slot %d was" % s,
                            cause, kind.lower(),
                            "" if b in BY_ITEM else ", not an item"))

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


def splits(cumulative):
    out, prev = [], 0.0
    for c in cumulative:
        if c is None:
            break
        out.append(c - prev)
        prev = c
    return out
