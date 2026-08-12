#!/usr/bin/env python3
"""Offline: dump the pooled object manager at *(0x809C2EF0) on one frame.

Enumerating it the way the game's iterator does gives at most 3 live objects,
which is the same suspiciously low number the old `ItemDirector + 0x264` read
gave. Either the flag test is wrong, the count is wrong, or a race really does
hold that few item objects. This prints the raw slots so the answer is visible
rather than inferred.

Run (no sudo):
  mk/bin/python3 -m lab.items.dump_obj_manager <recording-substring> [frame]
"""

import glob
import os
import sys

from mkw.capture.session import Session, RECORDINGS
from lab.items.find_live_items import (OBJ_MANAGER, OFF_ENTRIES, OFF_COUNT,
                                       OFF_ENTRY_FLAGS, OFF_ENTRY_OBJ,
                                       OFF_TYPE, OFF_OWNER, OFF_STATE, is_heap)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    dirs = [d for d in dirs if which in d] if which else dirs
    s = Session(dirs[0])
    i = int(sys.argv[2]) if len(sys.argv) > 2 else len(s) // 2
    print("%s  frame %d\n" % (os.path.basename(dirs[0]), i))

    mgr = s.u32(i, OBJ_MANAGER)
    print("manager   0x%08x" % mgr)
    for off in (0x1C, 0x20, 0x24, 0x28, 0x42C, 0x430, 0x434, 0x438, 0x43C):
        print("   +0x%03x  0x%08x" % (off, s.u32(i, mgr + off)))

    table = s.u32(i, mgr + OFF_ENTRIES)
    count = s.u32(i, mgr + OFF_COUNT)
    print("\n%d entries at 0x%08x" % (count, table))
    print("  %-4s %-10s %-10s %-10s %-6s %-6s %s"
          % ("slot", "entry", "flags", "object", "type", "owner", "state"))
    for k in range(min(count, 128)):
        entry = s.u32(i, table + k * 4)
        if not is_heap(entry):
            print("  %-4d %-10s" % (k, "0x%08x" % (entry or 0)))
            continue
        flags = s.u32(i, entry + OFF_ENTRY_FLAGS)
        obj = s.u32(i, entry + OFF_ENTRY_OBJ)
        row = "  %-4d 0x%08x 0x%08x 0x%08x" % (k, entry, flags, obj or 0)
        if is_heap(obj):
            row += " %-6s %-6s 0x%08x" % (s.u32(i, obj + OFF_TYPE),
                                          s.u8(i, obj + OFF_OWNER),
                                          s.u32(i, obj + OFF_STATE))
        print(row)


if __name__ == "__main__":
    main()
