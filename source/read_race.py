#!/usr/bin/env python3
"""
Read live race data from Mario Kart Wii (Dolphin, PAL).

Trusted reads:
- Position: u8(u32(0x809c27f8) + 0x3e)
- Course code: u8(u32(0x809c27f8) + 0x13)

Note: course code is MKW slot code (for example Mario Circuit=0x00), not
cup-order index 0-31.

Run:
  sudo python3 source/read_race.py
"""

import dolphin_memory_engine as dme
import struct

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809c27f8
POSITION_OFFSET = 0x3e
# Canonical course path from testers/tracks/CONFIRMED_TRACK_PATHS.md.
# If needed, this can be swapped to another confirmed (slot, offset) pair.
COURSE_CODE_OFFSET = 0x13
COURSE_NAMES = {
    0x00: "Mario Circuit",
    0x01: "Moo Moo Meadows",
    0x02: "Mushroom Gorge",
    0x03: "Grumble Volcano",
    0x04: "Toad's Factory",
    0x05: "Coconut Mall",
    0x06: "DK Summit",
    0x07: "Wario's Gold Mine",
    0x08: "Luigi Circuit",
    0x09: "Daisy Circuit",
    0x0A: "Moonview Highway",
    0x0B: "Maple Treeway",
    0x0C: "Bowser's Castle",
    0x0D: "Rainbow Road",
    0x0E: "Dry Dry Ruins",
    0x0F: "Koopa Cape",
    0x10: "GCN Peach Beach",
    0x11: "GCN Mario Circuit",
    0x12: "GCN Waluigi Stadium",
    0x13: "GCN DK Mountain",
    0x14: "DS Yoshi Falls",
    0x15: "DS Desert Hills",
    0x16: "DS Peach Gardens",
    0x17: "DS Delfino Square",
    0x18: "SNES Mario Circuit 3",
    0x19: "SNES Ghost Valley 2",
    0x1A: "N64 Mario Raceway",
    0x1B: "N64 Sherbet Land",
    0x1C: "N64 Bowser's Castle",
    0x1D: "N64 DK's Jungle Parkway",
    0x1E: "GBA Bowser Castle 3",
    0x1F: "GBA Shy Guy Beach",
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
    course_code = u8(block + COURSE_CODE_OFFSET)
    return {"position": position, "block": block, "course_code": course_code}


def main():
    r = read()
    if r is None:
        print("in_race=False")
        return
    code = r["course_code"]
    print(
        "position=%d  in_race=True  course_code=0x%02x (%s)"
        % (r["position"], code, COURSE_NAMES.get(code, "?"))
    )


if __name__ == "__main__":
    main()
