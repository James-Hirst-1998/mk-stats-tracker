#!/usr/bin/env python3
"""
Minimal in-progress tracker for Mario Kart Wii race state.

Signals:
- in_race gate: position check via u32(0x809c27f8)+0x3e
- in_progress signal: movement of u32(u32(0x809c27f8)+0x144)

Output:
- only prints `in_race` + `in_progress` (plus timestamp)

Run:
  sudo mk/bin/python3 -m lab.race.race_in_progress_tester
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E
PROGRESS_SIGNAL_OFFSET = 0x144

POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0

# Hysteresis tuning:
# - Ignore tiny jitter by requiring larger delta magnitude.
# - Require sustained movement to enter running.
# - Require sustained quiet to leave running.
RUN_WINDOW = 8
STOP_WINDOW = 14
MOVE_DELTA_MIN = 16
RUN_MOVE_MIN = 3
STOP_MOVE_MAX = 0
STATE_CONFIRM_POLLS = 2


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def race_snapshot():
    try:
        block = read_u32(STABLE_PTR)
    except Exception:
        return {"ok": False, "in_race": False, "block": 0}

    if not in_mem1(block):
        return {"ok": True, "in_race": False, "block": block}

    try:
        pos = read_u8(block + POSITION_OFFSET)
    except Exception:
        return {"ok": False, "in_race": False, "block": block}

    return {"ok": True, "in_race": (1 <= pos <= 12), "block": block}


def main():
    dme.hook()
    print("Race In-Progress Tester (experimental)")
    print("Polling every %.1fs; printing every %.1fs. Ctrl+C to stop." % (POLL_INTERVAL, PRINT_INTERVAL))

    prev_value = None
    deltas = []

    committed_in_progress = False
    last_committed_in_progress = None
    pending_in_progress = None
    pending_count = 0
    seen_running_this_race = False

    last_in_race = None
    last_print = 0.0

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        snap = race_snapshot()

        if not snap["ok"]:
            print("[%s] read_error" % ts)
            prev_value = None
            deltas = []
            pending_in_progress = None
            pending_count = 0
            time.sleep(POLL_INTERVAL)
            continue

        if not snap["in_race"]:
            prev_value = None
            deltas = []
            pending_in_progress = False
            pending_count = STATE_CONFIRM_POLLS
            committed_in_progress = False
            seen_running_this_race = False
        else:
            try:
                value = read_u32(snap["block"] + PROGRESS_SIGNAL_OFFSET)
            except Exception:
                print("[%s] read_error signal" % ts)
                prev_value = None
                deltas = []
                time.sleep(POLL_INTERVAL)
                continue

            delta = 0 if prev_value is None else (value - prev_value)
            prev_value = value

            deltas.append(delta)
            if len(deltas) > STOP_WINDOW:
                deltas = deltas[-STOP_WINDOW:]

            run_recent = deltas[-RUN_WINDOW:]
            stop_recent = deltas[-STOP_WINDOW:]

            run_moves = sum(1 for d in run_recent if abs(d) >= MOVE_DELTA_MIN)
            stop_moves = sum(1 for d in stop_recent if abs(d) >= MOVE_DELTA_MIN)

            target = None
            if run_moves >= RUN_MOVE_MIN:
                seen_running_this_race = True
                target = True
            elif (
                seen_running_this_race
                and len(stop_recent) >= STOP_WINDOW
                and stop_moves <= STOP_MOVE_MAX
            ):
                target = False

            if target is not None:
                if target == pending_in_progress:
                    pending_count += 1
                else:
                    pending_in_progress = target
                    pending_count = 1
                if pending_count >= STATE_CONFIRM_POLLS:
                    committed_in_progress = target

        do_print = (
            (snap["in_race"] != last_in_race)
            or (committed_in_progress != last_committed_in_progress)
            or ((now - last_print) >= PRINT_INTERVAL)
        )
        if do_print:
            print("[%s] in_race=%s in_progress=%s" % (ts, snap["in_race"], committed_in_progress))
            last_print = now

        last_in_race = snap["in_race"]
        last_committed_in_progress = committed_in_progress
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
