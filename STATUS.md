## Mario Kart Wii Stats Tracker – Progress Summary

Phase 1 – Attempt on Real Wii (Gecko / Homebrew)
• Installed Homebrew Channel, Gecko codes, memory patching.
• Abandoned: ASM hooks too brittle; moved to Dolphin.

Phase 2 – Dolphin + dolphin-memory-engine
• Python scripts read MEM1 via dolphin-memory-engine (sudo on macOS).
• Position addresses found by scanning for live value changes; confirmed they change each race.

Phase 3 – Stable pointer to position
• Used find_pointers_to.py to find what points to our position addresses.
• **Stable pointer (PAL): 0x809c27f8** → points to block containing local player data; **position at +0x3e**.
• Works across race changes and restarts.

⸻

**Current**

• **read_race.py** – Reads position (block+0x3e) and optionally item via pointer-in-block (set PTR_OFFSET / ITEM_OFFSET_IN_PTR). Just run it; no flags.
• **item_finder.py** – Narrow memory to the byte that holds current item ID (run during a race, change item to narrow).
• **find_item_chain.py** – Run during same race with item address(es); finds 2-level pointer chain from block to item so read_race can use PTR_OFFSET.
• **pick_stable_item.py** – Run during a race; prints value at candidate addresses (paste your item_finder addresses into CANDIDATES). Run again in another race; the address that shows the correct item both times is stable — set STABLE_ITEM_ADDRESS in read_race.py.
• **find_pointers_to.py** – Given addresses on stdin, finds all pointers in MEM1 that point to them.
• **dolphin-finders.py** – Manual position scan if you need to re-find position for a new setup.

**Next**

• Find **race stage** (0=intro, 1=countdown, 2=race, 3+=done): run `read_race.py --dump` at intro, during race, and at results; diff the hex to see which byte changes.
• Find **race time** in the same region or via another stable pointer.
• Gate position output on stage==2 so we only log while the race is actually running.
• Pipe into a logger/dashboard for stats.
