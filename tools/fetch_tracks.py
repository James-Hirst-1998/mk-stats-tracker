#!/usr/bin/env python3
"""Download the course layout drawings the replay screen traces its outlines
from.

    python3 -m tools.fetch_tracks

The Super Mario Wiki has a top-down line drawing for every one of the 32
courses: black outline, transparent background, 100-280px. They are hand-drawn
rather than ripped - the game's minimap is a 3D model (`map_model.brres`)
rendered live, so there is no flat image to rip without extracting the disc.

Titles are listed here rather than searched for. The wiki has three naming
conventions and two of its filenames are wrong about which course they show,
so a search would quietly hand back the wrong track; every title below was
opened and checked against the course it claims to be.

Files land in assets/tracks/source/<slug>.png, named by the course's slug, and
are never re-downloaded. `python3 -m tools.build_tracks` turns them into the
paths the dashboard draws.
"""

import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkw.names import COURSES
from mkw.racelog import slug
from tools.fetch_assets import UA, file_url, title_exists

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets")
SOURCE = os.path.join(ASSETS, "tracks", "source")

# course id -> wiki file title. The nitro sixteen follow "<name> MKWii
# layout.png" with the punctuation dropped from the name; the retro sixteen
# follow nothing in particular.
TITLES = {
    0x00: "Mario Circuit MKWii layout.png",
    0x01: "Moo Moo Meadows MKWii layout.png",
    0x02: "Mushroom Gorge MKWii layout.png",
    0x03: "Grumble Volcano MKWii layout.png",
    0x04: "Toad Factory MKWii layout.png",
    0x05: "Coconut Mall MKWii layout.png",
    0x06: "DK Summit MKWii layout.png",
    0x07: "Wario Gold Mine MKWii layout.png",
    0x08: "Luigi Circuit MKWii layout.png",
    0x09: "Daisy Circuit MKWii layout.png",
    0x0A: "Moonview Highway MKWii layout.png",
    0x0B: "Maple Treeway MKWii layout.png",
    0x0C: "Bowser Castle MKWii layout.png",
    0x0D: "Rainbow Road MKWii layout.png",
    0x0E: "Dry Dry Ruins MKWii layout.png",
    0x0F: "Koopa Cape MKWii layout.png",
    0x10: "MKW GCN Peach Beach Map.png",
    0x11: "GCN Mario Circuit.png",
    0x12: "GCNWaluigiStadium.png",
    0x13: "MKWGCNDKMountainMinimap.png",
    0x14: "MKWDSYoshiFallsMiniMap.png",
    0x15: "MKWDSDesertHillsMiniMap.png",
    0x16: "MKWDSPeachGardensMiniMap.png",
    0x17: "MKWDSDelfinoSquareMiniMap.png",
    0x18: "WiiMariocircuit3.png",
    0x19: "WiiGhostvalley2.png",
    # The wiki files for these two are misnamed: "WiiMarioCircuit64" is N64
    # Mario Raceway, and "Sherbert" is how that page spells Sherbet.
    0x1A: "WiiMarioCircuit64.png",
    0x1B: "Wii Sherbert Land.png",
    0x1C: "N64Bowser'sCastle.png",
    0x1D: "N64 DK's Jungle Parkway.png",
    0x1E: "GBA Bowser's Castle 3.png",
    0x1F: "GBA Shy Guy Beach.png",
}


def main():
    os.makedirs(SOURCE, exist_ok=True)
    missing = []
    for code, title in sorted(TITLES.items()):
        name = COURSES[code]
        dest = os.path.join(SOURCE, slug(name) + ".png")
        if os.path.exists(dest):
            print("  %-24s already present" % name)
            continue
        try:
            url = title_exists("File:" + title) or file_url("File:" + title)
            if not url:
                raise LookupError("no such file on the wiki")
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = r.read()
        except Exception as exc:
            print("  %-24s FAILED: %s" % (name, exc))
            missing.append(name)
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print("  %-24s <- %s (%d KB)" % (name, title, len(data) // 1024))
        time.sleep(0.5)                  # polite to the wiki
    if missing:
        print("\nmissing (%d): %s" % (len(missing), ", ".join(missing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
