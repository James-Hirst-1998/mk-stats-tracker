"""Names for the numbers the game stores: courses, items, damage types."""

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

# Item objects in the world use their own enum, separate from ITEMS above.
# Learned by watching which object appears when a known item is used, and
# cross-checked against the handler each index resolves to.
OBJECT_TYPES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 5: "Blue Shell",
    7: "Fake Item Box", 9: "Bob-omb",
}
