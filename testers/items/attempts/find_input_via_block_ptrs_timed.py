#!/usr/bin/env python3
"""
Timed input scan via stable block pointer.

No interactive prompts after start. It:
  1) Counts down and captures "idle"
  2) Counts down and captures "pressed"
  3) Counts down and captures "released"
  4) Counts down and captures "pressed again"
  5) Diffs across phases and reports bytes that toggle consistently

Usage:
  sudo python3 find_input_via_block_ptrs_timed.py
"""
import struct
import time
import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Scan sizes / caps (tune if needed)
BLOCK_PTR_SCAN = 0x4000
P1_SNAPSHOT = 0x600
P2_SNAPSHOT = 0x400
MAX_P1 = 1024
MAX_P2_PER_P1 = 256
MAX_HITS = 200

COUNTDOWN_SECONDS = 3
WINDOW_SECONDS = 3
FILTER_SINGLE_BIT = True  # only keep bytes that toggle a single bit (e.g. 0<->1 or 0<->128)
FILTER_ONLY_BOOL = True   # only keep 0<->1 toggles


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


def countdown(n):
    for i in range(n, 0, -1):
        print("  %d..." % i)
        time.sleep(1)


def is_single_bit_toggle(a, b):
    x = a ^ b
    return x != 0 and (x & (x - 1)) == 0


def is_bool_toggle(a, b):
    return (a == 0 and b == 1) or (a == 1 and b == 0)


def main():
    if not dme.is_hooked():
        print("Dolphin not found / not hooked.")
        return

    print("Start a race (no menus).")
    print("We will capture input changes using a timed window.")
    print("Follow the prompts: RELEASE, HOLD, RELEASE, HOLD.")
    input("Press Enter to start... ")

    block = read_block()
    if block is None:
        print("Not in race.")
        return

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

    def snapshot_phase(phase_block_bytes):
        p1_snap = {}
        p2_snap = {}
        for off1, p1 in p1_list:
            # Ensure p1 pointer stable for this phase
            p1_now = struct.unpack(">I", phase_block_bytes[off1:off1+4])[0]
            if p1_now != p1:
                continue
            try:
                b1 = dump(p1, P1_SNAPSHOT)
                p1_snap[(off1, p1)] = b1
            except Exception:
                continue

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
        return p1_snap, p2_snap

    def capture_phase(label):
        print("\n%s" % label)
        countdown(WINDOW_SECONDS)
        b = read_block()
        if b is None or b != block:
            print("Block changed; restart script.")
            return None
        return dump(block, BLOCK_PTR_SCAN)

    print("\nPhase 1: RELEASE (do not press)")
    idle_block_bytes = capture_phase("Capturing RELEASE...")
    if idle_block_bytes is None:
        return

    print("\nPhase 2: HOLD (press and hold)")
    press1_block_bytes = capture_phase("Capturing HOLD...")
    if press1_block_bytes is None:
        return

    print("\nPhase 3: RELEASE (let go)")
    release_block_bytes = capture_phase("Capturing RELEASE...")
    if release_block_bytes is None:
        return

    print("\nPhase 4: HOLD (press and hold again)")
    press2_block_bytes = capture_phase("Capturing HOLD...")
    if press2_block_bytes is None:
        return

    # Snapshot per phase
    p1_idle, p2_idle = snapshot_phase(idle_block_bytes)
    p1_press1, p2_press1 = snapshot_phase(press1_block_bytes)
    p1_release, p2_release = snapshot_phase(release_block_bytes)
    p1_press2, p2_press2 = snapshot_phase(press2_block_bytes)

    # Diffs with 4-phase consistency:
    # We want bytes where idle==release, press1==press2, and idle != press1
    direct_hits = []
    level2_hits = []

    for key in p1_idle.keys():
        if key not in p1_press1 or key not in p1_release or key not in p1_press2:
            continue
        off1, p1 = key
        b_idle = p1_idle[key]
        b_press1 = p1_press1[key]
        b_release = p1_release[key]
        b_press2 = p1_press2[key]
        n = min(len(b_idle), len(b_press1), len(b_release), len(b_press2))
        for i in range(n):
            if b_idle[i] == b_release[i] and b_press1[i] == b_press2[i] and b_idle[i] != b_press1[i]:
                if FILTER_SINGLE_BIT and not is_single_bit_toggle(b_idle[i], b_press1[i]):
                    continue
                if FILTER_ONLY_BOOL and not is_bool_toggle(b_idle[i], b_press1[i]):
                    continue
                direct_hits.append((off1, p1, i, b_idle[i], b_press1[i]))
                if len(direct_hits) >= MAX_HITS:
                    break
        if len(direct_hits) >= MAX_HITS:
            break

    for key in p2_idle.keys():
        if key not in p2_press1 or key not in p2_release or key not in p2_press2:
            continue
        off1, p1, off2, p2 = key
        b_idle = p2_idle[key]
        b_press1 = p2_press1[key]
        b_release = p2_release[key]
        b_press2 = p2_press2[key]
        n = min(len(b_idle), len(b_press1), len(b_release), len(b_press2))
        for i in range(n):
            if b_idle[i] == b_release[i] and b_press1[i] == b_press2[i] and b_idle[i] != b_press1[i]:
                if FILTER_SINGLE_BIT and not is_single_bit_toggle(b_idle[i], b_press1[i]):
                    continue
                if FILTER_ONLY_BOOL and not is_bool_toggle(b_idle[i], b_press1[i]):
                    continue
                level2_hits.append((off1, p1, off2, p2, i, b_idle[i], b_press1[i]))
                if len(level2_hits) >= MAX_HITS:
                    break
        if len(level2_hits) >= MAX_HITS:
            break

    print("\nCONSISTENT TOGGLES across RELEASE/HOLD/RELEASE/HOLD:")
    print("Direct (block->p1):", len(direct_hits))
    for off1, p1, i, b0, b1 in direct_hits[:50]:
        print("  block+%s -> %s ; byte @ p1+%s : %d -> %d"
              % (hex(off1), hex(p1), hex(i), b0, b1))

    print("\n2-LEVEL (block->p1->p2):", len(level2_hits))
    for off1, p1, off2, p2, i, b0, b1 in level2_hits[:50]:
        print("  block+%s -> %s ; p1+%s -> %s ; byte @ p2+%s : %d -> %d"
              % (hex(off1), hex(p1), hex(off2), hex(p2), hex(i), b0, b1))

    print("\nTip: rerun and use a different key to confirm the input byte.")


if __name__ == "__main__":
    main()
