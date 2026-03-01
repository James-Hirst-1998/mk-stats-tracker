## Mario Kart Wii Stats Tracker – Status

### Goal
Track Mario Kart Wii stats reliably on local Dolphin (UK/PAL), with discovery done iteratively on this setup.

### Current Working Source
- `source/read_race.py`:
  - Stable pointer `0x809c27f8` -> player block.
  - Local player position at `block + 0x3e`.
  - Stable course code at `block + 0x13` (MKW course slot code).
  - Item reading removed from source; item path remains untrusted.

### Experimental Work
- `testers/items/item_finder.py`: usable for in-race item discovery.
- All unproven or failed item/pointer scripts are in `testers/items/attempts/`.
- Attempt history lives in `testers/items/attempts/ATTEMPTS.md`.
- Track discovery/validation scripts and final confirmed path pool are in `testers/tracks/`.

### Rule
- Nothing moves into `source/` until it is stable across multiple races/restarts.
