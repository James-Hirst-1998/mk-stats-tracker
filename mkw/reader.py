"""Read a live race out of Dolphin.

Every function here is a plain read of an address in `mkw.addresses`. Nothing
is inferred; if a value cannot be read the function returns None rather than
guessing. The same functions are driven offline from a recording by
`tools/replay_live.py`, which swaps out the four accessors below - so whatever
this prints live is exactly what the offline checks verify.
"""

import struct

from mkw import addresses as A
from mkw.names import DAMAGE_TYPES

_dme = None


def hook():
    """Attach to a running Dolphin. Returns True on success."""
    global _dme
    import dolphin_memory_engine
    _dme = dolphin_memory_engine
    _dme.hook()
    return _dme.is_hooked()


def _read(addr, size):
    return bytes(_dme.read_bytes(addr - A.MEM1[0], size))


def u8(addr):
    return _read(addr, 1)[0]


def u16(addr):
    return struct.unpack(">H", _read(addr, 2))[0]


def u32(addr):
    return struct.unpack(">I", _read(addr, 4))[0]


def f32(addr):
    return struct.unpack(">f", _read(addr, 4))[0]


def s32(addr):
    v = u32(addr)
    return v - (1 << 32) if v & 0x80000000 else v


def in_mem1(p):
    return A.MEM1[0] <= p < A.MEM1[1]


def read_timer(addr):
    """Seconds, or None if the game has not filled this timer in yet."""
    if not in_mem1(addr) or not u8(addr + A.TIMER_SET):
        return None
    return (u16(addr + A.TIMER_MINUTES) * 60
            + u8(addr + A.TIMER_SECONDS)
            + u16(addr + A.TIMER_MILLIS) / 1000.0)


def read_course():
    block = u32(A.COURSE_PTR)
    return u8(block + A.COURSE_OFFSET) if in_mem1(block) else None


def read_players():
    """Everything the race manager knows per racer, or None if not racing."""
    base = u32(A.PLAYER_PTR) + A.PLAYER_DELTA
    if not in_mem1(base):
        return None
    out = []
    for slot in range(A.N_PLAYERS):
        p = base + slot * A.PLAYER_STRIDE
        max_lap = u8(p + A.OFF_MAX_LAP)
        lap_ptr = u32(p + A.OFF_LAP_TIMES)
        splits = []
        if in_mem1(lap_ptr):
            for k in range(min(max_lap, 8)):
                splits.append(read_timer(lap_ptr + k * A.TIMER_SIZE))
        cur = u16(p + A.OFF_CURRENT_LAP)
        out.append({
            "slot": slot,
            "position": u8(p + A.OFF_POSITION),
            "lap": cur,
            "max_lap": max_lap,
            "completion": f32(p + A.OFF_COMPLETION),
            "lap_fraction": f32(p + A.OFF_LAP_FRACTION),
            "clock": u32(p + A.OFF_FRAME_COUNTER) / 60.0,
            "leading": u32(p + A.OFF_FRAMES_IN_FIRST) / 60.0,
            "cumulative": splits,
            "finished": bool(max_lap) and cur > max_lap,
            "finish": read_timer(u32(p + A.OFF_FINISH_TIME)),
        })
    # A valid race always has each position 1..12 exactly once. This is the
    # cheapest way to tell a real race from a menu full of stale memory.
    if sorted(r["position"] for r in out) != list(range(1, A.N_PLAYERS + 1)):
        return None
    return out


def item_base():
    director = u32(A.ITEM_DIRECTOR)
    if not in_mem1(director):
        return None
    base = u32(director + A.OFF_ITEM_ARRAY)
    return base if in_mem1(base) else None


def read_items(base):
    """(held, roulette) id per racer, or None if not readable."""
    held, roul = [], []
    for slot in range(A.N_PLAYERS):
        p = base + slot * A.ITEM_STRIDE
        held.append(u8(p + A.OFF_HELD))
        roul.append(u8(p + A.OFF_ROULETTE))
    if any(v > A.EMPTY_ITEM for v in held + roul):
        return None
    return held, roul


def read_damage(base):
    """Damage type per racer, -1 where the racer is not currently hit."""
    out = []
    for slot in range(A.N_PLAYERS):
        accessor = u32(base + slot * A.ITEM_STRIDE)
        if not in_mem1(accessor):
            return None
        sub = u32(accessor + A.OFF_ACCESSOR_SUB)
        if not in_mem1(sub):
            return None
        v = s32(sub + A.OFF_DAMAGE)
        if not (A.NO_DAMAGE <= v <= max(DAMAGE_TYPES)):
            return None
        out.append(v)
    return out


def read_world_items():
    """Items actually on the track: [(type, owner)], or None.

    Not yet used for naming a hit - see `docs/EXPERIMENTS.md`, "open".
    """
    director = u32(A.ITEM_DIRECTOR)
    if not in_mem1(director):
        return None
    out = []
    for i in range(A.MAX_OBJECTS):
        p = u32(director + A.OFF_OBJECT_ARRAY + i * 4)
        if not (0x80900000 <= p < 0x81800000):
            continue
        typ = u32(p + A.OFF_OBJECT_TYPE)
        owner = u8(p + A.OFF_OBJECT_OWNER)
        if typ < 24 and owner <= A.N_PLAYERS:
            out.append((typ, owner))
    return out


def read():
    """One complete snapshot, or None when no race is running."""
    players = read_players()
    if players is None:
        return None
    base = item_base()
    items = read_items(base) if base is not None else None
    damage = read_damage(base) if base is not None else None
    for r in players:
        r["item"] = items[0][r["slot"]] if items else None
        r["roulette"] = items[1][r["slot"]] if items else None
        r["damage"] = damage[r["slot"]] if damage else None
    return {"course_code": read_course(), "players": players}


def splits_of(cumulative):
    """Per-lap times from the game's cumulative lap finish times."""
    out, prev = [], 0.0
    for c in cumulative:
        if c is None:
            break
        out.append(c - prev)
        prev = c
    return out
