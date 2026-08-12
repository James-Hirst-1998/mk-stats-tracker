#!/usr/bin/env python3
"""
One script: (1) find item addresses by scanning/narrowing, (2) find pointers in MEM1 to given addresses.

  sudo python3 discover.py find-item   # interactive: scan for item ID, narrow by changing item
  sudo python3 discover.py find-ptrs   # scan MEM1 for 4-byte values that equal TARGETS
"""
import dolphin_memory_engine as dme
import struct
import sys

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809c27f8

# For find-ptrs: addresses to search for (e.g. from find-item).
TARGETS = [0x81249ab7, 0x81384253]

PTR_SCAN_START = 0x80000000
PTR_SCAN_END   = 0x81800000
PTR_STEP       = 0x1000

ITEM_SCAN_START = 0x80000000
ITEM_SCAN_END   = 0x91800000
ITEM_STEP       = 0x4000


def find_pointers():
    targets = set(TARGETS)
    for a in list(targets):
        targets.add(a & ~3)
        targets.add(a & ~0xf)
        targets.add(a & ~0x3f)
        targets.add(a & ~0xff)
    targets = sorted(targets)
    print("Targets (exact + aligned):", [hex(t) for t in targets])
    print("Scanning MEM1 %s to %s ..." % (hex(PTR_SCAN_START), hex(PTR_SCAN_END)))
    try:
        block_ptr = struct.unpack(">I", bytes(dme.read_bytes(STABLE_PTR - BASE, 4)))[0]
        if 0x80000000 <= block_ptr <= 0x81800000:
            print("Sanity: %s -> %s (position block)" % (hex(STABLE_PTR), hex(block_ptr)))
    except Exception:
        block_ptr = None
    hits = []
    sanity_found = None
    addr = PTR_SCAN_START
    while addr < PTR_SCAN_END:
        off = addr - BASE
        try:
            chunk = dme.read_bytes(off, PTR_STEP)
            for i in range(0, len(chunk) - 3, 4):
                val = struct.unpack(">I", bytes(chunk[i:i+4]))[0]
                if val in targets:
                    hits.append((addr + i, val))
                if block_ptr is not None and val == block_ptr:
                    sanity_found = addr + i
        except Exception:
            pass
        addr += PTR_STEP
    if sanity_found is not None:
        print("Sanity OK: position block pointer at %s" % hex(sanity_found))
    elif block_ptr is not None:
        print("Sanity: scan did not find %s" % hex(STABLE_PTR))
    print("Found %d pointer(s) to TARGETS:" % len(hits))
    for loc, val in sorted(hits):
        print("  %s  ->  %s" % (hex(loc), hex(val)))
    if not hits:
        print("(No pointer in MEM1 to these addresses.)")


def find_item():
    print("Hold an item. Enter current item ID (0-20, empty=20):")
    current = int(input("> "), 0)
    candidates = set()
    addr = ITEM_SCAN_START
    while addr < ITEM_SCAN_END:
        off = addr - BASE
        if off < 0:
            addr += ITEM_STEP
            continue
        try:
            chunk = dme.read_bytes(off, ITEM_STEP)
            for i, b in enumerate(chunk):
                if b == current:
                    candidates.add(addr + i)
        except Exception:
            pass
        addr += ITEM_STEP
    print("Initial candidates:", len(candidates))
    while True:
        print("\nChange item. Enter new item ID (empty=20):")
        new_val = int(input("> "), 0)
        next_set = set()
        for a in candidates:
            try:
                if dme.read_bytes(a - BASE, 1)[0] == new_val:
                    next_set.add(a)
            except Exception:
                pass
        candidates = next_set
        print("Remaining:", len(candidates))
        if len(candidates) <= 20:
            print("Addresses:")
            for c in sorted(candidates):
                print("  ", hex(c))
            print("\nPaste into TARGETS in this script or into position_to_item_gap.py ITEM_ADDRESSES.")
            break


def main():
    if len(sys.argv) < 2:
        print("Usage: sudo python3 discover.py find-item | find-ptrs")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "find-item":
        find_item()
    elif cmd == "find-ptrs":
        find_pointers()
    else:
        print("Unknown: %s" % sys.argv[1])
        sys.exit(1)


if __name__ == "__main__":
    main()
