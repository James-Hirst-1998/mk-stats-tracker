#!/usr/bin/env python3
"""
Find held-item address by timing the USE event.

Flow:
  1) You enter current item ID (e.g. 15) and expected value after use (usually 20).
  2) Script scans memory for the current item ID to get candidates.
  3) For each round: countdown -> you USE the item -> we keep only addresses
     that change from old->new around the use moment.

Usage:
  sudo python3 item_use_finder.py
"""
import time
import dolphin_memory_engine as dme

dme.hook()

BASE = 0x80000000
START = 0x80000000
END = 0x91800000
STEP = 0x4000

COUNTDOWN = 3
POST_DELAY = 0.3  # seconds after "GO" to sample
MAX_CANDIDATES = 200000


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
            if len(matches) >= MAX_CANDIDATES:
                return matches
        except Exception:
            pass
        addr += STEP
    return matches


def countdown(n):
    for i in range(n, 0, -1):
        print("%d..." % i)
        time.sleep(1)


def sample_values(addrs):
    out = {}
    for a in addrs:
        try:
            out[a] = dme.read_bytes(a - BASE, 1)[0]
        except Exception:
            pass
    return out


def main():
    if not dme.is_hooked():
        print("Dolphin not found / not hooked.")
        return

    print("Hold an item.")
    old_val = int(input("Enter current held item ID (0-20, empty=20): ").strip(), 0)
    new_val = int(input("Enter expected value AFTER use (usually 20): ").strip(), 0)
    rounds = int(input("How many use rounds? (minimum 2, default 2): ").strip() or "2")
    if rounds < 2:
        rounds = 2

    print("Scanning memory for current item ID...")
    candidates = full_scan(old_val)
    print("Initial candidates:", len(candidates))
    if not candidates:
        print("No candidates found.")
        return

    for r in range(rounds):
        print("\nRound %d/%d" % (r + 1, rounds))
        print("Get ready to USE the item on GO.")
        countdown(COUNTDOWN)
        print("GO! USE NOW!")

        before = sample_values(candidates)
        time.sleep(POST_DELAY)
        after = sample_values(candidates)

        next_candidates = set()
        for a in candidates:
            b0 = before.get(a)
            b1 = after.get(a)
            if b0 == old_val and b1 == new_val:
                next_candidates.add(a)

        candidates = next_candidates
        print("Remaining:", len(candidates))
        if not candidates:
            print("No candidates left. Try fewer rounds or a different item.")
            return

        # Update old_val for subsequent rounds if the value should now be new_val
        old_val = new_val

    print("\nLikely item addresses:")
    for a in sorted(candidates)[:50]:
        print("  %s" % hex(a))
    if len(candidates) > 50:
        print("  ... (truncated)")
    print("Use these as per-race item addresses.")


if __name__ == "__main__":
    main()
