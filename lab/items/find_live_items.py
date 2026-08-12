#!/usr/bin/env python3
"""Offline: enumerate every item object actually alive, from the game's list.

`docs/MEMORY_MAP.md` reads live items out of `ItemDirector + 0x264`. The
disassembly says that is wrong: `0x80799cac` fills that buffer with the objects
near ONE kart, capped at 16, and the collision loop consumes it. Hence "at most
3 alive at once".

The real list is a pooled manager at `*(0x809C2EF0)`, walked by `0x80785df4`:

    lwz r0,1068(r3)     cursor at mgr+0x42C, 256 = end
    lwz r4,28(r3)       entry table at mgr+0x1C
    lwzx r5,r4,r0       entry = table[cursor]
    lwz r0,12(r4)       entry+0x0C bit 0x2 = in use
    lwz r0,1080(r3)     mgr+0x438 = number of entries
    lwz r3,16(r5)       entry+0x10 = the object

Run (no sudo):
  mk/bin/python3 -m lab.items.find_live_items [recording-substring]
"""

import glob
import os
import sys
from collections import Counter

from mkw.capture.session import Session, RECORDINGS

OBJ_MANAGER = 0x809C2EF0
OFF_ENTRIES = 0x01C          # -> table of entry pointers
OFF_COUNT = 0x438            # number of entries in that table
OFF_ENTRY_FLAGS = 0x0C       # bit 0x2 = this slot is in use
OFF_ENTRY_OBJ = 0x10

OFF_TYPE = 0x04
OFF_OWNER = 0x6C
OFF_STATE = 0x78


def is_heap(a):
    return a is not None and (0x80900000 <= a < 0x81800000
                              or 0x90000000 <= a < 0x91800000)


def live(s, i):
    """[(entry, obj, type, owner, state)] for one frame, or None."""
    mgr = s.u32(i, OBJ_MANAGER)
    if not is_heap(mgr):
        return None
    table = s.u32(i, mgr + OFF_ENTRIES)
    count = s.u32(i, mgr + OFF_COUNT)
    if not is_heap(table) or count is None or not 0 < count < 4096:
        return None
    out = []
    for k in range(count):
        entry = s.u32(i, table + k * 4)
        if not is_heap(entry):
            continue
        flags = s.u32(i, entry + OFF_ENTRY_FLAGS)
        if flags is None or not flags & 2:
            continue
        obj = s.u32(i, entry + OFF_ENTRY_OBJ)
        if not is_heap(obj):
            continue
        out.append((entry, obj, s.u32(i, obj + OFF_TYPE),
                    s.u8(i, obj + OFF_OWNER), s.u32(i, obj + OFF_STATE)))
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs

    for d in dirs:
        s = Session(d)
        peak = 0
        types = Counter()
        owners = Counter()
        entries = set()
        frames = 0
        step = max(1, len(s) // 400)
        for i in range(0, len(s), step):
            if s.index[i]["position"] is None:
                continue
            objs = live(s, i)
            if objs is None:
                continue
            frames += 1
            peak = max(peak, len(objs))
            for entry, obj, typ, owner, state in objs:
                entries.add(entry)
                types[typ] += 1
                owners[owner] += 1
        print("%-46s %3d frames, peak %2d alive, %d pool slots used"
              % (os.path.basename(d)[:46], frames, peak, len(entries)))
        print("      types  %s" % dict(types.most_common()))
        print("      owners %s" % dict(sorted(owners.items())))


if __name__ == "__main__":
    main()
