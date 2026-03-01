#!/usr/bin/env python3
"""
Track code root finder for Mario Kart Wii (PAL Dolphin).

Single-script, single-run interactive flow (no argparse).
Goal: find stable (slot_addr, offset) such that
  course_code = u8(u32(slot_addr) + offset)

Important: this script uses MKW course *slot IDs* (non-linear), not simple
0-31 cup order. Numeric input 0-31 is treated as cup-order index by default.
"""

from bisect import bisect_left, bisect_right
import time

import dolphin_memory_engine as dme


BASE = 0x80000000

# Memory regions where runtime state is commonly found on Wii.
MEM_RANGES = [
    (0x80000000, 0x81800000),  # MEM1
    (0x90000000, 0x94000000),  # MEM2
]
SCAN_STEP = 0x4000

# Where to scan for stable pointer slots (static/global-ish region in MEM1).
PTR_SLOT_START = 0x80800000
PTR_SLOT_END = 0x80C00000
PTR_SLOT_STEP = 0x4000

# Candidate (slot, off) where off = target_addr - u32(slot).
MAX_OFFSET = 0x240
PRINT_LIMIT = 20
INTERSECT_HINT_THRESHOLD = 300

RACE_STABLE_POLLS = 6
RACE_STABLE_INTERVAL = 0.25
RACE_STABLE_TIMEOUT = 8.0

# Known stable local-player position root used only for race-state gating.
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Cup/menu order index -> (name, MKW course slot code)
TRACKS = [
    ("Luigi Circuit", 0x08),
    ("Moo Moo Meadows", 0x01),
    ("Mushroom Gorge", 0x02),
    ("Toad's Factory", 0x04),
    ("Mario Circuit", 0x00),
    ("Coconut Mall", 0x05),
    ("DK Summit", 0x06),
    ("Wario's Gold Mine", 0x07),
    ("Daisy Circuit", 0x09),
    ("Koopa Cape", 0x0F),
    ("Maple Treeway", 0x0B),
    ("Grumble Volcano", 0x03),
    ("Dry Dry Ruins", 0x0E),
    ("Moonview Highway", 0x0A),
    ("Bowser's Castle", 0x0C),
    ("Rainbow Road", 0x0D),
    ("GCN Peach Beach", 0x10),
    ("DS Yoshi Falls", 0x14),
    ("SNES Ghost Valley 2", 0x19),
    ("N64 Mario Raceway", 0x1A),
    ("N64 Sherbet Land", 0x1B),
    ("GBA Shy Guy Beach", 0x1F),
    ("DS Delfino Square", 0x17),
    ("GCN Waluigi Stadium", 0x12),
    ("DS Desert Hills", 0x15),
    ("GBA Bowser Castle 3", 0x1E),
    ("N64 DK's Jungle Parkway", 0x1D),
    ("GCN Mario Circuit", 0x11),
    ("SNES Mario Circuit 3", 0x18),
    ("DS Peach Gardens", 0x16),
    ("GCN DK Mountain", 0x13),
    ("N64 Bowser's Castle", 0x1C),
]

VALID_CODES = {code for _, code in TRACKS}
CODE_TO_NAME = {}
for name, code in TRACKS:
    if code not in CODE_TO_NAME:
        CODE_TO_NAME[code] = name


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def in_mem2(p):
    return 0x90000000 <= p < 0x94000000


def in_game_mem(p):
    return in_mem1(p) or in_mem2(p)


def in_race():
    try:
        block = read_u32(STABLE_PTR)
        if not in_mem1(block):
            return False
        pos = read_u8(block + POSITION_OFFSET)
        return 1 <= pos <= 12
    except Exception:
        return False


def wait_for_race_stable():
    have = 0
    t0 = time.time()
    while time.time() - t0 < RACE_STABLE_TIMEOUT:
        if in_race():
            have += 1
            if have >= RACE_STABLE_POLLS:
                return True
        else:
            have = 0
        time.sleep(RACE_STABLE_INTERVAL)
    return False


def normalize_name(name):
    return "".join(ch.lower() for ch in name if ch.isalnum())


def code_name(code):
    if code in CODE_TO_NAME:
        return CODE_TO_NAME[code]
    return "?"


def print_track_table():
    print("Track table (menu index -> course code):")
    for idx, (name, code) in enumerate(TRACKS):
        print("  %2d -> 0x%02x (%2d)  %s" % (idx, code, code, name))
    print("Input rules:")
    print("  - plain number 0-31 => menu index")
    print("  - name => track name")
    print("  - c:<num> or code:<num> => explicit course code (hex or dec)")


def parse_track_input(raw):
    s = raw.strip()
    if not s:
        raise ValueError("empty input")

    lower = s.lower()
    if lower.startswith("c:") or lower.startswith("code:"):
        tail = s.split(":", 1)[1].strip()
        v = int(tail, 0)
        if v not in VALID_CODES:
            raise ValueError("course code not in vanilla race-code set")
        return v, code_name(v), "course_code"

    # Plain numeric: interpret as menu index (0-31) by design.
    try:
        v = int(s, 0)
        if 0 <= v < len(TRACKS):
            name, code = TRACKS[v]
            return code, name, "menu_index"
        raise ValueError("menu index must be 0-31")
    except ValueError:
        pass

    needle = normalize_name(s)
    exact = []
    partial = []
    for idx, (name, code) in enumerate(TRACKS):
        n = normalize_name(name)
        if n == needle:
            exact.append((idx, name, code))
        elif needle in n:
            partial.append((idx, name, code))

    if len(exact) == 1:
        idx, name, code = exact[0]
        return code, name, "name"
    if len(partial) == 1:
        idx, name, code = partial[0]
        return code, name, "name"
    if len(exact) + len(partial) > 1:
        opts = exact + partial
        msg = ", ".join("%d:%s" % (i, n) for i, n, _ in opts[:8])
        raise ValueError("ambiguous name; be more specific (%s)" % msg)

    raise ValueError("unknown track input")


def ask_track(prompt):
    while True:
        raw = input(prompt)
        try:
            code, name, source = parse_track_input(raw)
            print(
                "Using %s (%s) -> course_code=0x%02x (%d)"
                % (name, source, code, code)
            )
            return code, name
        except Exception as exc:
            print("Invalid input:", exc)


def scan_addresses_for_byte(value):
    hits = set()
    t0 = time.time()

    for start, end in MEM_RANGES:
        addr = start
        while addr < end:
            size = SCAN_STEP if (addr + SCAN_STEP) <= end else (end - addr)
            if size <= 0:
                addr += SCAN_STEP
                continue
            try:
                chunk = read_bytes(addr, size)
            except Exception:
                addr += SCAN_STEP
                continue

            for i, b in enumerate(chunk):
                if b == value:
                    hits.add(addr + i)
            addr += SCAN_STEP

    return hits, time.time() - t0


def sample_stable_addresses_for_code(code):
    a1, t1 = scan_addresses_for_byte(code)
    time.sleep(0.12)
    a2, t2 = scan_addresses_for_byte(code)
    stable = a1 & a2
    return stable, (t1 + t2)


def find_slot_offset_candidates(target_addresses):
    """
    Find (slot, off) where u32(slot)=p and (p+off) is one of target_addresses.
    """
    hits = set()
    sorted_addrs = sorted(target_addresses)
    if not sorted_addrs:
        return hits, 0.0, 0

    t0 = time.time()
    valid_slots = 0

    addr = PTR_SLOT_START
    while addr < PTR_SLOT_END:
        size = PTR_SLOT_STEP if (addr + PTR_SLOT_STEP) <= PTR_SLOT_END else (PTR_SLOT_END - addr)
        if size <= 0:
            addr += PTR_SLOT_STEP
            continue

        try:
            chunk = read_bytes(addr, size)
        except Exception:
            addr += PTR_SLOT_STEP
            continue

        for i in range(0, len(chunk) - 3, 4):
            slot = addr + i
            p = (
                (chunk[i] << 24)
                | (chunk[i + 1] << 16)
                | (chunk[i + 2] << 8)
                | chunk[i + 3]
            )
            if not in_game_mem(p):
                continue
            valid_slots += 1

            lo = bisect_left(sorted_addrs, p)
            hi = bisect_right(sorted_addrs, p + MAX_OFFSET)
            if lo >= hi:
                continue
            for idx in range(lo, hi):
                hits.add((slot, sorted_addrs[idx] - p))

        addr += PTR_SLOT_STEP

    return hits, time.time() - t0, valid_slots


def filter_candidates(candidates, expected_code):
    alive = set()
    for slot, off in candidates:
        try:
            base = read_u32(slot)
            if not in_game_mem(base):
                continue
            val = read_u8(base + off)
            if val == expected_code:
                alive.add((slot, off))
        except Exception:
            pass
    return alive


def candidate_preview(candidates, expected_code, title):
    print("\n%s: %d candidate(s)" % (title, len(candidates)))
    shown = 0
    for slot, off in sorted(candidates):
        if shown >= PRINT_LIMIT:
            break
        try:
            base = read_u32(slot)
            v = read_u8(base + off) if in_game_mem(base) else -1
            mark = "OK" if v == expected_code else "--"
            print(
                "  slot=%s base=%s off=0x%x val=0x%02x (%s) [%s]"
                % (
                    hex(slot),
                    hex(base),
                    off,
                    v & 0xFF,
                    code_name(v),
                    mark,
                )
            )
        except Exception:
            print("  slot=%s off=0x%x <read error>" % (hex(slot), off))
        shown += 1
    if len(candidates) > shown:
        print("  ... plus %d more" % (len(candidates) - shown))


def discovery_phase():
    print_track_table()

    if not in_race():
        print(
            "Warning: in-race sanity check failed via local position pointer. "
            "Only sample when fully loaded in race."
        )

    pool = None
    samples = 0

    while True:
        code, name = ask_track("\nEnter CURRENT track: ")

        if not wait_for_race_stable():
            print("Race not stable long enough. Retry once race is fully loaded.")
            continue

        print("Sampling stable addresses for course_code=0x%02x ..." % code)
        addrs, secs = sample_stable_addresses_for_code(code)
        print("  stable byte addresses: %d (%.2fs)" % (len(addrs), secs))
        if not addrs:
            print("  no addresses found; retry from stable in-race state")
            continue

        print(
            "Building slot+offset candidates from %s-%s ..."
            % (hex(PTR_SLOT_START), hex(PTR_SLOT_END))
        )
        sample_cands, psecs, valid_slots = find_slot_offset_candidates(addrs)
        print(
            "  sample candidates: %d from %d valid pointer slots (%.2fs)"
            % (len(sample_cands), valid_slots, psecs)
        )

        if pool is None:
            pool = sample_cands
            print("  seeded candidate pool: %d" % len(pool))
        else:
            before = len(pool)
            filtered = filter_candidates(pool, code)
            if filtered:
                pool = filtered
                print("  direct-read filter: %d -> %d" % (before, len(pool)))
            else:
                print(
                    "  direct-read filter hit 0; keeping prior pool (likely mistimed sample)"
                )

            if len(pool) > INTERSECT_HINT_THRESHOLD:
                before_i = len(pool)
                inter = pool & sample_cands
                if inter:
                    pool = inter
                    print("  safe intersection hint: %d -> %d" % (before_i, len(pool)))
                else:
                    print("  skipped destructive intersection (would go to 0)")

        samples += 1
        if not pool:
            print("No candidates left. Restart and sample only stable in-race states.")
            return None

        now_ok = filter_candidates(pool, code)
        candidate_preview(now_ok if now_ok else pool, code, "Preview")

        if len(pool) <= 12 and samples >= 2:
            print("\nPool is small; you can validate now.")

        cmd = input(
            "\nNext: [Enter]=add sample, v=validation phase, q=finish discovery: "
        ).strip().lower()
        if cmd == "q":
            return pool
        if cmd == "v":
            return pool


def validation_phase(candidates):
    if not candidates:
        print("No candidates to validate.")
        return

    current = set(candidates)
    print("\nValidation phase: switch track, enter track, filter by direct read.")

    while True:
        if not current:
            print("All candidates eliminated.")
            return

        code, name = ask_track("\nEnter NEW current track after switching race: ")
        if not wait_for_race_stable():
            print("Race not stable long enough. Retry this validation step.")
            continue

        before = len(current)
        filtered = filter_candidates(current, code)
        if not filtered:
            print("  filter would drop to 0; keeping prior set (timing/input likely wrong)")
            continue

        current = filtered
        print("  filtered: %d -> %d" % (before, len(current)))
        candidate_preview(current, code, "Validated")

        if len(current) == 1:
            slot, off = next(iter(current))
            print("\nLikely stable path:")
            print("  course_code = u8( u32(%s) + 0x%x )" % (hex(slot), off))
            print("  where course_code uses MKW slot IDs (not cup index).")
            return

        cmd = input("Continue validation? [Enter=yes, q=stop]: ").strip().lower()
        if cmd == "q":
            print("\nRemaining candidates:")
            candidate_preview(current, code, "Final")
            return


def main():
    dme.hook()
    print("Track code root finder (single script run)")
    print("Method: stable (slot, offset) discovery + direct-read validation.")

    discovered = discovery_phase()
    if not discovered:
        return

    print("\nDiscovery produced %d candidate(s)." % len(discovered))
    go = input("Start validation phase now? [Enter=yes, q=no]: ").strip().lower()
    if go == "q":
        return

    validation_phase(discovered)


if __name__ == "__main__":
    main()
