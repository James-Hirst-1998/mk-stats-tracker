#!/usr/bin/env python3
"""
Throughput probe. Run this once, sitting in a race, before recording anything.

Measures on this exact Mac:
  1. read speed at several chunk sizes
  2. time to read the full region set once
  3. a short live capture: achieved rate, changed pages per frame, bytes/frame

Prints the capture rate to use and the estimated size of a 3-minute race.

Run (from repo root, in a race, not paused):
  sudo mk/bin/python3 -m mkw.capture.probe
"""

import time

import numpy as np
import zstandard as zstd
import dolphin_memory_engine as dme

from mkw.capture import format as capfmt
from mkw.capture.format import PAGE_SIZE, REGIONS

CHUNK_SIZES = [0x4000, 0x40000, 0x100000, 0x400000]
PROBE_SECONDS = 6
PROBE_RATES = [10, 20, 30]
RACE_SECONDS = 180


def bench_chunk(chunk, seconds=1.0):
    """Rough read throughput in MiB/s at a given chunk size."""
    start_addr, size = REGIONS[0]
    read = 0
    addr = start_addr
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        n = min(chunk, start_addr + size - addr)
        try:
            capfmt.read_bytes(addr, n)
            read += n
        except Exception:
            pass
        addr += n
        if addr >= start_addr + size:
            addr = start_addr
    dt = time.perf_counter() - t0
    return read / dt / (1024 * 1024)


def probe_rate(rate, chunk, seconds=PROBE_SECONDS):
    """Capture at `rate` Hz for `seconds` and report what actually happened."""
    n_pages = capfmt.page_count()
    cctx = zstd.ZstdCompressor(level=1)
    prev = np.zeros(capfmt.image_size(), dtype=np.uint8)
    cur = np.zeros(capfmt.image_size(), dtype=np.uint8)

    period = 1.0 / rate
    deadline = time.perf_counter()
    frames = 0
    late = 0
    total_pages = 0
    total_bytes = 0
    read_time = 0.0
    work_time = 0.0
    end = time.perf_counter() + seconds

    while time.perf_counter() < end:
        deadline += period
        t0 = time.perf_counter()
        cur, _ = capfmt.read_image(chunk=chunk, out=cur)
        t1 = time.perf_counter()
        if frames > 0:
            pages = capfmt.changed_pages(cur, prev, n_pages)
            blob = capfmt.encode_frame(cur, pages, n_pages)
            total_pages += len(pages)
            total_bytes += len(cctx.compress(blob))
        prev, cur = cur, prev
        t2 = time.perf_counter()
        read_time += t1 - t0
        work_time += t2 - t0
        frames += 1

        slack = deadline - time.perf_counter()
        if slack < 0:
            late += 1
            deadline = time.perf_counter()
        else:
            time.sleep(slack)

    measured = max(frames - 1, 1)
    return {
        "rate": rate,
        "frames": frames,
        "late": late,
        "read_ms": read_time / frames * 1000,
        "work_ms": work_time / frames * 1000,
        "pages": total_pages / measured,
        "bytes": total_bytes / measured,
    }


def main():
    dme.hook()
    if not dme.is_hooked():
        print("Not hooked to Dolphin. Is the emulator running?")
        return
    mode = capfmt.resolve_addr_mode()
    print("hooked, address mode = %s" % mode)

    anchors = capfmt.read_anchors()
    print("anchors: block=%s position=%s course=%s" % (
        hex(anchors["block"]) if anchors["block"] else None,
        anchors["position"], anchors["course"],
    ))
    if anchors["position"] is None:
        print("WARNING: no valid position read. Sit in a running race and re-run.")

    print("\nregions: %.0f MiB total, %d pages of %d bytes" % (
        capfmt.image_size() / (1024 * 1024), capfmt.page_count(), PAGE_SIZE))

    print("\n-- read throughput by chunk size --")
    best_chunk, best_rate = CHUNK_SIZES[0], 0.0
    for chunk in CHUNK_SIZES:
        mib = bench_chunk(chunk)
        print("  chunk %8s -> %8.1f MiB/s" % (hex(chunk), mib))
        if mib > best_rate:
            best_chunk, best_rate = chunk, mib
    full_ms = capfmt.image_size() / (best_rate * 1024 * 1024) * 1000
    print("  best chunk %s; one full image read ~ %.0f ms" % (hex(best_chunk), full_ms))

    print("\n-- live capture probe (%ds each) --" % PROBE_SECONDS)
    results = []
    for rate in PROBE_RATES:
        r = probe_rate(rate, best_chunk)
        gb = r["bytes"] * rate * RACE_SECONDS / (1024 ** 3)
        r["race_gb"] = gb
        results.append(r)
        print(
            "  %2d Hz: work %5.1f ms/frame (read %5.1f), late %d/%d, "
            "%6.0f pages/frame, %7.1f KiB/frame -> %.2f GB per 3-min race"
            % (rate, r["work_ms"], r["read_ms"], r["late"], r["frames"],
               r["pages"], r["bytes"] / 1024, gb)
        )

    ok = [r for r in results if r["work_ms"] < (1000.0 / r["rate"]) * 0.8
          and r["late"] <= r["frames"] * 0.05]
    print("\n-- recommendation --")
    if ok:
        pick = max(ok, key=lambda r: r["rate"])
        print("  set RATE_HZ = %d and CHUNK = %s in recorder.py" % (pick["rate"], hex(best_chunk)))
        print("  expect ~%.2f GB per 3-minute race, ~%.2f GB for four races"
              % (pick["race_gb"], pick["race_gb"] * 4))
    else:
        print("  even %d Hz misses its deadline on this machine." % PROBE_RATES[0])
        print("  drop the MEM2 window in capfmt.REGIONS and re-run.")


if __name__ == "__main__":
    main()
