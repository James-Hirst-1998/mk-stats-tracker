#!/usr/bin/env python3
"""Read a course's KMP - the game's own map of the track.

    python3 -m tools.kmp path/to/course.kmp

A KMP sits inside each `Race/Course/*.szs` on the disc and holds, among other
things, the checkpoints: pairs of points across the road, in order round the
lap, with the start/finish line among them. That is exactly what the replay
wants and cannot get from a drawing - the real shape, in real units, starting
at the real line and running in the real direction.

This only reads a file it is given. Nothing here extracts anything from a
disc: see docs/DASHBOARD.md for the two commands that do that.

Format: a 16-byte header, then per-section offsets, then sections of fixed
size entries. Written down at https://wiki.tockdom.com/wiki/KMP_(File_Format)
and cross-checked against mkw-sp's CourseMap.hh, which has the same structs as
C++. Verified here against three published course files - Coconut Mall, Dry
Dry Ruins and DK Summit - whose checkpoints come out as closed laps of the
right shape.
"""

import math
import os
import struct
import sys

MAGIC = b"RKMD"


class Course:
    """One course.kmp, read back."""

    def __init__(self, data, name=None):
        self.name = name
        if data[:4] != MAGIC:
            raise ValueError("not a KMP (magic %r)" % data[:4])
        _, _, sections, head_len, self.version = struct.unpack(">4sIHHI", data[:16])
        offsets = struct.unpack(">%dI" % sections, data[16:16 + sections * 4])
        self.sections = {}
        for off in offsets:
            at = head_len + off
            kind, count, extra = struct.unpack(">4sHH", data[at:at + 8])
            self.sections[kind.decode("ascii")] = (count, extra, data[at + 8:])

    def entries(self, kind, size, fmt):
        got = self.sections.get(kind)
        if not got:
            return []
        count, _, body = got
        return [struct.unpack(fmt, body[i * size:(i + 1) * size])
                for i in range(count)]

    @property
    def checkpoints(self):
        """[(left_x, left_z, right_x, right_z, respawn, type, prev, next)].

        `type` is 0xFF for an ordinary checkpoint; the numbered ones are the
        key checkpoints that stop you skipping half the lap, and 0 is the
        start/finish line itself.
        """
        return self.entries("CKPT", 20, ">ffffBBBB")

    @property
    def enemy_points(self):
        """[(x, y, z, range, setting1, setting2, setting3)] - the CPU line."""
        return self.entries("ENPT", 20, ">ffffHBB")

    @property
    def start(self):
        """(x, y, z, yaw) of the starting grid, from KTPT."""
        got = self.entries("KTPT", 28, ">ffffhh")
        return got[0] if got else None

    def lap(self):
        """The lap as a list of (x, z) points up the middle of the road.

        Checkpoint midpoints, rotated so the start/finish line comes first, so
        that point 0 is where a lap begins and the order is the direction of
        travel. Alternate routes are ignored: a lap is one line, and the
        checkpoints of the main path are the ones that count it.
        """
        pts = [((a + c) / 2.0, (b + d) / 2.0)
               for a, b, c, d, _, _, _, _ in self.checkpoints]
        if not pts:
            return []
        kinds = [k for _, _, _, _, _, k, _, _ in self.checkpoints]
        first = kinds.index(0) if 0 in kinds else 0
        return pts[first:] + pts[:first]


def read(path):
    with open(path, "rb") as f:
        return Course(f.read(), os.path.basename(os.path.dirname(path)) or
                      os.path.basename(path))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    for path in sys.argv[1:]:
        c = read(path)
        lap = c.lap()
        length = sum(math.dist(a, b) for a, b in zip(lap, lap[1:] + lap[:1]))
        keys = sum(1 for e in c.checkpoints if e[5] != 0xFF)
        print("%s  version %d  sections %s"
              % (os.path.basename(path), c.version,
                 ",".join(sorted(c.sections))))
        print("   %d checkpoints (%d key), %d enemy points, lap %.0f units"
              % (len(c.checkpoints), keys, len(c.enemy_points), length))
        if lap:
            xs = [p[0] for p in lap]
            zs = [p[1] for p in lap]
            print("   starts at (%.0f, %.0f), spans x %.0f..%.0f  z %.0f..%.0f"
                  % (lap[0][0], lap[0][1], min(xs), max(xs), min(zs), max(zs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
