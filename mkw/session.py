"""A sitting: however many races got played between starting the tool and
stopping it.

One directory per session, one file per race inside it, plus an index:

    races/20260812-2013-versus/
      session.json          what it was, and a line per race
      01-luigi-circuit.jsonl
      02-moo-moo-meadows.jsonl
      03-mushroom-gorge.jsonl

Each race is a complete object in its own right - `mkw/racelog.py` reads one
without knowing about sessions at all. The session is what makes "how did the
three of us do across the night" a question you can ask.

The index is rewritten after every race, so stopping the tool with ctrl-c, or
losing it, costs at most the race in progress.
"""

import datetime
import glob
import json
import os

from mkw import racelog
from mkw.events import Field
from mkw.names import COURSES, VS_POINTS

VERSION = 1


class Recorder:
    """Writes races into a session directory as they finish.

    Nothing is created on disk until the first race ends, so starting the tool,
    changing your mind and stopping it leaves no empty directory behind.
    """

    def __init__(self, name=None, root=None, notes=None):
        when = datetime.datetime.now()
        self.root = root or racelog.RACES
        self.name = name or "session"
        self.dir = os.path.join(self.root, "%s-%s" % (
            when.strftime("%Y%m%d-%H%M%S"), racelog.slug(self.name)))
        self.meta = {
            "type": "session",
            "version": VERSION,
            "name": self.name,
            "started": when.isoformat(timespec="seconds"),
            "races": [],
        }
        if notes:
            self.meta["notes"] = notes

    def write_index(self):
        if not self.meta["races"]:
            return
        os.makedirs(self.dir, exist_ok=True)
        self.meta["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(os.path.join(self.dir, "session.json"), "w") as f:
            json.dump(self.meta, f, indent=1)

    def add(self, race):
        """Store a finished `events.Race`. Returns the path, or None."""
        n = len(self.meta["races"]) + 1
        name = racelog.slug(COURSES.get(race.course,
                                        "course-%02x" % (race.course or 0)))
        os.makedirs(self.dir, exist_ok=True)
        path = os.path.join(self.dir, "%02d-%s.jsonl" % (n, name))
        racelog.save(race, path=path, source="live")
        me = next((s for s in race.standings()
                   if s["slot"] == race.local_slot), {})
        self.meta["races"].append({
            "n": n,
            "file": os.path.basename(path),
            "course": race.course,
            "events": len(race.events),
            "your_position": me.get("position"),
            "your_time": me.get("time"),
        })
        self.write_index()
        return path

    def __len__(self):
        return len(self.meta["races"])


class Session:
    """A session, read back. `races` are `racelog.RaceLog`s in order."""

    def __init__(self, path):
        self.path = path
        with open(os.path.join(path, "session.json")) as f:
            self.meta = json.load(f)
        self.races = []
        for row in self.meta.get("races", []):
            full = os.path.join(path, row["file"])
            if os.path.isfile(full):
                self.races.append(racelog.RaceLog(full))
        # A racer is the same person across the session only if the field is;
        # take the names from the first race and let each race name itself.
        self.field = self.races[0].field if self.races else Field()

    @property
    def name(self):
        return self.meta.get("name", os.path.basename(self.path))

    def __len__(self):
        return len(self.races)

    def same_field(self):
        """Is it the same twelve racers, in the same slots, in every race?

        A VS sequence keeps the field, so adding up points across it means
        something. A set of unrelated races does not, and slot 4 being Toadette
        in one and Wario in the next would otherwise be quietly summed into one
        row. Checked rather than assumed.
        """
        seen = None
        for race in self.races:
            who = {r["slot"]: r["character"]
                   for r in race.meta.get("racers", [])}
            if seen is None:
                seen = who
            elif who != seen:
                return False
        return True

    def points(self):
        """{slot: points} on MKW's VS table, plus the finishing positions.

        The table is the published one, not something read out of memory - the
        game's own running total has not been located. It is right for VS; a
        set of unrelated races just gets a number that means nothing.
        """
        out = {}
        for race in self.races:
            for st in race.standings:
                row = out.setdefault(st["slot"], {"points": 0, "finishes": []})
                row["finishes"].append(st["position"])
                row["points"] += VS_POINTS.get(st["position"], 0)
        return out


def find(root=None, which=""):
    """Session directories, oldest first."""
    root = root or racelog.RACES
    return [p for p in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(p, "session.json"))
            and which in os.path.basename(p)]


def latest(root=None):
    got = find(root)
    return got[-1] if got else None
