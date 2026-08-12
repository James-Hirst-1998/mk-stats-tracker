#!/usr/bin/env python3
"""
Cross-race checker for race-clock candidates.

Goal:
- Watch candidate timer fields across race/menu transitions.
- Confirm they agree on running/stopped state in-race.
- Flag divergence so we can pick a single canonical offset.

Candidates:
  u32(u32(0x809c27f8)+0xa0)
  u32(u32(0x809c27f8)+0xb0)
  u32(u32(0x809c27f8)+0x144)
  u32(u32(0x809c27f8)+0x148)

Run:
  sudo mk/bin/python3 -m lab.race.race_clock_cross_race_checker
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E
COURSE_CODE_OFFSET = 0x13

CANDIDATES = [
    (0x0A0, 4),
    (0x0B0, 4),
    (0x144, 4),
    (0x148, 4),
]

POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0
RUN_WINDOW = 6
MIN_CHANGES_FOR_RUNNING = 2


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def read_be(buf, off, width):
    if width == 1:
        return buf[off]
    if width == 2:
        return (buf[off] << 8) | buf[off + 1]
    if width == 4:
        return (buf[off] << 24) | (buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3]
    raise ValueError("unsupported width")


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


def read_candidate_value(block, off, width):
    data = bytes(read_bytes(block + off, width))
    return read_be(data, 0, width)


def calc_running(delta_hist):
    recent = delta_hist[-RUN_WINDOW:]
    changed = sum(1 for d in recent if d != 0)
    return changed >= MIN_CHANGES_FOR_RUNNING


def main():
    dme.hook()
    print("Race Clock Cross-Race Checker (experimental)")
    print("Polling every %.1fs; printing every %.1fs. Ctrl+C to stop." % (POLL_INTERVAL, PRINT_INTERVAL))
    print("Candidates:")
    for i, (off, width) in enumerate(CANDIDATES):
        print("  #%d u%d(u32(0x809c27f8)+0x%x)" % (i, width * 8, off))

    prev_values = {}
    delta_hist = {i: [] for i in range(len(CANDIDATES))}

    last_print = 0.0
    last_in_race = None
    last_course = None
    last_consensus = None

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        snap = race_snapshot()

        if not snap["ok"]:
            print("[%s] read_error state=unknown" % ts)
            prev_values = {}
            for i in delta_hist:
                delta_hist[i] = []
            time.sleep(POLL_INTERVAL)
            continue

        lines = []
        run_flags = []
        if not snap["in_race"]:
            prev_values = {}
            for i in delta_hist:
                delta_hist[i] = []
            consensus_running = False
            unanimous = True
        else:
            for i, (off, width) in enumerate(CANDIDATES):
                try:
                    value = read_candidate_value(snap["block"], off, width)
                    delta = 0 if i not in prev_values else (value - prev_values[i])
                    prev_values[i] = value
                    h = delta_hist[i]
                    h.append(delta)
                    if len(h) > RUN_WINDOW:
                        delta_hist[i] = h[-RUN_WINDOW:]
                        h = delta_hist[i]
                    running = calc_running(h)
                    run_flags.append(running)
                    lines.append(
                        "#%d off=0x%x v=%d d=%+d run=%s" % (i, off, value, delta, running)
                    )
                except Exception:
                    prev_values.pop(i, None)
                    delta_hist[i] = []
                    run_flags.append(False)
                    lines.append("#%d off=0x%x v=? d=? run=?" % (i, off))

            trues = sum(1 for x in run_flags if x)
            consensus_running = trues >= max(1, (len(run_flags) // 2) + 1)
            unanimous = all(x == run_flags[0] for x in run_flags) if run_flags else True

        # Transition/event logs.
        if last_in_race is None or snap["in_race"] != last_in_race:
            print(
                "[%s] EVENT in_race_changed %s -> %s block=%s"
                % (ts, last_in_race, snap["in_race"], hex(snap["block"]))
            )
        if snap["in_race"]:
            if last_course is None:
                last_course = snap["course"]
            elif snap["course"] != last_course:
                print(
                    "[%s] EVENT course_changed 0x%02x -> 0x%02x"
                    % (ts, last_course, snap["course"])
                )
                last_course = snap["course"]
        else:
            last_course = None
        if last_consensus is None or consensus_running != last_consensus:
            print(
                "[%s] EVENT race_running_changed %s -> %s"
                % (ts, last_consensus, consensus_running)
            )
            last_consensus = consensus_running

        # Periodic/changed status line.
        changed = False
        if last_in_race is not None and snap["in_race"] != last_in_race:
            changed = True
        if (now - last_print) >= PRINT_INTERVAL:
            changed = True
        if changed:
            if not snap["in_race"]:
                print(
                    "[%s] in_race=False race_running=False unanimous=%s block=%s"
                    % (ts, unanimous, hex(snap["block"]))
                )
            else:
                print(
                    "[%s] in_race=True race_running=%s unanimous=%s pos=%d course=0x%02x block=%s  %s"
                    % (
                        ts,
                        consensus_running,
                        unanimous,
                        snap["pos"],
                        snap["course"] if snap["course"] is not None else 0,
                        hex(snap["block"]),
                        " | ".join(lines),
                    )
                )
            last_print = now

        last_in_race = snap["in_race"]
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
