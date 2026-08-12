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
from mkw.events import Field
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
    with open(path, "w") as f:
        f.write(json.dumps(head) + "\n")
        for e in race.events:
            f.write(json.dumps(e) + "\n")
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
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("type") == "race":
                    self.meta = rec
                elif rec.get("type") == "standings":
                    self.standings = rec.get("standings", [])
                else:
                    self.events.append(rec)
        self.field = Field(self.meta.get("racers"),
                           self.meta.get("local_slot", A.LOCAL_SLOT))

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
    """Stored races, oldest first, optionally filtered by substring."""
    root = root or RACES
    return [p for p in sorted(glob.glob(os.path.join(root, "*.jsonl")))
            if which in os.path.basename(p)]


def latest(root=None):
    got = find(root)
    return got[-1] if got else None
