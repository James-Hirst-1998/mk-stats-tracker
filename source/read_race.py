#!/usr/bin/env python3
"""
Read live race data from Mario Kart Wii (Dolphin).
Position: stable pointer 0x809c27f8 -> block, position at block+0x3e (PAL).

  sudo python3 read_race.py
"""

import dolphin_memory_engine as dme
import struct
import sys

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809c27f8
POSITION_OFFSET = 0x3e
# Item: block+offset only works in the same race you measured; next race it usually fails.
# For a stable item path, run find_item_via_neighbours.py (or see STATUS.md for other ideas).
ITEM_OFFSETS_FROM_BLOCK = [0x136277, 0x29e123]  # optional; often wrong after one race

ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box", 4: "Mushroom",
    5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell", 8: "Lightning", 9: "Star",
    10: "Golden Mushroom", 11: "Mega Mushroom", 12: "Blooper", 13: "POW Block", 14: "Thunder Cloud",
    15: "Bullet Bill", 16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "empty",
}


def u8(addr):
    return dme.read_bytes(addr - BASE, 1)[0]

def u32(addr):
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]

def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def read():
    block = u32(STABLE_PTR)
    if not in_mem1(block):
        return None
    position = u8(block + POSITION_OFFSET)
    if position < 1 or position > 12:
        return None
    item = None
    for off in ITEM_OFFSETS_FROM_BLOCK:
        try:
            b = u8(block + off)
            if 0 <= b <= 20:
                item = b
                break
        except Exception:
            pass
    return {"position": position, "block": block, "item": item}


def main():
    r = read()
    if r is None:
        print("in_race=False")
        return
    item = r.get("item")
    if item is not None:
        item_str = "%d (%s)" % (item, ITEM_NAMES.get(item, "?"))
    else:
        item_str = "?"
    print("position=%d  in_race=True  item=%s" % (r["position"], item_str))


if __name__ == "__main__":
    main()
