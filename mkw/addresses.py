"""Every memory address and offset this project relies on, in one place.

Mario Kart Wii, PAL / RMCP01, running under Dolphin. All of it was found and
checked on that build; nothing here is guessed from another region.

How each path was established is in `docs/MEMORY_MAP.md`, and the full trail of
what was tried is in `docs/EXPERIMENTS.md`.
"""

MEM1 = (0x80000000, 0x81800000)
MEM2 = (0x90000000, 0x91800000)

N_PLAYERS = 12
LOCAL_SLOT = 0                  # the human player is always racer 0 here

# --- who each racer is: RaceConfig ----------------------------------------
# Lives in MEM2. The layout is the game's own, from 0x8052880C:
#   lbz  r4,36(r3)      how many racers
#   addi r6,r3,40       the array
#   mulli r0,r0,240     stride
#   lwz  r3,16(r3)      +0x10, compared against 0 and 2
RACE_CONFIG = 0x809BD728
OFF_RACER_COUNT = 0x24          # u8
OFF_RACERS = 0x28
RACER_STRIDE = 0xF0

OFF_VEHICLE = 0x08              # u32
OFF_CHARACTER = 0x0C            # u32
OFF_PLAYER_TYPE = 0x10          # u32, see PLAYER_TYPES in names.py
OFF_TEAM = 0xCC                 # u32, 2 when the race has no teams
OFF_GRID = 0xE1                 # u8, starting position 1..12

TYPE_LOCAL, TYPE_CPU, TYPE_ONLINE = 0, 1, 2
MAX_CHARACTER = 0x30            # ids above the 24 named ones are Miis
MAX_VEHICLE = 0x24

# --- course ---------------------------------------------------------------
COURSE_PTR = 0x809C27F8
COURSE_OFFSET = 0x13

# --- racers: RaceinfoPlayer, one per racer --------------------------------
PLAYER_PTR = 0x809BD730
PLAYER_DELTA = 0x120
PLAYER_STRIDE = 0xC4

OFF_COMPLETION = 0x0C           # float, lap + fraction of the current lap
OFF_LAP_FRACTION = 0x18         # float, 0..1 through the current lap
OFF_POSITION = 0x20             # u8, 1..12
OFF_CURRENT_LAP = 0x24          # u16, becomes maxLap + 1 on finishing
OFF_MAX_LAP = 0x26              # u8
OFF_FRAME_COUNTER = 0x2C        # u32 at 60Hz, freezes when that racer finishes
OFF_FRAMES_IN_FIRST = 0x30      # u32 at 60Hz, time spent leading
OFF_LAP_TIMES = 0x3C            # Timer*, one per lap, cumulative
OFF_FINISH_TIME = 0x40          # Timer*

# --- Timer ----------------------------------------------------------------
TIMER_SIZE = 0x0C
TIMER_MINUTES = 0x04            # u16
TIMER_SECONDS = 0x06            # u8
TIMER_MILLIS = 0x08             # u16
TIMER_SET = 0x0A                # non-zero once the game has filled it in

# --- items: KartItem, one per racer ---------------------------------------
ITEM_DIRECTOR = 0x809C3618
OFF_ITEM_ARRAY = 0x14
ITEM_STRIDE = 0x248

OFF_ROULETTE = 0x077            # u8, what the spin has already chosen
OFF_HELD = 0x08F                # u8, 20 = nothing
EMPTY_ITEM = 20

# --- damage ---------------------------------------------------------------
# KartItem is a KartObjectProxy, so it can be walked to the object the
# collision code writes a hit into.
OFF_ACCESSOR_SUB = 0x2C         # accessor -> damage sub-object
OFF_DAMAGE = 0x1C               # s32, -1 when the racer is not hit
OFF_LAST_DAMAGE_ENTRY = 0xC0    # -> DAMAGE_TABLE + type*12, kept after the hit
OFF_DAMAGE_PRIORITY = 0xF6      # s16, a stronger hit overrides a weaker one
DAMAGE_TABLE = 0x808B4C58
NO_DAMAGE = -1

# --- items in the world ---------------------------------------------------
# The shells, bananas and boxes actually lying on the track or in flight. One
# pool per item type, in a table hanging off ItemDirector. A pool slot keeps
# its address for the whole race, so an address is a stable identity.
HEAP = (0x80900000, 0x81800000)

OFF_POOL_TABLE = 0x48           # ItemDirector + this is pool entry 0
POOL_STRIDE = 0x24
OFF_POOL_TYPE = 0x00            # u32, equal to the entry's own index
OFF_POOL_ARRAY = 0x04           # -> array of pointers to that type's objects
OFF_POOL_CAP = 0x08             # u32
OFF_POOL_LIVE = 0x10            # u32, live objects sit at array[0..live-1]
N_OBJECT_TYPES = 15
MAX_POOL = 64                   # sanity bound on a capacity

OFF_OBJECT_TYPE = 0x04          # u32, same value as its pool's index
OFF_OBJECT_OWNER = 0x6C         # u8, the racer who fired it
OBJECT_HANDLER_TABLE = 0x808B5468   # stride 0xC, getDamageType at +8

# --- code, for anyone wanting to re-derive the above ----------------------
# These are read-only landmarks in the executable, not data.
CODE_DAMAGE_THUNK = 0x80590D5C      # (proxy, damageType) -> virtual dispatch
CODE_DAMAGE_HANDLER = 0x805675DC    # stores the type at sub+0x1C
CODE_GET_PLAYER_IDX = 0x80590A5C    # proxy -> [0] -> [0] -> u8 at +0x10
CODE_COLLISION_LOOP = 0x805725E8    # consumes the per-kart candidate buffer
CODE_ITEM_QUERY = 0x80799CAC        # fills that buffer, ItemDirector + 0x264
