#!/usr/bin/env python3
"""
Track race progress state from a single timer-like field.

Chosen candidate:
  timer = u32(u32(0x809c27f8) + 0xb0)

Why this one:
- 32-bit aligned offset.
- Stable behavior in probe output.
- Avoids unaligned alias candidates.

States:
- not_in_race
- in_race_stopped   (paused/countdown/finished/static)
- in_race_running   (timer value is advancing)

Run:
  sudo mk/bin/python3 -m lab.race.race_progress_state_tester
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E
COURSE_CODE_OFFSET = 0x13
TIMER_OFFSET = 0xB0

POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0
RUN_WINDOW = 8
MIN_CHANGES_FOR_RUNNING = 2


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def snapshot():
    try:
        block = read_u32(STABLE_PTR)
    except Exception:
        return {"ok": False, "in_race": False, "block": 0, "pos": None, "course": None, "timer": None}

    if not in_mem1(block):
        return {"ok": True, "in_race": False, "block": block, "pos": None, "course": None, "timer": None}

    try:
        pos = read_u8(block + POSITION_OFFSET)
    except Exception:
        return {"ok": False, "in_race": False, "block": block, "pos": None, "course": None, "timer": None}

    in_race = 1 <= pos <= 12
    if not in_race:
        return {"ok": True, "in_race": False, "block": block, "pos": pos, "course": None, "timer": None}

    try:
        course = read_u8(block + COURSE_CODE_OFFSET)
        timer = read_u32(block + TIMER_OFFSET)
    except Exception:
        return {"ok": False, "in_race": True, "block": block, "pos": pos, "course": None, "timer": None}

    return {
        "ok": True,
        "in_race": True,
        "block": block,
        "pos": pos,
        "course": course,
        "timer": timer,
    }


def derive_running(delta_hist):
    recent = delta_hist[-RUN_WINDOW:]
    changed = sum(1 for d in recent if d != 0)
    return changed >= MIN_CHANGES_FOR_RUNNING


def derive_state(in_race, running):
    if not in_race:
        return "not_in_race"
    if running:
        return "in_race_running"
    return "in_race_stopped"


def main():
    dme.hook()
    print("Race Progress State Tester (experimental)")
    print("Timer field: u32(u32(0x809c27f8)+0xb0)")
    print("Polling every %.1fs; print every %.1fs. Ctrl+C to stop." % (POLL_INTERVAL, PRINT_INTERVAL))

    prev_timer = None
    delta_hist = []
    last_state = None
    last_print = 0.0

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        s = snapshot()

        if not s["ok"]:
            line = "[%s] read_error state=unknown" % ts
            print(line)
            prev_timer = None
            delta_hist = []
            time.sleep(POLL_INTERVAL)
            continue

        if not s["in_race"]:
            state = "not_in_race"
            prev_timer = None
            delta_hist = []
            delta = None
            running = False
        else:
            if prev_timer is None or s["timer"] is None:
                delta = 0
            else:
                delta = s["timer"] - prev_timer
            prev_timer = s["timer"]

            delta_hist.append(delta)
            if len(delta_hist) > RUN_WINDOW:
                delta_hist = delta_hist[-RUN_WINDOW:]

            running = derive_running(delta_hist)
            state = derive_state(True, running)

        changed = state != last_state
        should_print = changed or ((now - last_print) >= PRINT_INTERVAL)
        if should_print:
            if not s["in_race"]:
                print("[%s] state=%s in_race=False block=%s" % (ts, state, hex(s["block"])))
            else:
                print(
                    "[%s] state=%s in_race=True pos=%d course=0x%02x block=%s timer=%d delta=%+d running=%s"
                    % (
                        ts,
                        state,
                        s["pos"],
                        s["course"] if s["course"] is not None else 0,
                        hex(s["block"]),
                        s["timer"] if s["timer"] is not None else -1,
                        delta if delta is not None else 0,
                        running,
                    )
                )
            last_print = now

        last_state = state
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
