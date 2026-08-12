"""Read a live race out of Dolphin.

Every function here is a plain read of an address in `mkw.addresses`. Nothing
is inferred; if a value cannot be read the function returns None rather than
guessing. The same functions are driven offline from a recording by
`tools/replay_live.py`, which swaps out the four accessors below - so whatever
this prints live is exactly what the offline checks verify.
"""

import struct

from mkw import addresses as A
from mkw.names import DAMAGE_TYPES, PLAYER_TYPES

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


def in_heap(p):
    return A.HEAP[0] <= p < A.HEAP[1]


def in_mem2(p):
    return A.MEM2[0] <= p < A.MEM2[1]


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


def read_race_frames():
    """Frames since GO, or None. Zero through the intro and the countdown.

    The per-racer counter at +0x2C is not this: it starts 412 frames earlier,
    at the intro camera, and freezes when that racer finishes. This one is the
    clock the game puts on screen.
    """
    obj = u32(A.PLAYER_PTR)
    return u32(obj + A.OFF_RACE_FRAMES) if in_mem1(obj) else None


def read_players():
    """Everything the race manager knows per racer, or None if not racing."""
    base = u32(A.PLAYER_PTR) + A.PLAYER_DELTA
    if not in_mem1(base):
        return None
    out = []
    for slot in range(A.N_PLAYERS):
        p = base + slot * A.PLAYER_STRIDE
        reached = u8(p + A.OFF_LAP_REACHED)
        lap_ptr = u32(p + A.OFF_LAP_TIMES)
        splits = []
        if in_mem1(lap_ptr):
            for k in range(min(reached, 8)):
                splits.append(read_timer(lap_ptr + k * A.TIMER_SIZE))
        cur = u16(p + A.OFF_CURRENT_LAP)
        out.append({
            "slot": slot,
            "position": u8(p + A.OFF_POSITION),
            "lap": cur,
            "lap_reached": reached,
            "completion": f32(p + A.OFF_COMPLETION),
            "lap_fraction": f32(p + A.OFF_LAP_FRACTION),
            "clock": u32(p + A.OFF_FRAME_COUNTER) / 60.0,
            "leading": u32(p + A.OFF_FRAMES_IN_FIRST) / 60.0,
            "cumulative": splits,
            "finished": bool(reached) and cur > reached,
            "finish": read_timer(u32(p + A.OFF_FINISH_TIME)),
        })
    # A valid race always has each position 1..12 exactly once. This is the
    # cheapest way to tell a real race from a menu full of stale memory.
    if sorted(r["position"] for r in out) != list(range(1, A.N_PLAYERS + 1)):
        return None
    return out


def read_racers():
    """Who each racer is, or None. Fixed for a race, so cheap to re-read.

    RaceConfig lives in MEM2. `_read` subtracts MEM1's base, which is also what
    the recorder does, and Dolphin's flat address space continues into MEM2 at
    that offset - so MEM2 addresses read correctly without a special case.
    """
    cfg = u32(A.RACE_CONFIG)
    if not in_mem2(cfg):
        return None
    count = u8(cfg + A.OFF_RACER_COUNT)
    if not 0 < count <= A.N_PLAYERS:
        return None
    out = []
    for slot in range(A.N_PLAYERS):
        p = cfg + A.OFF_RACERS + slot * A.RACER_STRIDE
        character = u32(p + A.OFF_CHARACTER)
        vehicle = u32(p + A.OFF_VEHICLE)
        kind = u32(p + A.OFF_PLAYER_TYPE)
        if character > A.MAX_CHARACTER or vehicle > A.MAX_VEHICLE:
            return None
        if kind not in PLAYER_TYPES:
            return None
        out.append({
            "slot": slot,
            "character": character,
            "vehicle": vehicle,
            "type": kind,
            "cpu": kind == A.TYPE_CPU,
            "grid": u8(p + A.OFF_GRID),
        })
    return out


def read_settings():
    """The race's settings block, as raw words, or None.

    Only `[0]` is understood - it is the course id, and it agrees with the
    `COURSE_PTR` path on every recording. The rest is stored undecoded so that
    a question asked later (which race of a VS sequence is this?) can be
    answered from races already saved instead of needing new ones.
    """
    cfg = u32(A.RACE_CONFIG)
    if not in_mem2(cfg):
        return None
    return [u32(cfg + A.OFF_SETTINGS + i * 4) for i in range(A.SETTINGS_WORDS)]


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
    """Every item in the world as {object address: (type, owner)}, or None.

    One pool per item type; the live ones are the front of each pool's array.
    A pool slot keeps its address for the whole race, so the key is a stable
    identity and an address disappearing is that item being destroyed.

    Fails closed: every pool entry states its own type index and every object
    repeats it, so a bad read is caught rather than returned.
    """
    director = u32(A.ITEM_DIRECTOR)
    if not in_mem1(director):
        return None
    out = {}
    for t in range(A.N_OBJECT_TYPES):
        e = director + A.OFF_POOL_TABLE + t * A.POOL_STRIDE
        if u32(e + A.OFF_POOL_TYPE) != t:
            return None
        array = u32(e + A.OFF_POOL_ARRAY)
        cap = u32(e + A.OFF_POOL_CAP)
        live = u32(e + A.OFF_POOL_LIVE)
        if not in_heap(array) or not 0 < cap <= A.MAX_POOL or live > cap:
            return None
        for k in range(live):
            obj = u32(array + k * 4)
            if not in_heap(obj) or u32(obj + A.OFF_OBJECT_TYPE) != t:
                return None
            out[obj] = (t, u8(obj + A.OFF_OBJECT_OWNER))
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
    frames = read_race_frames()
    return {"course_code": read_course(), "players": players,
            "racers": read_racers(), "world_items": read_world_items(),
            "settings": read_settings(),
            "race_frames": frames,
            "race_time": None if frames is None else frames / 60.0}


def splits_of(cumulative):
    """Per-lap times from the game's cumulative lap finish times."""
    out, prev = [], 0.0
    for c in cumulative:
        if c is None:
            break
        out.append(c - prev)
        prev = c
    return out
