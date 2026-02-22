#!/usr/bin/env python3
"""
See which of your item_finder addresses keeps the correct item across races.

Run this during a race. It prints the current value at each candidate address.
Run again in a different race with a different item. The address that shows
the right value both times is stable — set STABLE_ITEM_ADDRESS in read_race.py.

  sudo python3 pick_stable_item.py

Edit CANDIDATES below with the hex addresses from item_finder (one per line).
"""

import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000

# 0–20 = item ID (20 = empty). Paste your item_finder addresses here.
CANDIDATES = [
    0x81249ab7,
    0x81384253,
    0x9049634a,
    0x9049dc24,
    0x904b6914,
    0x904bd983,
    0x904bfd9f,
    0x904ce204
]

NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Box", 4: "Mushroom",
    5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell", 8: "Lightning", 9: "Star",
    10: "Golden Mushroom", 11: "Mega Mushroom", 12: "Blooper", 13: "POW", 14: "Thunder Cloud",
    15: "Bullet Bill", 16: "Triple Green", 17: "Triple Red", 18: "Triple Banana",
    19: "(unused)", 20: "empty",
}

def main():
    print("Current value at each candidate (0–20 = item ID):")
    print()
    for addr in CANDIDATES:
        try:
            off = addr - BASE
            b = dme.read_bytes(off, 1)[0]
            name = NAMES.get(b, "?%d" % b)
            print("  %s  ->  %s (%s)" % (hex(addr), b, name))
        except Exception as e:
            print("  %s  ->  (read failed: %s)" % (hex(addr), e))
    print()
    print("Run in another race with a different item. The address that matches both times:")
    print("  Set in read_race.py: STABLE_ITEM_ADDRESS = 0x???????")

if __name__ == "__main__":
    main()
