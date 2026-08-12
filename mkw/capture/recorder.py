#!/usr/bin/env python3
"""
Session recorder. Dumps the memory regions in capfmt.REGIONS to disk as a
page-delta stream while you play, so every later hypothesis can be tested
offline instead of during a live race.

Set RATE_HZ and CHUNK below from what tools/probe.py recommends.

Procedure per race:
  1. start your screen recording (cmd+shift+5, Record Entire Screen,
     Options -> microphone on) BEFORE starting this script
  2. run this, give the session a name, press enter
  3. play the race; say "hit" out loud when something hits you
  4. ctrl-c when the race ends, then stop the screen recording
  5. keep the .mov next to the recording directory

Run (from repo root):
  sudo mk/bin/python3 -m mkw.capture.recorder
"""

import json
import os
import time
import datetime

import numpy as np
import zstandard as zstd
import dolphin_memory_engine as dme

from mkw.capture import format as capfmt
from mkw.capture.format import PAGE_SIZE, REGIONS

# Set from tools/probe.py on this machine, 2026-08-11:
# reads ~3 GiB/s, 27.6 ms work per frame at 20 Hz, 1 late frame in 120.
RATE_HZ = 20
CHUNK = 0x4000
ZSTD_LEVEL = 1
KEYFRAME_EVERY = 400          # frames; 20s at 20 Hz
OUT_ROOT = os.environ.get("MKW_RECORDINGS", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "recordings"))
STATUS_EVERY = 1.0            # seconds


def prompt_session():
    print("Session name (e.g. race1-luigi-circuit-vs12):")
    name = input("> ").strip().replace(" ", "-")
    if not name:
        name = "session"
    print("Notes (track, player count, anything unusual). Enter to skip:")
    notes = input("> ").strip()
    return name, notes


def make_dir(name):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(OUT_ROOT, "%s-%s" % (stamp, name))
    os.makedirs(path, exist_ok=False)
    return path


def main():
    dme.hook()
    if not dme.is_hooked():
        print("Not hooked to Dolphin. Is the emulator running?")
        return
    mode = capfmt.resolve_addr_mode()

    anchors = capfmt.read_anchors()
    print("hooked, address mode = %s" % mode)
    print("anchors: block=%s position=%s course=%s" % (
        hex(anchors["block"]) if anchors["block"] else None,
        anchors["position"], anchors["course"],
    ))
    if anchors["position"] is None:
        print("WARNING: position is not readable right now. Fine if you are still")
        print("in menus, but check it goes 1-12 once the race starts.")

    name, notes = prompt_session()
    path = make_dir(name)

    print("\nStart your screen recording NOW if it is not already running.")
    print("Press enter to begin capture, ctrl-c to stop.")
    input("> ")

    n_pages = capfmt.page_count()
    cctx = zstd.ZstdCompressor(level=ZSTD_LEVEL)
    prev = np.zeros(capfmt.image_size(), dtype=np.uint8)
    cur = np.zeros(capfmt.image_size(), dtype=np.uint8)

    meta = {
        "name": name,
        "notes": notes,
        "regions": [[start, size] for start, size in REGIONS],
        "page_size": PAGE_SIZE,
        "rate_hz": RATE_HZ,
        "zstd_level": ZSTD_LEVEL,
        "keyframe_every": KEYFRAME_EVERY,
        "address_mode": mode,
        "started_wall": time.time(),
        "started_iso": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(path, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    frames_path = os.path.join(path, "frames.zst")
    index_path = os.path.join(path, "index.jsonl")

    period = 1.0 / RATE_HZ
    deadline = time.perf_counter()
    i = 0
    late = 0
    written = 0
    last_status = time.perf_counter()
    t_start = time.perf_counter()

    print("\nrecording -> %s" % path)
    try:
        with open(frames_path, "wb") as fbin, open(index_path, "w") as fidx:
            while True:
                deadline += period
                t_frame = time.perf_counter()

                cur, failed = capfmt.read_image(chunk=CHUNK, out=cur)
                a = capfmt.read_anchors()

                keyframe = (i % KEYFRAME_EVERY) == 0
                pages = None if keyframe else capfmt.changed_pages(cur, prev, n_pages)
                blob = cctx.compress(capfmt.encode_frame(cur, pages, n_pages))

                offset = fbin.tell()
                fbin.write(blob)
                written += len(blob)

                fidx.write(json.dumps({
                    "i": i,
                    "t": time.time(),
                    "mono": t_frame - t_start,
                    "kind": "key" if keyframe else "delta",
                    "off": offset,
                    "clen": len(blob),
                    "npages": n_pages if keyframe else int(len(pages)),
                    "failed_chunks": failed,
                    "block": a["block"],
                    "position": a["position"],
                    "course": a["course"],
                }) + "\n")

                prev, cur = cur, prev
                i += 1

                now = time.perf_counter()
                if now - last_status >= STATUS_EVERY:
                    fidx.flush()
                    elapsed = now - t_start
                    print(
                        "\r%6.1fs  %6d frames  %5.1f Hz  late %d  %6.2f GB  "
                        "pos=%-4s course=%-4s" % (
                            elapsed, i, i / elapsed, late, written / (1024 ** 3),
                            a["position"], a["course"]),
                        end="", flush=True,
                    )
                    last_status = now

                slack = deadline - time.perf_counter()
                if slack < 0:
                    late += 1
                    deadline = time.perf_counter()
                else:
                    time.sleep(slack)
    except KeyboardInterrupt:
        pass

    elapsed = time.perf_counter() - t_start
    meta.update({
        "frames": i,
        "late_frames": late,
        "duration_s": elapsed,
        "achieved_hz": i / elapsed if elapsed else 0,
        "bytes": written,
        "ended_wall": time.time(),
    })
    with open(os.path.join(path, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("\n\nstopped: %d frames in %.1fs (%.1f Hz), %d late, %.2f GB"
          % (i, elapsed, meta["achieved_hz"], late, written / (1024 ** 3)))
    print("saved -> %s" % path)
    print("stop your screen recording and keep the .mov with this directory.")
    print("\nverify with:  mk/bin/python3 -m mkw.capture.recorder")


if __name__ == "__main__":
    main()
