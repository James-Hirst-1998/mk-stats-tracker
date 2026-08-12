#!/usr/bin/env python3
"""
Find the address of your current held item: scan for the item ID byte,
then narrow when the item changes (use item, get new item, or empty = 20).

Item IDs (Tockdom). Enter decimal or hex:
  0 Green Shell    1 Red Shell    2 Banana    3 Fake Item Box    4 Mushroom
  5 Triple Mushroom  6 Bob-omb  7 Spiny Shell  8 Lightning  9 Star
  10 Golden Mushroom  11 Mega Mushroom  12 Blooper  13 POW Block  14 Thunder Cloud
  15 Bullet Bill  16 Triple Green  17 Triple Red  18 Triple Bananas  19 (unused)  20 empty

Run: sudo python3 item_finder.py
"""

import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
START = 0x80000000
END = 0x91800000
STEP = 0x4000

ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box", 4: "Mushroom",
    5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell", 8: "Lightning", 9: "Star",
    10: "Golden Mushroom", 11: "Mega Mushroom", 12: "Blooper", 13: "POW Block", 14: "Thunder Cloud",
    15: "Bullet Bill", 16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "empty",
}


def full_scan(byte_value):
    matches = set()
    addr = START
    while addr < END:
        off = addr - BASE
        if off < 0:
            addr += STEP
            continue
        try:
            chunk = dme.read_bytes(off, STEP)
            for i, b in enumerate(chunk):
                if b == byte_value:
                    matches.add(addr + i)
        except Exception:
            pass
        addr += STEP
    return matches


print("Hold an item. Enter current item ID (0-20, empty=20):")
current = int(input("> "), 0)

candidates = full_scan(current)
print("Initial candidates:", len(candidates))

while True:
    print("\nChange item (use it, get new one, or go empty). Enter new item ID (empty=20):")
    new_val = int(input("> "), 0)

    new_candidates = set()
    for addr in candidates:
        try:
            if dme.read_bytes(addr - BASE, 1)[0] == new_val:
                new_candidates.add(addr)
        except Exception:
            pass
    candidates = new_candidates
    print("Remaining:", len(candidates))

    if len(candidates) <= 10:
        print("Likely item addresses:")
        for c in sorted(candidates):
            try:
                v = dme.read_bytes(c - BASE, 1)[0]
                name = ITEM_NAMES.get(v, "?%d" % v)
                print("  %s  ->  %d (%s)" % (hex(c), v, name))
            except Exception:
                print(hex(c))
        print("\nPaste these into position_to_item_gap.py ITEM_ADDRESSES, run that in same race to get gaps. Put gaps in read_race.py ITEM_OFFSETS_FROM_BLOCK.")
        break
