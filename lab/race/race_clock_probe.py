#!/usr/bin/env python3
"""
Find a race-clock style signal (changes while race is unpaused even if stationary,
and freezes while paused).

This avoids movement-only fields (for example position/velocity-like values).

Flow:
1) MOVING: drive normally.
2) STILL-1: keep kart stationary (unpaused, in-race).
3) PAUSE: open pause menu.
4) STILL-2: unpause and stay stationary again.
5) Script ranks candidates and can live-watch all remaining candidates.

Run:
  sudo mk/bin/python3 -m lab.race.race_clock_probe
"""

import time

import dolphin_memory_engine as dme


BASE = 0x80000000
STABLE_PTR = 0x809C27F8
POSITION_OFFSET = 0x3E

SCAN_SIZE = 0x400
WIDTHS = (1, 2, 4)
POLL_INTERVAL = 0.2
PRINT_INTERVAL = 2.0
WINDOW_SECONDS = 4.0
TOP_N = 15
TARGET_FINAL = 5


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
            print("  race-state gate failed during %s." % label)
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
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        if d == 0:
            continue
        changed += 1
        if d > 0:
            up += 1
        else:
            down += 1
    return {"changed": changed, "up": up, "down": down, "first": values[0], "last": values[-1]}


def dominant_sign(stats):
    if stats["up"] == stats["down"]:
        return 0
    return 1 if stats["up"] > stats["down"] else -1


def candidate_sort_key(c):
    return (-c["score"], 0 if c["aligned"] else 1, -c["width"], c["off"])


def candidate_expr(c):
    return "u%d(u32(0x809c27f8)+0x%x)" % (c["width"] * 8, c["off"])


def spans_overlap(a, b):
    a0, a1 = a["off"], a["off"] + a["width"] - 1
    b0, b1 = b["off"], b["off"] + b["width"] - 1
    return not (a1 < b0 or b1 < a0)


def dedupe_overlaps(cands):
    kept = []
    for c in sorted(cands, key=candidate_sort_key):
        if any(spans_overlap(c, k) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=candidate_sort_key)
    return kept


def build_candidates(moving, still1, pause, still2):
    total_m = max(1, len(moving) - 1)
    total_s1 = max(1, len(still1) - 1)
    total_p = max(1, len(pause) - 1)
    total_s2 = max(1, len(still2) - 1)

    out = []
    for width in WIDTHS:
        for off in range(0, SCAN_SIZE - width + 1):
            vm = [read_be(s, off, width) for s in moving]
            vs1 = [read_be(s, off, width) for s in still1]
            vp = [read_be(s, off, width) for s in pause]
            vs2 = [read_be(s, off, width) for s in still2]

            sm = series_stats(vm)
            s1 = series_stats(vs1)
            sp = series_stats(vp)
            s2 = series_stats(vs2)

            rm = float(sm["changed"]) / total_m
            rs1 = float(s1["changed"]) / total_s1
            rp = float(sp["changed"]) / total_p
            rs2 = float(s2["changed"]) / total_s2

            # Keep values that keep ticking even while stationary,
            # but freeze in pause.
            if rs1 < 0.35 or rs2 < 0.35:
                continue
            if rp > 0.10:
                continue
            if rm < 0.35:
                continue

            d1 = dominant_sign(s1)
            d2 = dominant_sign(s2)
            if d1 == 0 or d2 == 0 or d1 != d2:
                continue

            score = (s1["changed"] + s2["changed"]) * 5 + sm["changed"] * 2 - sp["changed"] * 10
            out.append(
                {
                    "score": score,
                    "off": off,
                    "width": width,
                    "aligned": (off % width) == 0,
                    "moving": sm,
                    "still1": s1,
                    "pause": sp,
                    "still2": s2,
                }
            )

    out.sort(key=candidate_sort_key)
    return out


def print_candidates(cands, title):
    print("\n%s" % title)
    if not cands:
        print("No candidates matched. Retry with cleaner still/pause windows.")
        return

    print(" idx  width off    aln score  moving(chg) still1(chg) pause(chg) still2(chg) expr")
    for i, c in enumerate(cands[:TOP_N]):
        print(
            " %3d  %5d 0x%03x   %s  %5d      %2d          %2d         %2d          %2d      %s"
            % (
                i,
                c["width"],
                c["off"],
                "Y" if c["aligned"] else "N",
                c["score"],
                c["moving"]["changed"],
                c["still1"]["changed"],
                c["pause"]["changed"],
                c["still2"]["changed"],
                candidate_expr(c),
            )
        )


def refine(cands):
    if not cands:
        return cands
    while len(cands) > TARGET_FINAL:
        print("\nRefine: %d candidates remain (target <= %d)." % (len(cands), TARGET_FINAL))
        print("Choose: [s] stationary unpaused window, [p] pause window, [d] done")
        raw = input("> ").strip().lower()
        if raw in ("", "s"):
            print("Stay unpaused and keep kart still, then Enter.")
            input()
            samples, _ = collect_window("REFINE-STILL", WINDOW_SECONDS)
            mode = "still"
        elif raw == "p":
            print("Pause and keep menu open, then Enter.")
            input()
            samples, _ = collect_window("REFINE-PAUSE", WINDOW_SECONDS)
            mode = "pause"
        elif raw in ("d", "q"):
            break
        else:
            print("Invalid choice.")
            continue

        if samples is None:
            print("Capture failed; keeping current set.")
            continue

        total = max(1, len(samples) - 1)
        before = len(cands)
        filtered = []
        for c in cands:
            vals = [read_be(s, c["off"], c["width"]) for s in samples]
            st = series_stats(vals)
            ratio = float(st["changed"]) / total
            if mode == "still":
                if ratio >= 0.35:
                    filtered.append(c)
            else:
                if ratio <= 0.10:
                    filtered.append(c)

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
    prev_vals = {}
    hist = {i: [] for i in range(len(cands))}
    last_print = 0.0

    print("\nLive watch (all candidates). Ctrl+C to stop.")
    print("Printing every %.1fs." % PRINT_INTERVAL)
    for i, c in enumerate(cands):
        print("  #%d %s" % (i, candidate_expr(c)))

    while True:
        now = time.time()
        ts = time.strftime("%H:%M:%S")
        block = get_race_block()
        any_running = False
        lines = []

        if block is None:
            prev_vals = {}
            for i in hist:
                hist[i] = []
        else:
            for i, c in enumerate(cands):
                try:
                    v = read_be(bytes(read_bytes(block + c["off"], c["width"])), 0, c["width"])
                except Exception:
                    prev_vals.pop(i, None)
                    hist[i] = []
                    lines.append("#%d off=0x%x w=%d v=? d=? run=?" % (i, c["off"], c["width"] * 8))
                    continue

                d = 0 if i not in prev_vals else (v - prev_vals[i])
                prev_vals[i] = v
                h = hist[i]
                h.append(d)
                if len(h) > 6:
                    hist[i] = h[-6:]
                    h = hist[i]
                changed = sum(1 for x in h if x != 0)
                run = changed >= 2
                if run:
                    any_running = True
                lines.append("#%d off=0x%x w=%d v=%d d=%+d run=%s" % (i, c["off"], c["width"] * 8, v, d, run))

        if (now - last_print) >= PRINT_INTERVAL:
            if block is None:
                print("[%s] in_race=False race_running=False" % ts)
            else:
                print("[%s] in_race=True race_running=%s  %s" % (ts, any_running, " | ".join(lines)))
            last_print = now

        time.sleep(POLL_INTERVAL)


def main():
    dme.hook()
    print("Race Clock Probe (experimental)")
    print("Goal: value that changes while unpaused+stationary and freezes while paused.")
    print("\nStep 0: load into VS race.")
    print("Press Enter when ready.")
    input()

    block = wait_for_in_race()
    if block is None:
        print("Could not confirm in-race state.")
        return
    print("In-race detected. block=%s" % hex(block))

    print("\nStep 1/4: drive normally.")
    print("Press Enter to start MOVING capture.")
    input()
    moving, b1 = collect_window("MOVING", WINDOW_SECONDS)
    if moving is None:
        return

    print("\nStep 2/4: stay unpaused and keep kart stationary.")
    print("Press Enter to start STILL-1 capture.")
    input()
    still1, b2 = collect_window("STILL-1", WINDOW_SECONDS)
    if still1 is None:
        return

    print("\nStep 3/4: pause and keep pause menu open.")
    print("Press Enter to start PAUSE capture.")
    input()
    pause, b3 = collect_window("PAUSE", WINDOW_SECONDS)
    if pause is None:
        return

    print("\nStep 4/4: unpause, keep kart stationary again.")
    print("Press Enter to start STILL-2 capture.")
    input()
    still2, b4 = collect_window("STILL-2", WINDOW_SECONDS)
    if still2 is None:
        return

    blocks = set((b1 + b2 + b3 + b4))
    if len(blocks) != 1:
        print("Warning: player block changed during sampling (%d unique blocks)." % len(blocks))

    raw = build_candidates(moving, still1, pause, still2)
    cands = dedupe_overlaps(raw)
    print("\nCandidate count: raw=%d, deduped=%d" % (len(raw), len(cands)))
    print_candidates(cands, "Top Race-Clock Candidates")

    cands = refine(cands)
    if not cands:
        print("\nNo candidates left.")
        return

    try:
        watch_candidates(cands)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
