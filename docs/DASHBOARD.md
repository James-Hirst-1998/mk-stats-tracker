# The dashboard

A local web app over stored race logs. Nothing in it reads memory: every
number is computed by `mkw/stats.py` from the session directory, by fixed
rules, so the same files always give the same dashboard.

## Running it

```
python3 -m tools.dashboard
```

Then open http://localhost:8125. No sudo, no Dolphin, no dependencies beyond
the Python standard library; the frontend loads Chart.js from a CDN, which is
the one thing that needs the network. `--host 0.0.0.0` lets other machines on
the network open it.

Live: run `tools/track.py` as usual. It keeps `live.json` in the session
directory while a race is being recorded; the dashboard polls every two
seconds, shows "Race N in progress", and folds each race in when its file
lands. Stopping the tracker removes the file. Old sessions are just picked
from the dropdown - same screen, no live pill.

## Naming the players

A session directory may carry a `players.json`:

```json
{
 "planned_races": 32,
 "players": [
  {"name": "James",   "human": true},
  {"name": "Shikhar", "character": 22},
  {"name": "Wang",    "character": 2},
  {"name": "Seb",     "character": 18}
 ],
 "teams": [
  {"name": "James + Shikhar", "members": [0, 1]},
  {"name": "Wang + Seb",      "members": [2, 3]}
 ]
}
```

- `character` matches the racer playing that character - the normal case,
  since everybody keeps their character for a night.
- `"human": true` matches whichever racer the game flags as human, which
  survives a character change between races - but is only usable when exactly
  one player is human. On a real multi-human night, use characters.
- Without the file, the tracked players are simply the humans found in the
  races, named by their characters, and there are no teams.

The Characters/Names toggle on the page switches every label between the two;
CPUs always count as attackers, victims and opponents but never get a row.

## Decisions

- **All players equal.** No "you". The tracker's `local_slot` is not used for
  display at all.
- **Stats live in Python, the frontend renders.** If a number cannot be
  derived in `mkw/stats.py` the frontend cannot show it, which keeps a single
  deterministic source and keeps the JS honest.
- **"Boosts" means boost items used** (Mushrooms, Golden, Star, Bullet).
  Trick, wheelie and drift boosts are not in the logs. A later memory-map
  discovery could add them; the column would not change meaning, so it would
  be a new column.
- **Awards are fixed rules** (see `mkw/stats.py::awards`): blue shell magnet,
  sniper (best landed/thrown, minimum 5 thrown), first blood (cleanly
  attributed only), the collapse (most seconds led in a race finished off the
  podium). Ties are shown as ties.
- **The replay track outline is a placeholder.** The screen prefers
  `assets/tracks/<course-slug>.svg` - first `<path>` is the centreline, start
  line at the path start, direction of travel along the path - and falls back
  to a generic loop that says so. Real outlines are a to-do: either traced
  minimaps or, better, real kart coordinates from the recordings
  (`KartObject` position is a known decomp candidate, verifiable offline).
- **Gaps in the replay are estimates**: progress difference times the race's
  median lap time. Good enough to read, not a timing screen.

## Assets

`assets/characters/` and `assets/items/` are downloaded once by

```
python3 -m tools.fetch_assets
```

from the Super Mario Wiki (exact known filenames first, search as fallback;
see the script). Anything missing renders as an initials avatar - as of the
first run, five files could not be found (Dry Bones, Koopa Troopa, Bowser
Jr., Dry Bowser, POW Block); drop a PNG with the slug name into the
directory and it is used, and never re-downloaded.
