#!/usr/bin/env python3
"""Offline: the moments between races, which are where things break.

James lost a session to a crash at the start of his second race: `read_course`
returns None while the course pointer is being rebuilt, and the header
formatted it with `%02x`. One race was already safely on disk, but the tool
died and the rest of the night went unrecorded.

The lesson is not "fix that one format string". It is that the frames between
races are a normal thing to be handed and almost nothing exercises them, so
they get checked here. Every field a snapshot carries is set to None in turn,
and the whole loop - the event stream and the display - has to survive it.

  1. `Race.update` accepts a snapshot with any single field missing
  2. `render` draws something for every one of those, and never raises
  3. the specific shape James hit: course None, mid-session, race two starting

Run (no sudo):
  mk/bin/python3 -m analysis.validate_transitions
"""

import tempfile

from mkw import session as sess
from mkw.events import Race
from tools.track import render, header

SLOTS = 12


def snapshot(frames=60, course=2, racers=True, settings=True, world=True):
    return {
        "course_code": course,
        "race_frames": frames,
        "race_time": None if frames is None else frames / 60.0,
        "racers": [{"slot": i, "character": i, "vehicle": i % 3,
                    "type": 0 if i == 0 else 1, "cpu": i != 0,
                    "grid": SLOTS - i} for i in range(SLOTS)] if racers else None,
        "settings": [0] * 16 if settings else None,
        "world_items": {} if world else None,
        "players": [{"slot": i, "position": i + 1, "lap": 1, "lap_reached": 1,
                     "completion": 1.0 + i * 0.01, "lap_fraction": 0.1,
                     "clock": 10.0, "leading": 0.0, "cumulative": [],
                     "finished": False, "finish": None,
                     "item": 20, "roulette": 20, "damage": -1}
                    for i in range(SLOTS)],
    }


def blank(field):
    """A snapshot with one field missing, the way a torn read gives one."""
    r = snapshot()
    if field == "course_code":
        r["course_code"] = None
    elif field == "race_frames":
        r["race_frames"], r["race_time"] = None, None
    elif field in ("racers", "settings", "world_items"):
        r[field] = None
    else:
        for p in r["players"]:
            p[field] = None
    return r


FIELDS = ["course_code", "race_frames", "racers", "settings", "world_items",
          "item", "roulette", "damage", "finish"]


def main():
    ok = True
    with tempfile.TemporaryDirectory() as root:
        rec = sess.Recorder(name="transitions", root=root)

        for field in FIELDS:
            race = Race()
            race.update(snapshot())          # a normal frame first
            try:
                race.update(blank(field))
                drew = render(blank(field), race, rec)
                good = isinstance(drew, str) and len(drew) > 0
            except Exception as exc:
                good = False
                drew = repr(exc)
            ok &= good
            print("  %s %-14s None -> %s"
                  % ("PASS" if good else "FAIL", field,
                     drew.splitlines()[0] if good else drew))

        # The exact sequence: a race finishes, the clock goes back, and the
        # course is briefly unreadable while the next one loads. Both races are
        # on the same course, which is the case the old course-change test
        # would have merged into one file.
        print()

        def racing(step, course=2):
            """A frame of a race where something is actually happening."""
            r = snapshot(frames=step * 12, course=course)
            for p in r["players"]:
                p["completion"] = 1.0 + step * 0.02 + p["slot"] * 0.01
                # two racers trading places, and one picking an item up and
                # throwing it, so the race has events and is worth keeping
                if p["slot"] == 0:
                    p["position"] = 1 if step % 20 < 10 else 2
                    p["item"] = 2 if 5 <= step % 20 < 8 else 20
                elif p["slot"] == 1:
                    p["position"] = 2 if step % 20 < 10 else 1
            return r

        stored = []
        race = Race(on_end=lambda r: stored.append(r.course))
        try:
            for step in range(60):                  # race one
                race.update(racing(step))
            for _ in range(4):                      # between races
                r = snapshot(course=None, frames=0)
                race.update(r)
                render(r, race, rec)
            for step in range(60):                  # race two, same course
                race.update(racing(step))
            race.end()
            good = len(stored) == 2
        except Exception as exc:
            good = False
            stored = repr(exc)
        ok &= good
        print("  %s a race, an unreadable gap, then another race on the same "
              "course -> %s races stored"
              % ("PASS" if good else "FAIL",
                 len(stored) if isinstance(stored, list) else stored))

    print("\n%s" % ("all checks pass" if ok else "SOMETHING FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
