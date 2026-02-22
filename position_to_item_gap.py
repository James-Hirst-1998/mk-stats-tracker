#!/usr/bin/env python3
"""
Print where we read position from (block and block+0x3e), then the gap from
**block** to each item address. Run in the same race you ran item_finder.py.

The gap is from the BLOCK (the address the stable pointer points to), not from
the position byte. If the offset were the same every race, you could use
block+offset in read_race.py — but often block and item are separate allocations,
so the offset changes each race.

  sudo python3 position_to_item_gap.py
"""
import dolphin_memory_engine as dme
import struct

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809c27f8
POSITION_OFFSET = 0x3e

# From item_finder.py output (same race).
ITEM_ADDRESSES = [
    0x81249ab7,
    0x81384253,
]


def u8(addr):
    return dme.read_bytes(addr - BASE, 1)[0]

def u32(addr):
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]

def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def main():
    block = u32(STABLE_PTR)
    if not in_mem1(block):
        print("Not in race. Start a race and run again.")
        return
    position = u8(block + POSITION_OFFSET)
    if position < 1 or position > 12:
        print("Not in race. Start a race and run again.")
        return

    position_addr = block + POSITION_OFFSET
    print("Position source:")
    print("  block          = %s  (what the stable pointer points to)" % hex(block))
    print("  position byte  = block + 0x%x = %s" % (POSITION_OFFSET, hex(position_addr)))
    print("  position value = %d" % position)
    print()
    print("Gap from BLOCK to each item address (use these in read_race.py ITEM_OFFSETS_FROM_BLOCK):")
    for item_addr in ITEM_ADDRESSES:
        off_from_block = item_addr - block
        inside = " (inside block)" if 0 <= off_from_block < 0x10000 else ""
        print("  %s  ->  block + 0x%x (%d)%s" % (hex(item_addr), off_from_block & 0xFFFFFFFF, off_from_block, inside))
    print()
    print("Copy the hex offsets into read_race.py ITEM_OFFSETS_FROM_BLOCK. If item stops working next race, re-run item_finder and this script to get new offsets.")


if __name__ == "__main__":
    main()
