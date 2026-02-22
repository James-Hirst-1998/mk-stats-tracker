#!/usr/bin/env python3
"""Find all pointers in MEM1 that point to the given addresses. Usage: python3 find_pointers_to.py < addrs.txt"""

import dolphin_memory_engine as dme
import struct
import sys

dme.hook()
BASE = 0x70000000
START = 0x80000000
END = 0x91800000
STEP = 0x4000

# Load target addresses from stdin (hex, one per line)
targets = set()
for line in sys.stdin:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        continue
    try:
        a = int(line, 0)
        targets.add(a)
        targets.add(a & ~3)   # 4-byte aligned
        targets.add(a & ~0xf)  # 16-byte aligned (struct start)
        targets.add(a & ~0x3f) # 64-byte aligned
        targets.add(a & ~0xff) # 256-byte block
    except ValueError:
        pass
if not targets:
    print("No addresses on stdin.")
    exit(1)
targets = sorted(targets)
print("Looking for pointers to %d address(es) (exact + aligned bases)..." % len(targets))

# For each target we need to find ptr such that read_u32(ptr) == target (big-endian)
def u32_at(offset):
    b = dme.read_bytes(offset, 4)
    return struct.unpack(">I", bytes(b))[0]

# Build set of target bytes for fast scan (we'll check 4-byte aligned positions)
hits = []  # (where_pointer_is, points_to)
addr = START
while addr < END:
    off = addr - BASE
    try:
        chunk = dme.read_bytes(off, STEP)
        for i in range(0, len(chunk) - 3, 4):
            val = struct.unpack(">I", bytes(chunk[i:i+4]))[0]
            if val in targets:
                hits.append((addr + i, val))
    except Exception:
        pass
    addr += STEP

print("Found %d pointer(s):" % len(hits))
for ptr_loc, points_to in sorted(hits):
    print("  %s  ->  %s" % (hex(ptr_loc), hex(points_to)))

# If we found several, show if they're in a tight range (array of pointers)
if len(hits) >= 2:
    locs = sorted([h[0] for h in hits])
    print("")
    print("Pointer locations (sorted):")
    for i, loc in enumerate(locs):
        if i > 0:
            diff = loc - locs[i-1]
            print("  %s  (+%d from previous)" % (hex(loc), diff))
        else:
            print("  %s" % hex(loc))
