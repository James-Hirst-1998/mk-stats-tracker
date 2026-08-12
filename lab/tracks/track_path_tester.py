#!/usr/bin/env python3
"""
Verify a discovered track-code pointer path across race changes.

Path under test:
  course_code = u8( u32(slot_addr) + offset )

Run:
  sudo mk/bin/python3 -m lab.tracks.track_path_tester
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000

# Stable local-player position root used only for race-state gating.
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

RACE_STABLE_POLLS = 6
RACE_STABLE_INTERVAL = 0.25
RACE_STABLE_TIMEOUT = 10.0

TRACK_STABLE_POLLS = 5
TRACK_WAIT_TIMEOUT = 180.0

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


def code_name(code):
    if code in CODE_TO_NAME:
        return CODE_TO_NAME[code]
    return "?"


def normalize_name(name):
    return "".join(ch.lower() for ch in name if ch.isalnum())


def print_track_table():
    print("Track table (menu index -> course code):")
    for idx, (name, code) in enumerate(TRACKS):
        print("  %2d -> 0x%02x (%2d)  %s" % (idx, code, code, name))


def parse_track_input(raw):
    s = raw.strip()
    if not s:
        raise ValueError("empty input")

    lower = s.lower()
    if lower.startswith("c:") or lower.startswith("code:"):
        tail = s.split(":", 1)[1].strip()
        v = int(tail, 0)
        if v not in VALID_CODES:
            raise ValueError("course code not in vanilla set")
        return v, code_name(v), "course_code"

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
    raise ValueError("unknown or ambiguous track")


def ask_expected_track():
    while True:
        raw = input("Enter expected NEXT track, or q to stop: ").strip()
        if raw.lower() in ("q", "quit", "exit"):
            return None, None
        try:
            code, name, source = parse_track_input(raw)
            print(
                "Expected %s (%s) -> course_code=0x%02x (%d)"
                % (name, source, code, code)
            )
            return code, name
        except Exception as exc:
            print("Invalid input:", exc)


def ask_path():
    while True:
        raw_slot = input("Enter slot address (hex), e.g. 0x809bec9c: ").strip()
        raw_off = input("Enter offset (hex/dec), e.g. 0x70: ").strip()
        try:
            slot = int(raw_slot, 0)
            off = int(raw_off, 0)
            if slot % 4 != 0:
                print("Warning: slot is not 4-byte aligned.")
            if off < 0 or off > 0x4000:
                print("Warning: offset looks large; continuing anyway.")
            return slot, off
        except Exception as exc:
            print("Invalid slot/offset:", exc)


def read_course_code_via_path(slot_addr, off):
    base_ptr = read_u32(slot_addr)
    if not in_game_mem(base_ptr):
        raise RuntimeError("path base pointer out of range: %s" % hex(base_ptr))
    course_code = read_u8(base_ptr + off)
    return course_code, base_ptr


def wait_for_next_stable_course(slot_addr, off, previous_code):
    """Wait for next stable valid course code after a race transition."""
    stable_count = 0
    stable_value = None
    last_base = None
    race_true_streak = 0
    saw_non_race = False
    t0 = time.time()

    while time.time() - t0 < TRACK_WAIT_TIMEOUT:
        if not in_race():
            saw_non_race = True
            race_true_streak = 0
            stable_count = 0
            stable_value = None
            time.sleep(RACE_STABLE_INTERVAL)
            continue

        race_true_streak += 1
        if race_true_streak < RACE_STABLE_POLLS:
            time.sleep(RACE_STABLE_INTERVAL)
            continue

        try:
            v, base = read_course_code_via_path(slot_addr, off)
        except Exception:
            stable_count = 0
            stable_value = None
            time.sleep(RACE_STABLE_INTERVAL)
            continue

        # Ignore invalid/transient values.
        if v not in VALID_CODES:
            stable_count = 0
            stable_value = None
            last_base = base
            time.sleep(RACE_STABLE_INTERVAL)
            continue

        # Before a full non-race->race transition, ignore unchanged code.
        if not saw_non_race and v == previous_code:
            stable_count = 0
            stable_value = None
            last_base = base
            time.sleep(RACE_STABLE_INTERVAL)
            continue

        if stable_value == v:
            stable_count += 1
        else:
            stable_value = v
            stable_count = 1
        last_base = base

        if stable_count >= TRACK_STABLE_POLLS:
            return stable_value, last_base

        time.sleep(RACE_STABLE_INTERVAL)

    return None, last_base


def main():
    dme.hook()
    print("Track path tester")
    print_track_table()

    slot_addr, off = ask_path()
    print(
        "Testing path: course_code = u8( u32(%s) + 0x%x )"
        % (hex(slot_addr), off)
    )

    if not wait_for_race_stable():
        print("Race did not look stable. Start a race and run again.")
        return

    try:
        current_code, base = read_course_code_via_path(slot_addr, off)
    except Exception as exc:
        print("Initial read failed:", exc)
        return

    print(
        "Current via path: 0x%02x (%s) [slot=%s base=%s off=0x%x]"
        % (current_code, code_name(current_code), hex(slot_addr), hex(base), off)
    )

    while True:
        expected_code, expected_name = ask_expected_track()
        if expected_code is None:
            print("Done.")
            return

        print(
            "Switch to that track and load race. Waiting for next stable valid course code..."
        )
        observed, base = wait_for_next_stable_course(slot_addr, off, current_code)
        if observed is None:
            print("Timed out waiting for next stable course code.")
            continue

        outcome = "PASS" if observed == expected_code else "FAIL"
        print(
            "%s expected=0x%02x (%s) observed=0x%02x (%s) [slot=%s base=%s off=0x%x]"
            % (
                outcome,
                expected_code,
                expected_name,
                observed,
                code_name(observed),
                hex(slot_addr),
                hex(base) if base is not None else "?",
                off,
            )
        )
        current_code = observed


if __name__ == "__main__":
    main()
