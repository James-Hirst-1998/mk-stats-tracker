#!/usr/bin/env python3
"""
Race running-state tester using a primary signal plus diagnostic secondary.

Primary (state source):
  u32(u32(0x809c27f8)+0x144)

Secondary (diagnostic only):
  u32(u32(0x809c27f8)+0xb0)

Rationale:
- Cross-race logs showed 0x144 remains stable when stopped.
- 0xb0 can jitter while stopped; keep it only for comparison.

States:
- not_in_race
- in_race_running
- in_race_stopped

Run:
  sudo mk/bin/python3 -m lab.race.race_running_primary_tester

Output mode:
- Minimal: prints only `in_race=True/False` (default).
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E
COURSE_CODE_OFFSET = 0x13

PRIMARY_OFF = 0x144
SECONDARY_OFF = 0x0B0

POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0

# Running/stopped classification from PRIMARY signal deltas.
# Use sensitivity for small +/-1 ticks but strong stop hysteresis.
WINDOW = 10
DELTA_MIN = 1
RUN_ACTIVE_MIN = 2
STOP_QUIET_MIN = 9
STATE_CONFIRM_POLLS = 2
MINIMAL_LOG = True


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


def signal_class(delta_hist):
    recent = delta_hist[-WINDOW:]
    active = sum(1 for d in recent if abs(d) >= DELTA_MIN)
    quiet = sum(1 for d in recent if abs(d) < DELTA_MIN)
    if active >= RUN_ACTIVE_MIN:
        return "running"
    if quiet >= STOP_QUIET_MIN:
        return "stopped"
    return None


def signal_counts(delta_hist):
    recent = delta_hist[-WINDOW:]
    active = sum(1 for d in recent if abs(d) >= DELTA_MIN)
    quiet = sum(1 for d in recent if abs(d) < DELTA_MIN)
    return active, quiet


def main():
    dme.hook()
    print("Race Running Primary Tester (experimental)")
    if not MINIMAL_LOG:
        print("Primary=0x%x  Secondary=0x%x" % (PRIMARY_OFF, SECONDARY_OFF))
    print("Polling every %.1fs; printing every %.1fs. Ctrl+C to stop." % (POLL_INTERVAL, PRINT_INTERVAL))

    prev_primary = None
    prev_secondary = None
    hist_primary = []
    hist_secondary = []

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
            prev_primary = None
            prev_secondary = None
            hist_primary = []
            hist_secondary = []
            pending_state = None
            pending_count = 0
            time.sleep(POLL_INTERVAL)
            continue

        if not snap["in_race"]:
            p_val = None
            s_val = None
            dp = None
            ds = None
            p_class = "stopped"
            s_class = "stopped"
            target = "not_in_race"
            prev_primary = None
            prev_secondary = None
            hist_primary = []
            hist_secondary = []
            p_active, p_quiet = (0, 0)
            s_active, s_quiet = (0, 0)
        else:
            try:
                p_val = read_u32(snap["block"] + PRIMARY_OFF)
                s_val = read_u32(snap["block"] + SECONDARY_OFF)
            except Exception:
                print("[%s] read_error signals" % ts)
                prev_primary = None
                prev_secondary = None
                hist_primary = []
                hist_secondary = []
                time.sleep(POLL_INTERVAL)
                continue

            dp = 0 if prev_primary is None else (p_val - prev_primary)
            ds = 0 if prev_secondary is None else (s_val - prev_secondary)
            prev_primary = p_val
            prev_secondary = s_val

            hist_primary.append(dp)
            hist_secondary.append(ds)
            if len(hist_primary) > WINDOW:
                hist_primary = hist_primary[-WINDOW:]
            if len(hist_secondary) > WINDOW:
                hist_secondary = hist_secondary[-WINDOW:]

            p_class = signal_class(hist_primary)
            s_class = signal_class(hist_secondary)
            p_active, p_quiet = signal_counts(hist_primary)
            s_active, s_quiet = signal_counts(hist_secondary)

            if p_class == "running":
                target = "in_race_running"
            elif p_class == "stopped":
                target = "in_race_stopped"
            else:
                target = None

        # Debounced state commit.
        if target is not None:
            if target == pending_state:
                pending_count += 1
            else:
                pending_state = target
                pending_count = 1
            if pending_count >= STATE_CONFIRM_POLLS:
                committed_state = target

        # Event logs.
        if not MINIMAL_LOG:
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

        # Print on interval or committed state/in_race change.
        do_print = (
            (committed_state != last_committed_state)
            or (snap["in_race"] != last_in_race)
            or ((now - last_print) >= PRINT_INTERVAL)
        )
        if do_print:
            if MINIMAL_LOG:
                print("[%s] in_race=%s" % (ts, snap["in_race"]))
            else:
                if not snap["in_race"]:
                    print("[%s] state=%s in_race=False block=%s" % (ts, committed_state or "not_in_race", hex(snap["block"])))
                else:
                    print(
                        "[%s] state=%s in_race=True pos=%d course=0x%02x block=%s  P(v=%d d=%+d cls=%s a/q=%d/%d)  S(v=%d d=%+d cls=%s a/q=%d/%d)  agree=%s"
                        % (
                            ts,
                            committed_state or "in_race_stopped",
                            snap["pos"],
                            snap["course"] if snap["course"] is not None else 0,
                            hex(snap["block"]),
                            p_val,
                            dp if dp is not None else 0,
                            p_class,
                            p_active,
                            p_quiet,
                            s_val,
                            ds if ds is not None else 0,
                            s_class,
                            s_active,
                            s_quiet,
                            p_class == s_class,
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
