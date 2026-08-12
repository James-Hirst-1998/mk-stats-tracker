#!/usr/bin/env python3
"""
Find item via stable block pointer by scanning only reachable structs.

We:
  1) Read STABLE_PTR->block (ensure in race)
  2) Enumerate pointers inside the block (p1)
  3) Snapshot p1 bytes, and pointers inside p1 (p2) + their bytes
  4) Ask you to change item, then diff to find old->new transitions

This is a targeted 1-2 level search, not a full brute-force scan.

Usage:
  sudo python3 find_item_via_block_ptrs.py
"""
import struct
import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Scan sizes / caps (tune if needed)
BLOCK_PTR_SCAN = 0x4000        # bytes of block to scan for pointers
P1_SNAPSHOT = 0x600            # bytes to snapshot from p1
P2_SNAPSHOT = 0x400            # bytes to snapshot from p2
MAX_P1 = 1024
MAX_P2_PER_P1 = 256
MAX_HITS = 200

ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box", 4: "Mushroom",
    5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell", 8: "Lightning", 9: "Star",
    10: "Golden Mushroom", 11: "Mega Mushroom", 12: "Blooper", 13: "POW Block", 14: "Thunder Cloud",
    15: "Bullet Bill", 16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "empty",
}


def u8(addr: int) -> int:
    return dme.read_bytes(addr - BASE, 1)[0]

def u32(addr: int) -> int:
    return struct.unpack(">I", bytes(dme.read_bytes(addr - BASE, 4)))[0]

def dump(addr: int, n: int) -> bytes:
    return bytes(dme.read_bytes(addr - BASE, n))

def in_valid_mem(p: int) -> bool:
    return (0x80000000 <= p < 0x81800000) or (0x90000000 <= p < 0x94000000)

def read_block():
    block = u32(STABLE_PTR)
    if not in_valid_mem(block):
        return None
    pos = u8(block + POSITION_OFFSET)
    if not (1 <= pos <= 12):
        return None
    return block


def main():
    if not dme.is_hooked():
        print("Dolphin not found / not hooked.")
        return

    print("Start a race and HOLD an item (do not open menus).")
    input("Press Enter when ready... ")

    block = read_block()
    if block is None:
        print("Not in race.")
        return

    old_val = int(input("Enter current held item ID (0-20, empty=20): ").strip(), 0)

    # Snapshot block pointers
    block_bytes = dump(block, BLOCK_PTR_SCAN)
    p1_list = []
    for off in range(0, BLOCK_PTR_SCAN, 4):
        p1 = struct.unpack(">I", block_bytes[off:off+4])[0]
        if in_valid_mem(p1):
            p1_list.append((off, p1))
            if len(p1_list) >= MAX_P1:
                break

    if not p1_list:
        print("No pointers found in block scan range.")
        return

    # Snapshot p1 bytes and p2 pointers+bytes
    p1_snap = {}  # (off, p1) -> bytes
    p2_snap = {}  # (off1, p1, off2, p2) -> bytes
    for off1, p1 in p1_list:
        try:
            b1 = dump(p1, P1_SNAPSHOT)
            p1_snap[(off1, p1)] = b1
        except Exception:
            continue

        # enumerate p2 pointers inside p1 snapshot
        p2_count = 0
        for off2 in range(0, min(P1_SNAPSHOT, len(b1) - 4), 4):
            p2 = struct.unpack(">I", b1[off2:off2+4])[0]
            if not in_valid_mem(p2):
                continue
            try:
                b2 = dump(p2, P2_SNAPSHOT)
            except Exception:
                continue
            p2_snap[(off1, p1, off2, p2)] = b2
            p2_count += 1
            if p2_count >= MAX_P2_PER_P1:
                break

    print("Snapshot complete. Now CHANGE the item (use it / get a new one / go empty).")
    input("Press Enter when changed... ")

    block2 = read_block()
    if block2 is None:
        print("Not in race.")
        return
    if block2 != block:
        print("Block changed; restart script (race state changed).")
        return

    new_val = int(input("Enter NEW held item ID (0-20, empty=20): ").strip(), 0)
    if new_val == old_val:
        print("Old and new are the same. Do it again with a different item.")
        return

    # Re-read block for pointer stability
    block_bytes2 = dump(block, BLOCK_PTR_SCAN)

    direct_hits = []
    level2_hits = []

    # Direct in p1
    for (off1, p1), b1_before in p1_snap.items():
        # pointer unchanged?
        p1_now = struct.unpack(">I", block_bytes2[off1:off1+4])[0]
        if p1_now != p1:
            continue
        try:
            b1_now = dump(p1, P1_SNAPSHOT)
        except Exception:
            continue
        n = min(len(b1_before), len(b1_now))
        for i in range(n):
            if b1_before[i] == old_val and b1_now[i] == new_val:
                direct_hits.append((off1, p1, i))
                if len(direct_hits) >= MAX_HITS:
                    break
        if len(direct_hits) >= MAX_HITS:
            break

    # Two-level: p1 -> p2
    for (off1, p1, off2, p2), b2_before in p2_snap.items():
        # p1 pointer unchanged?
        p1_now = struct.unpack(">I", block_bytes2[off1:off1+4])[0]
        if p1_now != p1:
            continue
        try:
            p2_now = u32(p1 + off2)
        except Exception:
            continue
        if p2_now != p2:
            continue
        try:
            b2_now = dump(p2, P2_SNAPSHOT)
        except Exception:
            continue
        n = min(len(b2_before), len(b2_now))
        for i in range(n):
            if b2_before[i] == old_val and b2_now[i] == new_val:
                level2_hits.append((off1, p1, off2, p2, i))
                if len(level2_hits) >= MAX_HITS:
                    break
        if len(level2_hits) >= MAX_HITS:
            break

    print("\nDIRECT hits (block->p1):", len(direct_hits))
    for off1, p1, item_off in direct_hits[:50]:
        print("  block+%s -> %s ; item @ p1+%s" % (hex(off1), hex(p1), hex(item_off)))

    print("\n2-LEVEL hits (block->p1->p2):", len(level2_hits))
    for off1, p1, off2, p2, item_off in level2_hits[:50]:
        print("  block+%s -> %s ; p1+%s -> %s ; item @ p2+%s"
              % (hex(off1), hex(p1), hex(off2), hex(p2), hex(item_off)))

    # If we have 2-level hits, allow iterative narrowing by further item changes.
    if level2_hits:
        print("\nNow you can NARROW the 2-level hits by changing items again.")
        print("Each time, enter the new item ID; we keep only chains that match.")
        candidates = level2_hits
        while True:
            print("\nChange item again (or just press Enter to stop). Enter new item ID:")
            s = input("> ").strip()
            if not s:
                break
            try:
                new_id = int(s, 0)
            except Exception:
                print("Invalid number.")
                continue

            # Re-read block to ensure we are still in same race
            block3 = read_block()
            if block3 is None or block3 != block:
                print("Block changed; stop and rerun script.")
                return

            next_candidates = []
            for off1, p1, off2, p2, item_off in candidates:
                try:
                    p1_now = u32(block + off1)
                    if p1_now != p1:
                        continue
                    p2_now = u32(p1 + off2)
                    if p2_now != p2:
                        continue
                    b = u8(p2 + item_off)
                    if b == new_id:
                        next_candidates.append((off1, p1, off2, p2, item_off))
                except Exception:
                    pass
            candidates = next_candidates
            print("Remaining:", len(candidates))
            if len(candidates) <= 20:
                for off1, p1, off2, p2, item_off in candidates:
                    print("  block+%s -> %s ; p1+%s -> %s ; item @ p2+%s"
                          % (hex(off1), hex(p1), hex(off2), hex(p2), hex(item_off)))
            if len(candidates) == 0:
                print("No candidates left. Rerun with a more distinctive change.")
                break

    print("\nTip: best results with a distinctive change (e.g. 8->20 or 15->20).")


if __name__ == "__main__":
    main()
