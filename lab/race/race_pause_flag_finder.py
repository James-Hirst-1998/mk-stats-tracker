#!/usr/bin/env python3
"""
Find a direct in-progress/pause flag by phase-differential scanning.

Method:
- Scan a focused static region in MEM1.
- Capture 4 phases while staying in-race:
  RUN-1  -> PAUSE-1  -> RUN-2  -> PAUSE-2
- Keep byte addresses where value is:
  - stable within each phase window
  - same across RUN windows
  - same across PAUSE windows
  - different between RUN vs PAUSE

This targets a state flag instead of timer-delta heuristics.

Run:
  sudo mk/bin/python3 -m lab.race.race_pause_flag_finder
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

# Focus scan near known stable MKW globals.
SCAN_START = 0x80900000
SCAN_END = 0x80A00000

POLL_INTERVAL = 0.25
PHASE_SECONDS = 2.5
TOP_N = 25
WATCH_INTERVAL = 2.0


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def in_race():
    try:
        block = read_u32(STABLE_PTR)
        if not in_mem1(block):
            return False
        pos = read_u8(block + POSITION_OFFSET)
        return 1 <= pos <= 12
    except Exception:
        return False


def wait_in_race(timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if in_race():
            return True
        time.sleep(0.2)
    return False


def capture_phase(name):
    print("\n[%s] Capture %.1fs..." % (name, PHASE_SECONDS))
    samples = []
    end_t = time.time() + PHASE_SECONDS
    size = SCAN_END - SCAN_START

    while time.time() < end_t:
        if not in_race():
            print("  in_race gate failed during %s." % name)
            return None
        try:
            s = bytes(read_bytes(SCAN_START, size))
        except Exception as exc:
            print("  read failed: %s" % exc)
            return None
        samples.append(s)
        time.sleep(POLL_INTERVAL)

    print("  captured %d samples" % len(samples))
    return samples


def phase_stable_value(samples, off):
    v = samples[0][off]
    for s in samples[1:]:
        if s[off] != v:
            return None
    return v


def score_candidate(run_v, pause_v):
    # Prefer clean boolean-ish toggles first.
    bool_like = ((run_v, pause_v) in ((0, 1), (1, 0)))
    near_bool = ((run_v <= 3 and pause_v <= 3) and run_v != pause_v)
    return (2 if bool_like else 0) + (1 if near_bool else 0)


def find_candidates(run1, pause1, run2, pause2):
    size = SCAN_END - SCAN_START
    out = []

    for off in range(size):
        r1 = phase_stable_value(run1, off)
        if r1 is None:
            continue
        p1 = phase_stable_value(pause1, off)
        if p1 is None:
            continue
        r2 = phase_stable_value(run2, off)
        if r2 is None:
            continue
        p2 = phase_stable_value(pause2, off)
        if p2 is None:
            continue

        if r1 != r2:
            continue
        if p1 != p2:
            continue
        if r1 == p1:
            continue

        addr = SCAN_START + off
        out.append(
            {
                "addr": addr,
                "run_v": r1,
                "pause_v": p1,
                "score": score_candidate(r1, p1),
            }
        )

    out.sort(key=lambda c: (-c["score"], c["addr"]))
    return out


def print_candidates(cands):
    print("\nCandidates where value is stable and RUN!=PAUSE across both cycles:")
    if not cands:
        print("  none found")
        return
    print(" idx   addr         run_v pause_v score expr")
    for i, c in enumerate(cands[:TOP_N]):
        expr = "u8(0x%x)" % c["addr"]
        print(
            " %3d  0x%08x   %3d   %3d    %d   %s"
            % (i, c["addr"], c["run_v"], c["pause_v"], c["score"], expr)
        )


def choose_candidate(cands):
    if not cands:
        return None
    print("\nChoose index for live watch (Enter=0, q=quit):")
    raw = input("> ").strip().lower()
    if raw == "q":
        return None
    if raw == "":
        return cands[0]
    try:
        i = int(raw, 0)
        if 0 <= i < min(TOP_N, len(cands)):
            return cands[i]
    except Exception:
        pass
    print("Invalid index.")
    return None


def watch_candidate(c):
    addr = c["addr"]
    run_v = c["run_v"]
    pause_v = c["pause_v"]
    print("\nWatching %s (run_v=%d pause_v=%d). Ctrl+C to stop." % (hex(addr), run_v, pause_v))

    last_print = 0.0
    while True:
        now = time.time()
        if (now - last_print) < WATCH_INTERVAL:
            time.sleep(0.1)
            continue
        ts = time.strftime("%H:%M:%S")

        race = in_race()
        if not race:
            print("[%s] in_race=False in_progress=False value=-" % ts)
            last_print = now
            continue

        try:
            v = read_u8(addr)
        except Exception:
            print("[%s] in_race=True in_progress=? value=?" % ts)
            last_print = now
            continue

        in_progress = (v == run_v)
        paused_like = (v == pause_v)
        print(
            "[%s] in_race=True in_progress=%s value=%d run_v=%d pause_v=%d paused_like=%s"
            % (ts, in_progress, v, run_v, pause_v, paused_like)
        )
        last_print = now


def main():
    dme.hook()
    print("Race Pause Flag Finder (experimental)")
    print("Scan range: %s - %s (%d bytes)" % (hex(SCAN_START), hex(SCAN_END), (SCAN_END - SCAN_START)))
    print("Flow: RUN-1 -> PAUSE-1 -> RUN-2 -> PAUSE-2")
    print("\nStep 0: load into a race.")
    print("Press Enter when ready.")
    input()

    if not wait_in_race():
        print("Could not confirm in-race.")
        return

    print("\nStep 1/4: unpaused and driving.")
    print("Press Enter to capture RUN-1.")
    input()
    run1 = capture_phase("RUN-1")
    if run1 is None:
        return

    print("\nStep 2/4: pause and keep menu open.")
    print("Press Enter to capture PAUSE-1.")
    input()
    pause1 = capture_phase("PAUSE-1")
    if pause1 is None:
        return

    print("\nStep 3/4: unpause and drive again.")
    print("Press Enter to capture RUN-2.")
    input()
    run2 = capture_phase("RUN-2")
    if run2 is None:
        return

    print("\nStep 4/4: pause again.")
    print("Press Enter to capture PAUSE-2.")
    input()
    pause2 = capture_phase("PAUSE-2")
    if pause2 is None:
        return

    cands = find_candidates(run1, pause1, run2, pause2)
    print_candidates(cands)

    chosen = choose_candidate(cands)
    if chosen is None:
        return
    try:
        watch_candidate(chosen)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
