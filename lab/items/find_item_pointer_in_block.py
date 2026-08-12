#!/usr/bin/env python3
"""
Find a 2-level pointer chain from STABLE_PTR->block to the item byte.

We search:
  block + OFF1  -> p1
  p1   + OFF2   -> p2
  p2   + ITEMOFF -> item byte

Usage:
  sudo python3 find_item_chain.py 0x8124bf37 0x8136b28f

Edit only if needed:
  OFF1_SCAN, OFF2_SCAN, MAX_ITEMOFF
"""

import struct
import sys
import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809C27F8

OFF1_SCAN = 0x4000   # scan this many bytes from block for pointers (4-byte steps)
OFF2_SCAN = 0x4000   # scan this many bytes from p1   for pointers
MAX_ITEMOFF = 0x4000 # max distance from p2 to item byte

def u8(addr: int) -> int:
    return dme.read_bytes(addr - BASE, 1)[0]

def u32(addr: int) -> int:
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]

def in_mem1(p: int) -> bool:
    return 0x80000000 <= p < 0x81800000

def main():
    if len(sys.argv) < 2:
        print("usage: sudo python3 find_item_chain.py <item_addr1> [item_addr2 ...]")
        sys.exit(1)

    item_addrs = [int(x, 0) for x in sys.argv[1:]]
    for a in item_addrs:
        if not in_mem1(a):
            print("bad item addr:", hex(a))
            sys.exit(1)

    block = u32(STABLE_PTR)
    if not in_mem1(block):
        print("block invalid:", hex(block))
        sys.exit(1)

    item_vals = {a: u8(a) for a in item_addrs}
    print("block=", hex(block))
    for a in item_addrs:
        print("item_addr=", hex(a), "item_val=", item_vals[a])

    hits = []

    # level 1: pointers in block
    for off1 in range(0, OFF1_SCAN, 4):
        try:
            p1 = u32(block + off1)
        except Exception:
            continue
        if not in_mem1(p1):
            continue

        # level 2: pointers in p1
        for off2 in range(0, OFF2_SCAN, 4):
            try:
                p2 = u32(p1 + off2)
            except Exception:
                continue
            if not in_mem1(p2):
                continue

            # does p2 "own" all item addresses at some offset?
            item_offs = []
            ok = True
            for a in item_addrs:
                itemoff = a - p2
                if itemoff < 0 or itemoff >= MAX_ITEMOFF:
                    ok = False
                    break
                try:
                    if u8(p2 + itemoff) != item_vals[a]:
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
                item_offs.append(itemoff)

            if ok:
                hits.append((off1, p1, off2, p2, tuple(item_offs)))

    if not hits:
        print("\nNO HITS (2-level).")
        print("Try increasing OFF1_SCAN/OFF2_SCAN/MAX_ITEMOFF, or give more item addresses from same race.")
        return

    print("\nHITS:")
    for off1, p1, off2, p2, item_offs in hits[:50]:
        print(
            "OFF1", hex(off1), "p1", hex(p1),
            "OFF2", hex(off2), "p2", hex(p2),
            "ITEMOFFS", tuple(hex(x) for x in item_offs)
        )

    print("\nIf ITEMOFFS are identical (or one of them is your real item byte), then in read_race.py use:")
    print("  PTR_OFFSET = OFF1")
    print("  ITEM_OFFSET_IN_PTR = (OFF2 + ITEMOFF)  # i.e. deref p1+OFF2 then add ITEMOFF, or extend script to 3-level if needed")

if __name__ == "__main__":
    main()