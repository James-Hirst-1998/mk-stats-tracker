#!/usr/bin/env python3
"""
Find item via "neighbour pointers": static addrs near 0x809c27f8 point to per-race
data; one may point to a struct containing the item byte. We narrow by changing
your item (like item_finder) so we only keep locations that update with your item.

Run in a race. Enter current item ID, then change item and enter new ID; repeat until
one (or a few) candidates remain. Those are (pointer_addr, offset) to use in read_race.

  sudo python3 find_item_via_neighbours.py
"""
import dolphin_memory_engine as dme
import struct
import sys

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809c27f8

# Static region: a few words before and after the position pointer.
NEIGHBOUR_START = 0x809c27e0
NEIGHBOUR_END   = 0x809c2870
SCAN_SIZE       = 0x200   # bytes to scan at each pointed-to region

ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box", 4: "Mushroom",
    5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell", 8: "Lightning", 9: "Star",
    10: "Golden Mushroom", 11: "Mega Mushroom", 12: "Blooper", 13: "POW Block", 14: "Thunder Cloud",
    15: "Bullet Bill", 16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "empty",
}


def u32(addr):
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]

def u8(addr):
    return dme.read_bytes(addr - BASE, 1)[0]


def valid_ptr(p):
    return (0x80000000 <= p < 0x81800000) or (0x90000000 <= p <= 0x91800000)


def get_candidates_for_value(byte_value):
    """All (ptr_addr, offset) where the byte at u32(ptr_addr)+offset == byte_value."""
    out = []
    addr = NEIGHBOUR_START
    while addr < NEIGHBOUR_END:
        try:
            p = u32(addr)
            if not valid_ptr(p):
                addr += 4
                continue
            try:
                chunk = dme.read_bytes(p - BASE, SCAN_SIZE)
                for i, b in enumerate(chunk):
                    if b == byte_value:
                        out.append((addr, i))
            except Exception:
                pass
        except Exception:
            pass
        addr += 4
    return out


def main():
    print("Hold your current item. Enter its ID (0-20, empty=20):")
    current_item = int(input("> "), 0)
    name = ITEM_NAMES.get(current_item, "?%d" % current_item)
    print("Searching for %d (%s) in neighbour pointers..." % (current_item, name))

    candidates = get_candidates_for_value(current_item)
    if not candidates:
        print("No candidates. Tried static addrs %s..%s." % (hex(NEIGHBOUR_START), hex(NEIGHBOUR_END)))
        return
    print("Initial candidates: %d" % len(candidates))
    print()

    while True:
        print("Change your item (use it, get new one, or go empty). Enter new item ID (empty=20):")
        new_val = int(input("> "), 0)
        new_name = ITEM_NAMES.get(new_val, "?%d" % new_val)

        next_candidates = []
        for ptr_addr, offset in candidates:
            try:
                p = u32(ptr_addr)
                b = u8(p + offset)
                if b == new_val:
                    next_candidates.append((ptr_addr, offset))
            except Exception:
                pass
        candidates = next_candidates
        print("Remaining: %d  (byte at each candidate now == %d (%s))" % (len(candidates), new_val, new_name))
        print()

        if len(candidates) <= 0:
            print("None matched. The pointers may have changed or the value isn't in this region.")
            return
        if len(candidates) <= 15:
            print("Likely item (pointer_addr, offset) — use in read_race.py:")
            for ptr_addr, offset in sorted(candidates):
                try:
                    p = u32(ptr_addr)
                    b = u8(p + offset)
                    print("  %s  + 0x%x  ->  %d (%s)" % (hex(ptr_addr), offset, b, ITEM_NAMES.get(b, "?")))
                except Exception:
                    print("  %s  + 0x%x" % (hex(ptr_addr), offset))
            print()
            pa, off = candidates[0]
            print("Example for read_race.py: item = u8(u32(%s) + 0x%x)" % (hex(pa), off))
            print("Run again next race to confirm the same pointer+offset still works.")
            break


if __name__ == "__main__":
    main()
