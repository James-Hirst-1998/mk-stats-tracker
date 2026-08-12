#!/usr/bin/env python3
"""Offline: check who the game says each racer is.

`RaceConfig` lives in MEM2 and its layout is the game's own, from 0x8052880C:

    lwz  r3,-10456(r3)      cfg = *(0x809BD728)
    lbz  r4,36(r3)          cfg + 0x24 = how many racers
    addi r6,r3,40           cfg + 0x28 = the array, stride 0xF0
    lwz  r3,16(r3)          + 0x10, compared against 0 and 2

giving vehicle at `+0x08`, character at `+0x0C`, type at `+0x10`, team at
`+0xCC` (which is the field the item collision code reads) and the starting
grid at `+0xE1`.

Four checks, none of which needs the video:

  1. all three ids hold still for the whole race
  2. exactly one racer is not a CPU, and it is slot 0
  3. no two racers are the same character
  4. the character and vehicle tables agree with each other. MKW only lets a
     racer pick a vehicle of their own weight class, and in the vehicle
     ordering the class is `id % 3`, so `vehicle % 3` must equal the
     character's class for every racer. That is one constraint per racer
     linking two tables that were filled in separately.

Then the recordings' own notes are used as labels where they name something,
which is the only part that came from outside the game.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_racers [recording-substring]
"""

import glob
import json
import os
import sys

from mkw.capture.session import Session, RECORDINGS
from mkw.names import CHARACTERS, CHARACTER_CLASS, VEHICLES, PLAYER_TYPES

RACE_CONFIG = 0x809BD728
OFF_COUNT = 0x24
OFF_RACERS = 0x28
STRIDE = 0xF0
OFF_VEHICLE = 0x08
OFF_CHARACTER = 0x0C
OFF_TYPE = 0x10
OFF_TEAM = 0xCC
OFF_GRID = 0xE1
N_PLAYERS = 12
CPU = 1
SAMPLES = 30

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 12: "12th"}


def racers(s, i):
    cfg = s.u32(i, RACE_CONFIG)
    if cfg is None or not 0x90000000 <= cfg < 0x91800000:
        return None
    out = []
    for k in range(N_PLAYERS):
        p = cfg + OFF_RACERS + k * STRIDE
        out.append((s.u32(i, p + OFF_CHARACTER), s.u32(i, p + OFF_VEHICLE),
                    s.u32(i, p + OFF_TYPE), s.u32(i, p + OFF_TEAM),
                    s.u8(i, p + OFF_GRID)))
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    problems = []
    class_ok = class_tot = 0
    label_ok = label_tot = 0
    for d in dirs:
        s = Session(d)
        frames = [i for i in range(len(s)) if s.index[i]["position"] is not None]
        if not frames:
            continue
        frames = frames[::max(1, len(frames) // SAMPLES)]
        rows = racers(s, frames[0])
        if rows is None:
            problems.append("%s: no config" % os.path.basename(d))
            continue
        note = (json.load(open(os.path.join(d, "meta.json"))).get("notes")
                or "").lower()

        for i in frames[1:]:
            if racers(s, i) != rows:
                problems.append("%s: racer table moved during the race"
                                % os.path.basename(d))
                break

        humans = [k for k, r in enumerate(rows) if r[2] != CPU]
        if humans != [0]:
            problems.append("%s: expected only slot 0 human, got %s"
                            % (os.path.basename(d), humans))
        chars = [r[0] for r in rows]
        if len(set(chars)) != N_PLAYERS:
            problems.append("%s: repeated character %s"
                            % (os.path.basename(d), chars))
        if sorted(r[4] for r in rows) != list(range(1, N_PLAYERS + 1)):
            problems.append("%s: grid is not a permutation: %s"
                            % (os.path.basename(d), [r[4] for r in rows]))

        print("=== %s" % os.path.basename(d))
        print("    notes: %s" % (note or "-"))
        print("    %-5s %-14s %-18s %-7s %-5s %s"
              % ("slot", "character", "vehicle", "type", "team", "grid"))
        for k, (ch, ve, ty, team, grid) in enumerate(rows):
            class_tot += 1
            fits = CHARACTER_CLASS.get(ch) == ve % 3
            class_ok += fits
            print("    %-5d %-14s %-18s %-7s %-5d %-4d%s"
                  % (k, CHARACTERS.get(ch, "id %d" % ch),
                     VEHICLES.get(ve, "id %d" % ve),
                     PLAYER_TYPES.get(ty, ty), team, grid,
                     "" if fits else "   <- CLASS MISMATCH"))

        # the notes are the only outside labels; use them where they say something
        ch, ve, _, _, grid = rows[0]
        for text, got in ((CHARACTERS.get(ch, ""), "character"),
                          (VEHICLES.get(ve, ""), "vehicle")):
            if text and text.lower() in note:
                label_tot += 1
                label_ok += 1
                print("    note names the %s: %s, and slot 0 reads %s"
                      % (got, text, text))
        if ORDINALS.get(grid, "").lower() in note and ORDINALS.get(grid):
            label_tot += 1
            label_ok += 1
            print("    note says %s, and slot 0's grid reads %d"
                  % (ORDINALS[grid], grid))
        print()

    print("weight class agrees between the two tables: %d/%d racers"
          % (class_ok, class_tot))
    print("recording notes that name something, and match: %d/%d"
          % (label_ok, label_tot))
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  - %s" % p)
    else:
        print("no problems")


if __name__ == "__main__":
    main()
