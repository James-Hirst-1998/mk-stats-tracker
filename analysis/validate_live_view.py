#!/usr/bin/env python3
"""Offline: draw the live view for every frame of a recording.

Twice now a session has been lost to the screen rather than to the reading -
`read_course` returning None between races, and a clock the view formatted by
hand. The drawing is wrapped so a bug in it cannot take a session down, but a
view that throws every frame shows nothing, which is nearly as bad.

This runs `tools.track.render` over every frame of a recording, including the
frames where the reader returns nothing, and fails if any of them raises or if
the view stops naming the local player. No Dolphin, no live race.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_live_view [recording-substring]
"""

import sys

from mkw import reader
from mkw.capture.session import Session
from mkw.events import Race
from tools.replay_live import install
from tools.track import render
from lab.events.snapshots import recordings


class FakeRecorder:
    """Everything `render` asks a session recorder for, and nothing else."""
    name = "validate"
    dir = "-"

    def __len__(self):
        return 0


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    ok = True
    for d in recordings(which):
        s = Session(d)
        state = {"img": None}
        install(s, state)
        race = Race()
        rec = FakeRecorder()
        drawn = blank = 0
        named = 0
        failed = []
        last = None
        for i, img in s.frames():
            state["img"] = img
            try:
                r = reader.read()
            except Exception:
                r = None
            race.update(r)
            if r is not None:
                last = r
            try:
                out = render(last, race, rec)
                drawn += 1
                if last is None:
                    blank += 1
                elif "<- you" in out:
                    named += 1
            except Exception as exc:
                failed.append("frame %d: %s: %s"
                              % (i, type(exc).__name__, exc))
        race.end()
        name = d.split("/")[-1]
        if failed:
            ok = False
            print("  FAIL %-46s %d of %d frames raised" % (name, len(failed),
                                                           drawn))
            for line in failed[:3]:
                print("       %s" % line)
        else:
            print("  PASS %-46s %d frames drawn, %d of them waiting for a "
                  "race, %d naming you" % (name, drawn, blank, named))
    print("\n%s" % ("all frames drawn" if ok else "the live view can throw"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
