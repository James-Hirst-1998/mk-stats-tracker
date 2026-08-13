#!/usr/bin/env python3
"""Replay a recording through the real reader and hand back the snapshots.

Every question about what an event should mean - how long a boost lasts, who
was where when a shell went off - is answered from the same `reader.read()`
dicts the live tool sees, so an answer found here holds live. Exploratory
only; anything that becomes evidence moves to `analysis/`.
"""

import glob
import os

from mkw import reader
from mkw.capture.session import Session, RECORDINGS
from tools.replay_live import install


def recordings(which=""):
    return [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json")) and which in d]


def snapshots(path):
    """(name, [snapshot or None, ...]) for one recording, in frame order."""
    s = Session(path)
    state = {"img": None}
    install(s, state)
    out = []
    for i, img in s.frames():
        state["img"] = img
        try:
            out.append(reader.read())
        except Exception:
            out.append(None)
    return os.path.basename(path), out


def racing(path):
    """Just the frames where a race is running, with the race clock."""
    name, snaps = snapshots(path)
    return name, [(r["race_time"], r) for r in snaps
                  if r is not None and r.get("race_time")]
