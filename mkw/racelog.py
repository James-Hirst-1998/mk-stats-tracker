"""Store a race as its events, and read one back.

A recording is a gigabyte because it is every byte of the console's memory
twenty times a second. Almost none of that is worth keeping once the events
have been read out of it. A race log keeps only the events - tens of kilobytes
- and everything the tracker reports can be rebuilt from it.

One file per race, JSON Lines, so it is appendable, greppable, diffable, and
readable without this repo. Three kinds of record:

    {"type": "race", ...}        exactly one, first: who raced, where, when
    {"t": 12.3, "type": ...}     the events, in race order
    {"type": "standings", ...}   exactly one, last: final state per racer

Times are seconds from GO, on the game's own clock. Ids are stored, not names,
so `mkw.names` can be corrected later without the stored races going stale.

A reader must ignore record types and fields it does not know: that is what
makes adding a new event safe. `VERSION` goes up only if the meaning of an
existing field changes.
"""

import datetime
import glob
import json
import os

from mkw import addresses as A
from mkw.events import Field, TRACK_HZ, JUMP
from mkw.names import COURSES

VERSION = 1

RACES = os.environ.get(
    "MKW_RACES",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "races"))


def slug(text):
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "race"


def filename(course, when=None, root=None):
    when = when or datetime.datetime.now()
    return os.path.join(root or RACES, "%s-%s.jsonl" % (
        when.strftime("%Y%m%d-%H%M%S"),
        slug(COURSES.get(course, "course-%02x" % (course or 0)))))


def save(race, path=None, source=None, notes=None, root=None):
    """Write a finished `events.Race` out. Returns the path written."""
    when = datetime.datetime.now()
    path = path or filename(race.course, when, root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    head = {
        "type": "race",
        "version": VERSION,
        "recorded": when.isoformat(timespec="seconds"),
        "course": race.course,
        "laps": race.lap_count(),
        # Race time of the first frame seen. Non-zero means the race was
        # already running, and nothing before it was observed.
        "begins": round(race.begins, 3),
        "local_slot": race.local_slot,
        "racers": race.racers or [],
    }
    if source:
        head["source"] = source
    if notes:
        head["notes"] = notes
    if race.settings:
        # Undecoded on purpose - see mkw/addresses.py. Kept so a question about
        # VS sequences can be answered from races already stored.
        head["settings"] = ["0x%08x" % w for w in race.settings]
    with open(path, "w") as f:
        f.write(json.dumps(head) + "\n")
        for e in race.events:
            f.write(json.dumps(e) + "\n")
        if race.track:
            f.write(json.dumps({
                "type": "progress", "hz": TRACK_HZ,
                "t0": round(race.begins, 3),
                "completion": {str(s): v for s, v in sorted(race.track.items())},
            }) + "\n")
        f.write(json.dumps({"type": "standings",
                            "standings": race.standings()}) + "\n")
    return path


class RaceLog:
    """A stored race, read back."""

    def __init__(self, path):
        self.path = path
        self.meta = {}
        self.events = []
        self.standings = []
        self.track = {}
        self.track_hz = TRACK_HZ
        self.track_t0 = 0.0
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                kind = rec.get("type")
                if kind == "race":
                    self.meta = rec
                elif kind == "standings":
                    self.standings = rec.get("standings", [])
                elif kind == "progress":
                    self.track = {int(k): v
                                  for k, v in rec.get("completion", {}).items()}
                    self.track_hz = rec.get("hz", TRACK_HZ)
                    self.track_t0 = rec.get("t0", 0.0)
                else:
                    self.events.append(rec)
        self.field = Field(self.meta.get("racers"),
                           self.meta.get("local_slot", A.LOCAL_SLOT))

    # --- replaying the race ------------------------------------------------

    def track_times(self):
        n = max((len(v) for v in self.track.values()), default=0)
        return [round(self.track_t0 + k / float(self.track_hz), 3)
                for k in range(n)]

    def progress_at(self, t):
        """{slot: progress} at any moment, interpolated between samples.

        Progress is lap plus fraction of a lap, so the difference between two
        racers is the gap between them and sorting by it is the running order -
        which agrees with the position the game reports 98-99% of the time and
        no better, so `pos` events remain the authority on position.
        """
        if not self.track:
            return {}
        x = (t - self.track_t0) * self.track_hz
        i = int(x)
        frac = x - i
        out = {}
        for slot, row in self.track.items():
            if not row:
                continue
            j = min(max(i, 0), len(row) - 1)
            k = min(j + 1, len(row) - 1)
            f = frac if j == i else 0.0
            # Crossing the line puts progress back to the start of the last
            # lap, so a step that big is a jump, not motion.
            if abs(row[k] - row[j]) > JUMP:
                out[slot] = row[j] if f < 0.5 else row[k]
            else:
                out[slot] = row[j] + (row[k] - row[j]) * f
        return out

    def order_at(self, t):
        """The running order at any moment: slots, leader first."""
        return [s for s, _ in sorted(self.progress_at(t).items(),
                                     key=lambda kv: -kv[1])]

    def events_between(self, a, b):
        return [e for e in self.events if a <= e["t"] < b]

    @property
    def course(self):
        return self.meta.get("course")

    @property
    def course_name(self):
        return COURSES.get(self.course, "course 0x%02x" % (self.course or 0))

    @property
    def local_slot(self):
        return self.meta.get("local_slot", A.LOCAL_SLOT)

    def of_type(self, *types):
        return [e for e in self.events if e["type"] in types]

    def slots(self):
        return sorted(r["slot"] for r in self.meta.get("racers", [])) or \
            sorted({e["slot"] for e in self.events if "slot" in e})

    def __len__(self):
        return len(self.events)


def find(root=None, which=""):
    """Stored races, oldest first. Loose files only - a race inside a session
    directory belongs to that session, and `mkw.session` finds those."""
    root = root or RACES
    return [p for p in sorted(glob.glob(os.path.join(root, "*.jsonl")))
            if which in os.path.basename(p)]


def latest(root=None):
    got = find(root)
    return got[-1] if got else None
