"""Names for the numbers the game stores: courses, items, damage types."""

# Who is driving. Confirmed on this setup at three points: the recordings whose
# notes say "birdo" have slot 0 reading 17 and the ones saying "luigi" read 7,
# and a nameplate reading "Funky Kong" in the Waluigi Stadium video sits over
# the racer whose id is 22. Ids run 0..23 and no id outside that appeared in
# 84 racer entries. Anything higher is a Mii.
CHARACTERS = {
    0: "Mario", 1: "Baby Peach", 2: "Waluigi", 3: "Bowser", 4: "Baby Daisy",
    5: "Dry Bones", 6: "Baby Mario", 7: "Luigi", 8: "Toad", 9: "Donkey Kong",
    10: "Yoshi", 11: "Wario", 12: "Baby Luigi", 13: "Toadette",
    14: "Koopa Troopa", 15: "Daisy", 16: "Peach", 17: "Birdo",
    18: "Diddy Kong", 19: "King Boo", 20: "Bowser Jr.", 21: "Dry Bowser",
    22: "Funky Kong", 23: "Rosalina",
}

# Weight class per character, 0 small, 1 medium, 2 large. Not decoration: MKW
# only lets a racer pick a vehicle of their own class, so this is what checks
# the two tables against each other. See `analysis/validate_racers.py`.
CHARACTER_CLASS = {
    0: 1, 1: 0, 2: 2, 3: 2, 4: 0, 5: 0, 6: 0, 7: 1, 8: 0, 9: 2, 10: 1, 11: 2,
    12: 0, 13: 0, 14: 0, 15: 1, 16: 1, 17: 1, 18: 1, 19: 2, 20: 1, 21: 2,
    22: 2, 23: 2,
}

# What they are driving. Only 22 = Mach Bike is confirmed here, from the
# recording notes; the rest are the public ordering, which the class check
# supports - ids 0-17 are karts and 18-35 bikes, and within each the class is
# `id % 3`, which agrees with the character's class on all 84 entries. These
# are the common English names; some PAL menu names differ.
VEHICLES = {
    0: "Standard Kart S", 1: "Standard Kart M", 2: "Standard Kart L",
    3: "Baby Booster", 4: "Classic Dragster", 5: "Offroader",
    6: "Mini Beast", 7: "Wild Wing", 8: "Flame Flyer",
    9: "Cheep Charger", 10: "Super Blooper", 11: "Piranha Prowler",
    12: "Tiny Titan", 13: "Daytripper", 14: "Jetsetter",
    15: "Blue Falcon", 16: "Sprinter", 17: "Honeycoupe",
    18: "Standard Bike S", 19: "Standard Bike M", 20: "Standard Bike L",
    21: "Bullet Bike", 22: "Mach Bike", 23: "Flame Runner",
    24: "Bit Bike", 25: "Sugarscoot", 26: "Wario Bike",
    27: "Quacker", 28: "Zip Zip", 29: "Shooting Star",
    30: "Magikruiser", 31: "Sneakster", 32: "Spear",
    33: "Jet Bubble", 34: "Dolphin Dasher", 35: "Phantom",
}

# The value at RaceConfigPlayer +0x10. The collision code treats 0 and 2 alike
# and 1 differently, which is what says 1 is the CPU.
PLAYER_TYPES = {0: "human", 1: "CPU", 2: "human (online)", 3: "none",
                4: "ghost"}

COURSES = {
    0x00: "Mario Circuit", 0x01: "Moo Moo Meadows", 0x02: "Mushroom Gorge",
    0x03: "Grumble Volcano", 0x04: "Toad's Factory", 0x05: "Coconut Mall",
    0x06: "DK Summit", 0x07: "Wario's Gold Mine", 0x08: "Luigi Circuit",
    0x09: "Daisy Circuit", 0x0A: "Moonview Highway", 0x0B: "Maple Treeway",
    0x0C: "Bowser's Castle", 0x0D: "Rainbow Road", 0x0E: "Dry Dry Ruins",
    0x0F: "Koopa Cape", 0x10: "GCN Peach Beach", 0x11: "GCN Mario Circuit",
    0x12: "GCN Waluigi Stadium", 0x13: "GCN DK Mountain",
    0x14: "DS Yoshi Falls", 0x15: "DS Desert Hills", 0x16: "DS Peach Gardens",
    0x17: "DS Delfino Square", 0x18: "SNES Mario Circuit 3",
    0x19: "SNES Ghost Valley 2", 0x1A: "N64 Mario Raceway",
    0x1B: "N64 Sherbet Land", 0x1C: "N64 Bowser's Castle",
    0x1D: "N64 DK's Jungle Parkway", 0x1E: "GBA Bowser Castle 3",
    0x1F: "GBA Shy Guy Beach",
}


def course_name(code):
    """A course's name, or something honest when there is not one.

    `read_course` returns None while the course pointer is being rebuilt
    between races - which is exactly when a second race is starting, so this
    is a normal value and not an error. Formatting it as course 0 would name
    it Mario Circuit, which is a lie; the callers that used to do their own
    `"course 0x%02x" % code` either did that or crashed on it.
    """
    if code is None:
        return "(course unknown)"
    return COURSES.get(code, "course 0x%02x" % code)

# What a racer is holding. 20 means nothing.
ITEMS = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
    4: "Mushroom", 5: "Triple Mushrooms", 6: "Bob-omb", 7: "Blue Shell",
    8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
    12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
    16: "Triple Green Shells", 17: "Triple Red Shells", 18: "Triple Bananas",
    19: "(unused)", 20: "-",
}

# What the game did to you, and what can have caused it. Values 0x00-0x11.
# The ids come from the community's Item Damage Type Modifier codes; 10, 11
# and 17 are confirmed directly by the constants the PAL code passes.
DAMAGE_TYPES = {
    0:  ("Spin-out", "Banana"),
    1:  ("Spin-out", "an enemy"),
    2:  ("Knockback", "Shell or Fake Item Box"),
    3:  ("Knockback", "a boosted kart, cow or car"),
    4:  ("Knockback", "Chain Chomp"),
    5:  ("Knockback", "a Moonview car"),
    6:  ("Knockback", "Bullet Bill"),
    7:  ("Launched", "Bob-omb or Blue Shell"),
    8:  ("Launched", "a Cataquack"),
    9:  ("Fiery spin-out", "fire"),
    10: ("Spin-out", "Lightning"),
    11: ("POW'd", "POW Block"),
    12: ("Crushed", "a Thwomp"),
    13: ("Crushed", "Mega Mushroom"),
    14: ("Crushed", "a Moonview truck"),
    15: ("Spin-out", "a Zapper"),
    16: ("Crushed", "a Thwomp, then respawned"),
    17: ("Spin-out", "Thunder Cloud"),
}

# The damage types that can only have come from an item somebody used. The
# rest are track hazards or contact with a boosted kart.
BY_ITEM = {0, 2, 7, 10, 11, 13, 17}

# The damage types that knock whatever you are holding out of your hands.
# Measured, not taken from the game's rules: across all seven recordings, every
# hit where the victim was holding something was checked for the held item
# vanishing within 0.35s. Being flipped, flattened or shocked takes it, 23 of
# 25; a spin-out or a knockback does not, 2 of 20 - and both of those two
# cleared 0.35s BEFORE the hit, so they are throws that happened to be followed
# by one. `analysis/validate_item_loss.py`.
#
# The two misses are Mega Mushroom crushes where the racer kept what they were
# holding, so this is the set of hits that CAN take it, not hits that always
# do. That is the right shape for the caller: it only asks once an item has
# actually gone.
DROPS_ITEM = {3, 6, 7, 8, 10, 13, 17}

# Item objects in the world use their own enum, separate from ITEMS above.
# Learned by watching which object pool gains an entry when a known item is
# used: 66/66 for green, 65/65 red, 163/163 banana, 15/15 blue, 29/29 fake box,
# 6/6 bob-omb across seven recordings. The remaining indexes exist as pools but
# never spawned in those races.
OBJECT_TYPES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 4: "Star",
    5: "Blue Shell", 7: "Fake Item Box", 9: "Bob-omb",
    12: "Golden Mushroom",
}

# Which object types can produce a given damage type. Not guessed: each type's
# getDamageType is `u32(OBJECT_HANDLER_TABLE + type*0xC + 8)`, and disassembling
# them gives `li r3,2` for 0, 1 and 7, `neg r3,r0` (0 or -1) for 2, and
# `li r3,7` for 5 and 9 once the shell or bomb has gone off.
DAMAGE_FROM_OBJECT = {0: {2, 5, 9}, 2: {0, 1, 7}, 7: {5, 9}}

# The item ids that produce each object type, for sanity-checking a name
# against the throw that spawned it.
OBJECT_FROM_ITEM = {0: {0, 16}, 1: {1, 17}, 2: {2, 18}, 5: {7}, 7: {3}, 9: {6}}

# Points per finishing position in a VS race. The published MKW table, NOT
# read out of memory - the game's own running total has not been found. So a
# session's points are computed from the finishing positions, which are read,
# and will be right for a VS sequence and meaningless for unrelated races.
VS_POINTS = {1: 15, 2: 12, 3: 10, 4: 8, 5: 7, 6: 6,
             7: 5, 8: 4, 9: 3, 10: 2, 11: 1, 12: 0}
