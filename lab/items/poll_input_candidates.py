#!/usr/bin/env python3
"""
Poll candidate input bytes derived from find_input_via_block_ptrs_timed.

Watches:
  u8(u32(block+OFF) + BYTE_OFF)

Update CANDIDATES if you find different offsets.

Usage:
  sudo python3 poll_input_candidates.py
"""
import struct
import time
import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Candidates from your latest run:
CANDIDATES = [
    (0x4A0, 0x12B),  # block+0x4a0 -> p1 ; p1+0x12b
    (0xD30, 0x25D),  # block+0xd30 -> p1 ; p1+0x25d
    (0xD34, 0x25D),  # block+0xd34 -> p1 ; p1+0x25d
]


def u8(addr: int) -> int:
    return dme.read_bytes(addr - BASE, 1)[0]


def u32(addr: int) -> int:
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]


def in_mem(p: int) -> bool:
    return 0x80000000 <= p < 0x81800000 or 0x90000000 <= p < 0x94000000


def read_block():
    block = u32(STABLE_PTR)
    if not in_mem(block):
        return None
    pos = u8(block + POSITION_OFFSET)
    if not (1 <= pos <= 12):
        return None
    return block


def main():
    if not dme.is_hooked():
        print("Dolphin not found / not hooked.")
        return

    block = read_block()
    if block is None:
        print("Not in race.")
        return

    print("Polling input candidates every 0.2s. Click your mouse button (accelerate) to see which toggles.")
    print("Candidates:", ["block+%s +%s" % (hex(a), hex(b)) for a, b in CANDIDATES])
    while True:
        parts = []
        for off, byte_off in CANDIDATES:
            try:
                p1 = u32(block + off)
                if not in_mem(p1):
                    parts.append("block+%s -> ?" % hex(off))
                    continue
                b = u8(p1 + byte_off)
                parts.append("block+%s -> %s : %d" % (hex(off), hex(p1), b))
            except Exception:
                parts.append("block+%s -> ?" % hex(off))
        print(" | ".join(parts))
        time.sleep(0.2)


if __name__ == "__main__":
    main()
