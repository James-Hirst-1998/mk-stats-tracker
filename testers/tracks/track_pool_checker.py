#!/usr/bin/env python3
"""
Poll all discovered track-code candidate paths and report consensus.

Run:
  sudo python3 testers/tracks/track_pool_checker.py
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000

POLL_INTERVAL = 0.4

# Known stable local-player position root used for in-race status only.
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Candidate paths from track_finder output.
# Each entry is (slot_addr, offset).
CANDIDATES = [
    (0x809C2338, 0x13),
    (0x809C27F0, 0x77),
    (0x809C27F8, 0x13),
    (0x809C27F8, 0x1FF),
    (0x809C2850, 0x3F),
    (0x809C2850, 0x22B),
    (0x809C28A8, 0x3B),
    (0x809C5278, 0x177),
    (0x809C5280, 0x18F),
    (0x809C5BE8, 0x137),
]

# Menu index -> (name, course code)
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


def code_name(code):
    if code in CODE_TO_NAME:
        return CODE_TO_NAME[code]
    return "?"


def read_candidate(slot, off):
    base = read_u32(slot)
    if not in_game_mem(base):
        return {
            "ok": False,
            "slot": slot,
            "off": off,
            "base": base,
            "code": None,
            "err": "base_out_of_range",
        }
    code = read_u8(base + off)
    return {
        "ok": True,
        "slot": slot,
        "off": off,
        "base": base,
        "code": code,
        "err": None,
    }


def summarize(readings):
    counts = {}
    for r in readings:
        key = "ERR" if not r["ok"] else ("0x%02x" % r["code"])
        counts[key] = counts.get(key, 0) + 1
    parts = []
    for key, ct in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        parts.append("%s:%d" % (key, ct))
    return ", ".join(parts)


def consensus(readings):
    valid = {}
    for r in readings:
        if not r["ok"]:
            continue
        c = r["code"]
        valid[c] = valid.get(c, 0) + 1
    if not valid:
        return None, 0
    best_code = max(valid, key=valid.get)
    return best_code, valid[best_code]


def print_details(readings):
    for r in readings:
        if not r["ok"]:
            print(
                "  slot=%s off=0x%x base=%s ERR=%s"
                % (hex(r["slot"]), r["off"], hex(r["base"]), r["err"])
            )
            continue
        c = r["code"]
        name = code_name(c)
        tag = "valid" if c in VALID_CODES else "invalid"
        print(
            "  slot=%s off=0x%x base=%s code=0x%02x (%s) [%s]"
            % (hex(r["slot"]), r["off"], hex(r["base"]), c, name, tag)
        )


def main():
    dme.hook()
    print("Track pool checker")
    print("Polling %d candidate paths every %.2fs. Ctrl+C to stop." % (len(CANDIDATES), POLL_INTERVAL))

    last_codes = None
    while True:
        ts = time.strftime("%H:%M:%S")
        race = in_race()

        readings = []
        for slot, off in CANDIDATES:
            try:
                readings.append(read_candidate(slot, off))
            except Exception as exc:
                readings.append(
                    {
                        "ok": False,
                        "slot": slot,
                        "off": off,
                        "base": 0,
                        "code": None,
                        "err": str(exc),
                    }
                )

        codes_snapshot = tuple((r["ok"], r["code"]) for r in readings)
        changed = codes_snapshot != last_codes
        best_code, best_count = consensus(readings)
        summary = summarize(readings)

        if best_code is None:
            print("[%s] race=%s consensus=none  counts={%s}" % (ts, race, summary))
        else:
            print(
                "[%s] race=%s consensus=0x%02x (%s) %d/%d  counts={%s}"
                % (ts, race, best_code, code_name(best_code), best_count, len(CANDIDATES), summary)
            )

        # Print full breakdown on state changes or when not unanimous.
        if changed or best_count != len(CANDIDATES):
            print_details(readings)

        last_codes = codes_snapshot
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
