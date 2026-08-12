# Confirmed Track Paths (Final)

Date: `2026-03-01`  
Setup: Mario Kart Wii PAL on local Dolphin (macOS)

## Summary

- Track is read as MKW **course code** (slot code), not cup-order index.
- The following 10 `(slot, offset)` paths were validated together.
- `track_pool_checker.py` showed full consensus (`10/10`) through menu/race transitions and back into race.

Canonical source path promoted to `source/read_race.py`:
- `course_code = u8(u32(0x809c27f8) + 0x13)`

## Validated Candidate Pool (10)

1. `slot=0x809c2338, off=0x13`
2. `slot=0x809c27f0, off=0x77`
3. `slot=0x809c27f8, off=0x13`  <- promoted to source
4. `slot=0x809c27f8, off=0x1ff`
5. `slot=0x809c2850, off=0x3f`
6. `slot=0x809c2850, off=0x22b`
7. `slot=0x809c28a8, off=0x3b`
8. `slot=0x809c5278, off=0x177`
9. `slot=0x809c5280, off=0x18f`
10. `slot=0x809c5be8, off=0x137`

## Notes

- During non-race windows, pointer bases can temporarily read out-of-range (`base=0x0`); this is expected.
- Once race state stabilizes, all 10 paths converged to the same valid course code.
- Example observed consensus: `0x0b` (`Maple Treeway`) across all 10 candidates.
