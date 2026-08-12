#!/usr/bin/env python3
"""
Race running-state tester using a consensus of two stable candidates.

Selected candidates (from cross-race checker):
  A: u32(u32(0x809c27f8)+0xb0)
  B: u32(u32(0x809c27f8)+0x144)

Why these two:
- In your cross-race output, they agreed and stayed stable when stopped.
- Other candidates (0xa0, 0x148) showed idle jitter/flicker.

Output states:
- not_in_race
- in_race_running
- in_race_stopped

Run:
  sudo mk/bin/python3 -m lab.race.race_running_consensus_tester
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E
COURSE_CODE_OFFSET = 0x13

SIG_A_OFF = 0x0B0
SIG_B_OFF = 0x144

POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0

# Per-signal running detection:
# in a short window, if enough deltas are non-zero, signal is "running".
DELTA_WINDOW = 6
MIN_NONZERO_DELTAS = 2

# State debounce:
# require same target state N consecutive polls before committing.
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
        return {"ok": False, "in_race": False, "block": 0, "pos": None, "course": None}

    if not in_mem1(block):
        return {"ok": True, "in_race": False, "block": block, "pos": None, "course": None}

    try:
        pos = read_u8(block + POSITION_OFFSET)
    except Exception:
        return {"ok": False, "in_race": False, "block": block, "pos": None, "course": None}

    in_race = 1 <= pos <= 12
    if not in_race:
        return {"ok": True, "in_race": False, "block": block, "pos": pos, "course": None}

    try:
        course = read_u8(block + COURSE_CODE_OFFSET)
    except Exception:
        return {"ok": False, "in_race": True, "block": block, "pos": pos, "course": None}

    return {"ok": True, "in_race": True, "block": block, "pos": pos, "course": course}


def read_signal(block, off):
    return read_u32(block + off)


def signal_running(delta_hist):
    recent = delta_hist[-DELTA_WINDOW:]
    nonzero = sum(1 for d in recent if d != 0)
    return nonzero >= MIN_NONZERO_DELTAS


def target_state(in_race, run_a, run_b):
    if not in_race:
        return "not_in_race"
    if run_a and run_b:
        return "in_race_running"
    if (not run_a) and (not run_b):
        return "in_race_stopped"
    return None  # transition/ambiguous: hold previous committed state


def main():
    dme.hook()
    print("Race Running Consensus Tester (experimental)")
    print("Signals: A=0x%x, B=0x%x" % (SIG_A_OFF, SIG_B_OFF))
    print("Polling every %.1fs; printing every %.1fs. Ctrl+C to stop." % (POLL_INTERVAL, PRINT_INTERVAL))

    prev_a = None
    prev_b = None
    deltas_a = []
    deltas_b = []

    committed_state = None
    last_committed_state = None
    pending_state = None
    pending_count = 0

    last_print = 0.0
    last_in_race = None
    last_course = None

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        snap = race_snapshot()

        if not snap["ok"]:
            print("[%s] read_error state=unknown" % ts)
            prev_a = None
            prev_b = None
            deltas_a = []
            deltas_b = []
            pending_state = None
            pending_count = 0
            time.sleep(POLL_INTERVAL)
            continue

        if not snap["in_race"]:
            a_val = None
            b_val = None
            da = None
            db = None
            run_a = False
            run_b = False
            prev_a = None
            prev_b = None
            deltas_a = []
            deltas_b = []
        else:
            try:
                a_val = read_signal(snap["block"], SIG_A_OFF)
                b_val = read_signal(snap["block"], SIG_B_OFF)
            except Exception:
                print("[%s] read_error signals" % ts)
                prev_a = None
                prev_b = None
                deltas_a = []
                deltas_b = []
                time.sleep(POLL_INTERVAL)
                continue

            da = 0 if prev_a is None else (a_val - prev_a)
            db = 0 if prev_b is None else (b_val - prev_b)
            prev_a = a_val
            prev_b = b_val

            deltas_a.append(da)
            deltas_b.append(db)
            if len(deltas_a) > DELTA_WINDOW:
                deltas_a = deltas_a[-DELTA_WINDOW:]
            if len(deltas_b) > DELTA_WINDOW:
                deltas_b = deltas_b[-DELTA_WINDOW:]

            run_a = signal_running(deltas_a)
            run_b = signal_running(deltas_b)

        tgt = target_state(snap["in_race"], run_a, run_b)
        if tgt is not None:
            if tgt == pending_state:
                pending_count += 1
            else:
                pending_state = tgt
                pending_count = 1
            if pending_count >= STATE_CONFIRM_POLLS:
                committed_state = tgt

        # Events
        if last_in_race is None or snap["in_race"] != last_in_race:
            print(
                "[%s] EVENT in_race_changed %s -> %s block=%s"
                % (ts, last_in_race, snap["in_race"], hex(snap["block"]))
            )
        if snap["in_race"]:
            if last_course is None:
                last_course = snap["course"]
            elif snap["course"] != last_course:
                print("[%s] EVENT course_changed 0x%02x -> 0x%02x" % (ts, last_course, snap["course"]))
                last_course = snap["course"]
        else:
            last_course = None

        # Print on interval and on committed-state transition.
        changed = committed_state != last_committed_state
        if (now - last_print) >= PRINT_INTERVAL:
            changed = True

        if changed:
            if not snap["in_race"]:
                print(
                    "[%s] state=%s in_race=False block=%s"
                    % (ts, committed_state or "not_in_race", hex(snap["block"]))
                )
            else:
                print(
                    "[%s] state=%s in_race=True pos=%d course=0x%02x block=%s  A(v=%d d=%+d run=%s)  B(v=%d d=%+d run=%s)  agree=%s"
                    % (
                        ts,
                        committed_state or "in_race_stopped",
                        snap["pos"],
                        snap["course"] if snap["course"] is not None else 0,
                        hex(snap["block"]),
                        a_val,
                        da if da is not None else 0,
                        run_a,
                        b_val,
                        db if db is not None else 0,
                        run_b,
                        run_a == run_b,
                    )
                )
            last_print = now
        last_committed_state = committed_state

        last_in_race = snap["in_race"]
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
