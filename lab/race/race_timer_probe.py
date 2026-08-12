#!/usr/bin/env python3
"""
Probe race-progress state by finding timer-like values in the local player block.

This is an experiment script (not source-trusted yet).

Flow:
1) Start in-race and drive for a few seconds.
2) Pause the game and stay paused.
3) Unpause and drive again.
4) Script ranks offsets that move while driving but freeze while paused.
5) Overlap aliases are deduped (for example 0xa0/0xa1/0xa2 variants).
6) Extra pause/run validation cycles narrow false positives further.
7) Optional refinement windows can narrow candidates further.
8) Live watch prints all remaining candidates every 2 seconds.

Run:
  sudo mk/bin/python3 -m lab.race.race_timer_probe
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

SCAN_SIZE = 0x400
WIDTHS = (2, 4)
POLL_INTERVAL = 0.2
RUN_WINDOW_SECONDS = 5.0
PAUSE_WINDOW_SECONDS = 3.0
TOP_N = 15
TARGET_FINAL_CANDIDATES = 4
DEFAULT_VALIDATE_CYCLES = 2
WATCH_PRINT_INTERVAL = 2.0


def read_bytes(addr, length):
    return dme.read_bytes(addr - BASE, length)


def read_u8(addr):
    return read_bytes(addr, 1)[0]


def read_u32(addr):
    b = read_bytes(addr, 4)
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def read_be(buf, off, width):
    if width == 2:
        return (buf[off] << 8) | buf[off + 1]
    if width == 4:
        return (buf[off] << 24) | (buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3]
    raise ValueError("unsupported width")


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def get_race_block():
    try:
        block = read_u32(STABLE_PTR)
        if not in_mem1(block):
            return None
        pos = read_u8(block + POSITION_OFFSET)
        if 1 <= pos <= 12:
            return block
        return None
    except Exception:
        return None


def wait_for_in_race(timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        block = get_race_block()
        if block is not None:
            return block
        time.sleep(0.2)
    return None


def collect_window(label, seconds):
    print("\n[%s] Collecting for %.1fs..." % (label, seconds))
    end_t = time.time() + seconds
    samples = []
    blocks = []

    while time.time() < end_t:
        block = get_race_block()
        if block is None:
            print("  race-state gate failed during %s. Restart and keep race loaded." % label)
            return None, None
        try:
            data = bytes(read_bytes(block, SCAN_SIZE))
        except Exception as exc:
            print("  read failed during %s: %s" % (label, exc))
            return None, None
        samples.append(data)
        blocks.append(block)
        time.sleep(POLL_INTERVAL)

    print("  captured %d samples" % len(samples))
    return samples, blocks


def series_stats(values):
    changed = 0
    up = 0
    down = 0
    deltas = []

    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        deltas.append(d)
        if d == 0:
            continue
        changed += 1
        if d > 0:
            up += 1
        else:
            down += 1

    return {
        "changed": changed,
        "up": up,
        "down": down,
        "deltas": deltas,
        "first": values[0],
        "last": values[-1],
    }


def candidate_sort_key(c):
    return (-c["score"], 0 if c["aligned"] else 1, -c["width"], c["off"])


def candidate_expr(c):
    return "u%d(u32(0x809c27f8)+0x%x)" % (c["width"] * 8, c["off"])


def candidate_span(c):
    return (c["off"], c["off"] + c["width"] - 1)


def spans_overlap(a, b):
    a0, a1 = candidate_span(a)
    b0, b1 = candidate_span(b)
    return not (a1 < b0 or b1 < a0)


def dedupe_overlaps(cands):
    kept = []
    for c in sorted(cands, key=candidate_sort_key):
        if any(spans_overlap(c, k) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=candidate_sort_key)
    return kept


def build_candidates(run1, pause, run2):
    total_steps_run1 = max(1, len(run1) - 1)
    total_steps_pause = max(1, len(pause) - 1)
    total_steps_run2 = max(1, len(run2) - 1)

    results = []
    for width in WIDTHS:
        max_off = SCAN_SIZE - width
        for off in range(0, max_off + 1):
            v1 = [read_be(s, off, width) for s in run1]
            vp = [read_be(s, off, width) for s in pause]
            v2 = [read_be(s, off, width) for s in run2]

            s1 = series_stats(v1)
            sp = series_stats(vp)
            s2 = series_stats(v2)

            run1_ratio = float(s1["changed"]) / total_steps_run1
            run2_ratio = float(s2["changed"]) / total_steps_run2
            pause_ratio = float(sp["changed"]) / total_steps_pause

            if run1_ratio < 0.5:
                continue
            if run2_ratio < 0.5:
                continue
            if pause_ratio > 0.1:
                continue

            if s1["up"] < s1["changed"] * 0.85:
                continue
            if s2["up"] < s2["changed"] * 0.85:
                continue
            if s1["down"] > 1 or s2["down"] > 1:
                continue

            score = (s1["changed"] + s2["changed"]) - (sp["changed"] * 4) - (s1["down"] + s2["down"]) * 6
            results.append(
                {
                    "score": score,
                    "off": off,
                    "width": width,
                    "aligned": (off % width) == 0,
                    "run1": s1,
                    "pause": sp,
                    "run2": s2,
                }
            )

    results.sort(key=candidate_sort_key)
    return results


def print_candidates(cands, title):
    print("\n%s" % title)
    if not cands:
        print("No strong timer-like candidates found with current thresholds.")
        print("Retry with clean phases: moving -> paused -> moving.")
        return

    print(" idx  width  off    aln score  run1(chg/up/down) pause(chg) run2(chg/up/down) expr")
    for idx, c in enumerate(cands[:TOP_N]):
        expr = candidate_expr(c)
        print(
            " %3d  %5d  0x%03x   %s  %5d    %2d/%2d/%2d        %2d         %2d/%2d/%2d    %s"
            % (
                idx,
                c["width"],
                c["off"],
                "Y" if c["aligned"] else "N",
                c["score"],
                c["run1"]["changed"],
                c["run1"]["up"],
                c["run1"]["down"],
                c["pause"]["changed"],
                c["run2"]["changed"],
                c["run2"]["up"],
                c["run2"]["down"],
                expr,
            )
        )


def candidate_window_stats(cand, samples):
    vals = [read_be(s, cand["off"], cand["width"]) for s in samples]
    return series_stats(vals)


def passes_refinement(cand, samples, mode):
    st = candidate_window_stats(cand, samples)
    total_steps = max(1, len(samples) - 1)
    change_ratio = float(st["changed"]) / total_steps
    if mode == "run":
        if change_ratio < 0.5:
            return False
        if st["up"] < st["changed"] * 0.85:
            return False
        if st["down"] > 1:
            return False
        return True
    # freeze mode
    return change_ratio <= 0.1


def ask_validation_cycles():
    print("\nExtra validation: pause/play cycles to reduce false positives.")
    print("Enter cycle count (pause then run per cycle). Enter=%d, 0=skip." % DEFAULT_VALIDATE_CYCLES)
    raw = input("> ").strip()
    if raw == "":
        return DEFAULT_VALIDATE_CYCLES
    try:
        n = int(raw, 0)
        if n < 0:
            n = 0
        if n > 6:
            n = 6
        return n
    except Exception:
        print("Invalid input. Using %d." % DEFAULT_VALIDATE_CYCLES)
        return DEFAULT_VALIDATE_CYCLES


def validate_with_pause_run_cycles(cands, cycles):
    if not cands or cycles <= 0:
        return cands

    for i in range(1, cycles + 1):
        print("\nValidation cycle %d/%d: PAUSE phase." % (i, cycles))
        print("Pause and keep the menu open, then press Enter.")
        input()
        pause_samples, _ = collect_window("VALIDATE-%d-PAUSE" % i, PAUSE_WINDOW_SECONDS)
        if pause_samples is None:
            print("Pause capture failed; keeping current candidates.")
            continue

        before = len(cands)
        filtered = [c for c in cands if passes_refinement(c, pause_samples, "freeze")]
        filtered = dedupe_overlaps(filtered)
        if filtered:
            cands = filtered
            print("Pause filter kept %d -> %d candidates." % (before, len(cands)))
            print_candidates(cands, "Candidates After Pause Filter")
        else:
            print("Pause filter removed all candidates; keeping previous set.")

        print("\nValidation cycle %d/%d: RUN phase." % (i, cycles))
        print("Unpause and drive normally, then press Enter.")
        input()
        run_samples, _ = collect_window("VALIDATE-%d-RUN" % i, RUN_WINDOW_SECONDS)
        if run_samples is None:
            print("Run capture failed; keeping current candidates.")
            continue

        before = len(cands)
        filtered = [c for c in cands if passes_refinement(c, run_samples, "run")]
        filtered = dedupe_overlaps(filtered)
        if filtered:
            cands = filtered
            print("Run filter kept %d -> %d candidates." % (before, len(cands)))
            print_candidates(cands, "Candidates After Run Filter")
        else:
            print("Run filter removed all candidates; keeping previous set.")

    return cands


def refine_candidates(cands):
    if not cands:
        return cands

    while len(cands) > TARGET_FINAL_CANDIDATES:
        print(
            "\nRefine: %d candidates remain (target <= %d)."
            % (len(cands), TARGET_FINAL_CANDIDATES)
        )
        print("Choose extra test: [r] driving window, [p] paused window, [d] done")
        raw = input("> ").strip().lower()
        if raw == "":
            raw = "r"
        if raw in ("d", "q"):
            break
        if raw not in ("r", "p"):
            print("Invalid choice.")
            continue

        if raw == "r":
            print("\nDrive normally.")
            print("Press Enter when ready to capture RUN refinement window.")
            input()
            samples, _ = collect_window("REFINE-RUN", RUN_WINDOW_SECONDS)
            mode = "run"
        else:
            print("\nPause and keep pause menu open.")
            print("Press Enter when ready to capture PAUSE refinement window.")
            input()
            samples, _ = collect_window("REFINE-PAUSE", PAUSE_WINDOW_SECONDS)
            mode = "freeze"

        if samples is None:
            print("Refinement capture failed; keeping current candidates.")
            continue

        before = len(cands)
        filtered = [c for c in cands if passes_refinement(c, samples, mode)]
        filtered = dedupe_overlaps(filtered)

        if not filtered:
            print("Refinement removed all candidates; keeping previous set.")
            continue

        cands = filtered
        print("Refinement kept %d -> %d candidates." % (before, len(cands)))
        print_candidates(cands, "Candidates After Refinement")

    return cands


def watch_candidates(cands):
    if not cands:
        return

    cands = list(cands)
    histories = {i: [] for i in range(len(cands))}
    prev_values = {}
    last_print = 0.0

    print("\nLive watch (all remaining candidates). Ctrl+C to stop.")
    print("Printing every %.1fs." % WATCH_PRINT_INTERVAL)
    for i, c in enumerate(cands):
        print("  #%d %s" % (i, candidate_expr(c)))

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        block = get_race_block()

        snapshot = []
        any_running = False
        if block is None:
            for i in histories:
                histories[i] = []
            prev_values = {}
        else:
            for i, c in enumerate(cands):
                try:
                    buf = bytes(read_bytes(block + c["off"], c["width"]))
                    value = read_be(buf, 0, c["width"])
                except Exception:
                    histories[i] = []
                    prev_values.pop(i, None)
                    snapshot.append((i, c, None, None, False, False))
                    continue

                delta = 0 if i not in prev_values else (value - prev_values[i])
                prev_values[i] = value

                h = histories[i]
                h.append(value)
                if len(h) > 8:
                    histories[i] = h[-8:]
                    h = histories[i]

                running = len(h) >= 4 and len(set(h[-4:])) > 1
                if running:
                    any_running = True
                snapshot.append((i, c, value, delta, running, True))

        if (now - last_print) >= WATCH_PRINT_INTERVAL:
            if block is None:
                print("[%s] in_race=False race_in_progress=False" % ts)
            else:
                parts = []
                for i, c, value, delta, running, ok in snapshot:
                    if not ok:
                        parts.append("#%d off=0x%x w=%d v=? d=? run=?" % (i, c["off"], c["width"] * 8))
                    else:
                        parts.append(
                            "#%d off=0x%x w=%d v=%d d=%+d run=%s"
                            % (i, c["off"], c["width"] * 8, value, delta, running)
                        )
                print(
                    "[%s] in_race=True race_in_progress=%s  %s"
                    % (ts, any_running, " | ".join(parts))
                )
            last_print = now

        time.sleep(POLL_INTERVAL)


def main():
    dme.hook()
    print("Race Timer Probe (experimental)")
    print("Target: find a value that advances during race and freezes when paused.")
    print("\nStep 1/3: Load into a VS race and keep driving.")
    print("Press Enter when ready.")
    input()

    block = wait_for_in_race()
    if block is None:
        print("Could not confirm stable in-race state.")
        return
    print("In-race detected. player block=%s" % hex(block))

    run1, blocks1 = collect_window("RUN-1 (driving)", RUN_WINDOW_SECONDS)
    if run1 is None:
        return

    print("\nStep 2/3: PAUSE the race and keep the pause menu open.")
    print("Press Enter once paused.")
    input()
    pause, blocks_pause = collect_window("PAUSE", PAUSE_WINDOW_SECONDS)
    if pause is None:
        return

    print("\nStep 3/3: UNPAUSE and drive again.")
    print("Press Enter once unpaused.")
    input()
    run2, blocks2 = collect_window("RUN-2 (driving)", RUN_WINDOW_SECONDS)
    if run2 is None:
        return

    all_blocks = blocks1 + blocks_pause + blocks2
    unique_blocks = {b for b in all_blocks}
    if len(unique_blocks) != 1:
        print("\nWarning: player block changed during sampling (%d unique blocks)." % len(unique_blocks))
        print("Results may be noisy; rerun with cleaner race-state transitions.")

    raw_cands = build_candidates(run1, pause, run2)
    cands = dedupe_overlaps(raw_cands)
    print(
        "\nCandidate count: raw=%d, after-overlap-dedupe=%d"
        % (len(raw_cands), len(cands))
    )
    print_candidates(
        cands,
        "Top Timer-Like Candidates (moves in run windows, freezes while paused)",
    )

    cycles = ask_validation_cycles()
    cands = validate_with_pause_run_cycles(cands, cycles)

    cands = refine_candidates(cands)
    if not cands:
        print("\nNo candidates left after filtering.")
        return

    try:
        watch_candidates(cands)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
