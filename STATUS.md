## Mario Kart Wii Stats Tracker – Progress Summary

Phase 1 – Attempt on Real Wii (Gecko / Homebrew)
• Installed Homebrew Channel.
• Enabled Gecko codes.
• Successfully tested memory patching (e.g. banana size modifier).
• Attempted to hook position function directly via Gecko ASM.
• Ran into instability and crashes due to incorrect function patching.
• Realised logging directly from the Wii would require complex ASM hooks + SD file writing.
• Determined this path was too slow and brittle for large-scale stat extraction.

⸻

Phase 2 – Move to Dolphin Emulator
• Installed Dolphin (initially stable build, then development build).
• Ripped Mario Kart Wii disc to ISO.
• Extracted and imported MKW save data into Dolphin NAND.
• Enabled cheats and debugging tools.
• Learned that modern Dolphin removed old memory socket access.
• Attempted direct Python memory access via dolphin-memory-engine.
• macOS blocked memory access initially.
• Enabled Full Disk Access + Developer Tools for Terminal.
• Resolved by running scripts via sudo from Terminal (not IDE).

⸻

Phase 3 – Programmatic Memory Scanning
• Connected to Dolphin memory via dolphin-memory-engine.
• Built automated Python scripts to:
• Scan full MEM1 region.
• Filter candidate addresses by live position changes (12 → 11 → 10 etc).
• Identified 6 dynamic addresses representing racer position fields.
• Confirmed addresses changed each race (dynamic allocation).
• Determined absolute addresses are unstable.
• Began reverse-engineering object structure.
• Started scanning for struct base pointers and page-level pointer references.
• Created narrowing scripts to:
• Track candidate position addresses
• Compare across races
• Identify potential stable pointer locations

⸻

Current State

We can:
• Automatically detect live player position during a race.
• Narrow position addresses programmatically.
• Confirm dynamic memory reallocation per race.
• Begin isolating stable pointer chains to player structs.

Next step is:
• Identify stable RaceManager / player array base pointer.
• Compute position offset inside struct.
• Build persistent logger (position, item, lap, etc).
• Pipe structured data into Python for dashboard/stats tracking.
