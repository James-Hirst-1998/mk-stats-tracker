# Item Tracking Attempts Log

Use this as memory. Keep entries short.

## Known Failed / Unstable Approaches
- Block+offset from player block: works in one race, breaks next race due to allocation changes.
- Single/short pointer-chain from position block to held-item byte: not stable; do not retry same chain strategy.
- Scanning MEM1 for pointers to per-race item addresses: no stable pointer path found.
- "Item used" transition matching (old->new): misses held/cart states (for example triple bananas while held), so not reliable.
- Neighbour-pointer scans near `0x809c27f8`: not proven stable across races/restarts.

## Entry Format (append for each new attempt)
- `YYYY-MM-DD`: method -> result -> keep/stop.
- `2026-03-01`: track-slot scanner (`testers/tracks/track_finder.py`) using rescan+intersect across track changes -> created, pending on-device validation across races/restarts -> keep.
- `2026-03-01`: adjusted track scanner to prefer byte-width matching + unaligned scans + width-1 fallback on zero-intersection -> intended to reduce false elimination -> keep.
- `2026-03-01`: removed argparse; switched track finder to one interactive run that tests widths 1/2/4 together and can enter watch mode inline -> keep.
- `2026-03-01`: replaced track finder with stable `(pointer_slot, offset)` discovery across samples (not absolute-address intersection) + in-script validation phase -> keep.
- `2026-03-01`: hardened pointer-slot tracker: stable-race polling gate + non-destructive filtering (do not zero-out on one bad sample) + optional safe intersection for large sets -> keep.
- `2026-03-01`: added `testers/tracks/track_path_tester.py` to validate discovered path `u8(u32(0x809bec9c)+0x70)` against user-picked next tracks with PASS/FAIL output -> keep.
- `2026-03-01`: hardened `track_path_tester.py` to ignore out-of-range transition values (e.g. 252) and require stable in-race polls before accepting next-track read -> keep.
- `2026-03-01`: switched track scripts to MKW course-slot codes (not cup-order indices), rebuilt finder with non-destructive `(slot,offset)` filtering, and made path tester generic (user-provided slot+offset) -> keep.
- `2026-03-01`: added `testers/tracks/track_pool_checker.py` to poll all 10 discovered candidate paths and report consensus/mismatches across race events -> keep.
- `2026-03-01`: validated 10/10 track path consensus across transitions (including Maple Treeway), documented pool in `testers/tracks/CONFIRMED_TRACK_PATHS.md`, promoted `u8(u32(0x809c27f8)+0x13)` into `source/read_race.py`, removed untrusted item read from source -> final.
