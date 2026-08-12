#!/usr/bin/env python3
"""
Shared capture format + memory helpers for the session recorder/replayer.

Recording layout (one directory per session):
  meta.json    - regions, page size, rate, start times, notes
  frames.zst   - concatenated compressed frame blobs
  index.jsonl  - one JSON line per frame (timestamps, blob offset, anchors)

Frame blob (before zstd), big-endian:
  u32            n_pages
  u32[n_pages]   page indices (into the flat region-concatenated image)
  bytes          n_pages * PAGE_SIZE of page data

A frame is either a keyframe (every page) or a page-delta (only pages that
changed since the previous frame). Reconstruction walks forward from the most
recent keyframe.
"""

import struct

import numpy as np
import dolphin_memory_engine as dme

BASE = 0x80000000
PAGE_SIZE = 0x1000

# Flat image = these regions concatenated, in order.
# MEM2 default window matches the range lab/items/item_finder.py scans and
# covers the MEM2 item candidates in attempts/LOCATIONS.txt (0x904xxxxx).
REGIONS = [
    (0x80000000, 0x01800000),  # MEM1, 24 MiB
    (0x90000000, 0x01800000),  # MEM2 low window, 24 MiB
]

# Known-good reads from mkw/reader.py, stored per frame in index.jsonl so
# a recording can be sanity-checked and synced to video without decompressing.
ANCHOR_PTR = 0x809C27F8
ANCHOR_POSITION_OFF = 0x3E
ANCHOR_COURSE_OFF = 0x13

# Set by resolve_addr_mode(); dme builds differ on whether read_bytes() wants a
# console address or a flat offset from 0x80000000.
_ADDR_OFFSET = None


def resolve_addr_mode():
    """Detect whether dme.read_bytes wants console addresses or flat offsets.

    Probes the known-good pointer at ANCHOR_PTR both ways and keeps whichever
    yields a plausible MEM1 pointer. Returns the mode as a string.
    """
    global _ADDR_OFFSET
    for mode, sub in (("offset", BASE), ("console", 0)):
        try:
            raw = dme.read_bytes(ANCHOR_PTR - sub, 4)
        except Exception:
            continue
        value = struct.unpack(">I", bytes(raw))[0]
        if in_mem1(value):
            _ADDR_OFFSET = sub
            return mode
    raise RuntimeError(
        "Could not read %s in either address mode. Is a race loaded?" % hex(ANCHOR_PTR)
    )


def read_bytes(addr, size):
    if _ADDR_OFFSET is None:
        raise RuntimeError("call resolve_addr_mode() after dme.hook()")
    return dme.read_bytes(addr - _ADDR_OFFSET, size)


def u8(addr):
    return read_bytes(addr, 1)[0]


def u32(addr):
    return struct.unpack(">I", bytes(read_bytes(addr, 4)))[0]


def in_mem1(p):
    return 0x80000000 <= p < 0x81800000


def image_size(regions=REGIONS):
    return sum(size for _, size in regions)


def page_count(regions=REGIONS):
    return image_size(regions) // PAGE_SIZE


def addr_to_index(addr, regions=REGIONS):
    """Map a console address to its byte index in the flat image, or None."""
    base = 0
    for start, size in regions:
        if start <= addr < start + size:
            return base + (addr - start)
        base += size
    return None


def index_to_addr(idx, regions=REGIONS):
    """Inverse of addr_to_index."""
    base = 0
    for start, size in regions:
        if base <= idx < base + size:
            return start + (idx - base)
        base += size
    return None


def read_image(regions=REGIONS, chunk=0x100000, out=None):
    """Read every region into one flat uint8 array.

    Unreadable chunks are left as zeros rather than aborting the frame, so a
    transient failure costs one region slice instead of the whole session.
    """
    if out is None:
        out = np.zeros(image_size(regions), dtype=np.uint8)
    pos = 0
    failed = 0
    for start, size in regions:
        end = start + size
        addr = start
        while addr < end:
            n = min(chunk, end - addr)
            try:
                buf = read_bytes(addr, n)
                out[pos:pos + n] = np.frombuffer(buf, dtype=np.uint8, count=n)
            except Exception:
                out[pos:pos + n] = 0
                failed += 1
            pos += n
            addr += n
    return out, failed


def read_anchors():
    """Known-good live values, for per-frame sanity checks and video sync."""
    try:
        block = u32(ANCHOR_PTR)
    except Exception:
        return {"block": None, "position": None, "course": None}
    if not in_mem1(block):
        return {"block": block, "position": None, "course": None}
    try:
        return {
            "block": block,
            "position": u8(block + ANCHOR_POSITION_OFF),
            "course": u8(block + ANCHOR_COURSE_OFF),
        }
    except Exception:
        return {"block": block, "position": None, "course": None}


def changed_pages(cur, prev, n_pages):
    """Indices of PAGE_SIZE pages that differ between two flat images."""
    a = cur.reshape(n_pages, PAGE_SIZE)
    b = prev.reshape(n_pages, PAGE_SIZE)
    return np.nonzero((a != b).any(axis=1))[0].astype(np.uint32)


def encode_frame(image, pages, n_pages):
    """Pack the given page indices out of image into a frame blob."""
    if pages is None:
        pages = np.arange(n_pages, dtype=np.uint32)
    view = image.reshape(n_pages, PAGE_SIZE)
    header = struct.pack(">I", len(pages)) + pages.astype(">u4").tobytes()
    return header + view[pages].tobytes()


def decode_frame_into(blob, image, n_pages):
    """Apply a decompressed frame blob onto a flat image in place."""
    count = struct.unpack(">I", blob[:4])[0]
    idx_end = 4 + count * 4
    pages = np.frombuffer(blob[4:idx_end], dtype=">u4").astype(np.int64)
    data = np.frombuffer(blob[idx_end:], dtype=np.uint8)
    if data.size != count * PAGE_SIZE:
        raise ValueError("frame blob truncated: %d pages, %d bytes" % (count, data.size))
    image.reshape(n_pages, PAGE_SIZE)[pages] = data.reshape(count, PAGE_SIZE)
    return count
