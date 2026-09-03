# The dashboard

A local web app over stored race logs, in `web/`: TypeScript, React and
Tailwind. Nothing in it reads memory, and nothing in it is computed anywhere
else - every number comes out of `web/src/lib/stats.ts` from the session
directory, by fixed rules, so the same files always give the same dashboard.

## Running it

```
npm --prefix web install
```

```
npm --prefix web run dev
```

Then open http://localhost:8125. No sudo, and the two commands above are the
only setup; the race logs are read straight off disk by a small Vite plugin
(`web/api.mjs`) which does nothing but hand over files. `npm --prefix web run
build && npm --prefix web run serve` runs the same thing without Vite.

Live: run `tools/track.py` as usual, in another terminal.

```
sudo mk/bin/python3 -m tools.track versus-night
```

It keeps `live.json` in the session directory while a race is being recorded;
the dashboard polls every two seconds, shows "Race N of Y in progress" with
the course, and folds each race into the totals when its file lands. Stopping
the tracker removes the file. Old sessions are picked from the dropdown - same
screen, no live pill.

Four screens, all under the one hash router:

- `#/` the night: the leaderboard, then a grid of widgets - points, blue
  shells, awards, items, what everybody was hit by, who hit whom, totals - and
  the list of races.
- `#/race/<session>/<race>` one race: the per-player table, and the same grid
  for that race alone - how it unfolded, time in each position, items, every
  hit and who threw it, every blue shell, who hit whom.
- `#/replay/<session>/<race>` that race played back on its course.
- `#/tracks` every course outline. **Check** puts the layout drawing back
  behind it, with the traced centreline and the point a lap is measured from -
  this is how the tracing gets checked.

## Naming the players

**Who is who** on the dashboard is the easy way: it lists the racers the logs
found at a controller, you type a name against each, and it writes the file
below. The Characters/Names toggle has nothing to switch to until you do -
without names, both sides of it say "Birdo".

A session recorded under `sudo` before 2026-08-17 has a root-owned directory
and cannot be written to; the dashboard says so and gives you the command.
`tools/track.py` now hands its files back to whoever typed sudo.

```
sudo chown -R "$USER" races/<session>
```

The file it writes is a session directory's `players.json`, which is also the
one `tools/report.py` reads:

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

The Characters/Names toggle switches every label between the two; CPUs always
count as attackers, victims and opponents but never get a row.

## Decisions

- **The look is the older viewer's**, the Mantine app in `mario-kart-stats`:
  the same gradient behind white cards, blue as the one accent, character faces
  as identity, a leaderboard of four equal cards, tabbed charts, a slider over
  the races. Two apps over the same night should not look like two apps. The
  tokens are in `web/src/styles.css`; nothing is imported from that repo.
- **All players equal.** No "you". The tracker's `local_slot` is not used for
  display at all.
- **Widgets, not a column.** The night and a race are each a grid of small
  cards that sit beside each other, so the whole thing is on one screen, and
  each opens large (⤢) for the detail - the full-size chart, the table with
  every item or every CPU. James asked for this in place of the full-width
  charts: "widgets on the screen rather than massive ones, and a way to drill
  down". The small version is a summary; the large one leaves nothing out.
- **The slider is the whole screen, and sits above all of it.** It means
  "after race N": every card, total, award and nemesis line below it is
  computed over races 1 to N, so dragging it back is the screen the night had
  at that point. It sticks to the top of the window, because a control that
  changes everything under it should not be somewhere under it. 0 is before
  the first race, so a night can be watched from nothing.
- **Stats are computed in TypeScript, in one file.** `web/src/lib/stats.ts`
  is a port of what used to be `mkw/stats.py`, which is gone: keeping the same
  rules in two languages would have meant a correction landing in one of them.
  `mkw/report.py` is still the Python side of the same numbers for
  `tools/report.py`, and the two agree because both are ports of the same
  measurements - `web/src/lib/report.ts` says which.
- **The name tables are generated, not copied.** `tools/export_names.py`
  writes `web/src/data/names.ts` from `mkw/names.py`, so a corrected character
  id cannot be right in the recorder and wrong on the dashboard. Re-run it
  after editing `mkw/names.py`; the output is checked in.
- **"Boosts" means boost items used** (Mushrooms, Golden, Star, Bullet).
  Trick, wheelie and drift boosts are not in the logs. A later memory-map
  discovery could add them; the column would not change meaning, so it would
  be a new column.
- **Awards are fixed rules** (`web/src/lib/stats.ts::awards`): blue shell
  magnet, sniper (best landed/thrown, minimum 5 thrown), first blood (cleanly
  attributed only), the collapse (most seconds led in a race finished off the
  podium). Ties are shown as ties.
- **Player colours are fixed by player index, never by rank**, so a re-sort
  never repaints anybody. Adjacent-pair separation was measured in OKLab under
  deuteranopia, protanopia and tritanopia: the tightest pair is p1/p3 (orange
  and amber) at 8.8, which clears the floor of 8, and every series also
  carries a face and a name, so colour is never the only thing telling two
  players apart.
- **Gaps in the replay are estimates**: progress difference times the race's
  median lap time. Good enough to read, not a timing screen.
- **Which lane a kart is in on the replay means nothing.** The log says how far
  round the lap somebody is and nothing about which side of the road they were
  on, so the karts are fanned into three lanes by running order purely so that
  twelve of them at the start line are twelve things rather than one. The
  caption under the course says so.
- **Everything follows the slider**, the blue shell widget included. It used
  to be the whole night regardless, and was the one thing on the screen that
  did not move with the control above it, which read as a bug.
- **A blue shell dodge is derived** (`stats.ts::blueShells`): a Blue Shell
  `use` with no launched, un-caught, blue-object hit within 15s, credited to
  whoever was leading among the unfinished racers when it was thrown - a
  cannon, a Mushroom timed right, a Star, a Bill. The 15s comes from the
  use-to-hit gaps in the stored races, 3.2-9.6s. The pairing is measured in
  EXPERIMENTS.md under 2026-09-03.
- **Landed can exceed thrown.** A triple is one `use` in the log and each
  banana that lands is a hit, so a sniper can be "23 hits from 22 throws".
  Counting the three shots would mean watching each object in the pool, and
  RACE_LOG.md says why that was not done.

## Course outlines

`assets/tracks/source/*.png` holds a top-down layout drawing for all 32
courses, downloaded once by

```
python3 -m tools.fetch_tracks
```

from the Super Mario Wiki. They are line art rather than anything ripped: the
game's minimap is a 3D model (`map_model.brres`) rendered live, so there is no
flat image on the disc to take. The wiki has three naming conventions and two
of its filenames are wrong about which course they show, so the titles are
listed in the tool rather than searched for, and each was opened and checked.

```
python3 -m tools.build_tracks
```

writes `web/src/data/tracks.ts`, which is checked in. Two things come out of
each drawing:

- **the centreline**, `d` - the road is the region the outline encloses,
  thinned to one pixel wide, and the lap is the longest route through what is
  left. This is the line a lap fraction is measured along.
- **the road**, `outline` - every side of a road pixel that faces something
  outside the road, chained into closed loops and filled even-odd, so a course
  drawn as a ring keeps its hole. It is a path rather than a picture because
  the drawings are 100-280px and the replay draws a course at 600: the PNG
  goes to mush at that size and a path does not. Only the pieces the lap runs
  through are asked for their edges, so decoration the trace already threw
  away does not come back as road.

The tool prints what it found for each course, including `covers`: the traced
lap divided by all the road in the drawing. About 1.0 means the lap covers the
course; the tool flags anything outside 0.75-1.25. Nine courses are not drawn
as one continuous ribbon - Rainbow Road and Grumble Volcano have gaps you jump,
Mushroom Gorge has the bouncy mushrooms - and their pieces are joined end to
end.

**What this is not**: the drawing is the real course and the trace follows it,
but nothing in it says where the start line is or which way round the course
is driven. The trace begins wherever the thinning began and runs whichever way
the search walked it, so left alone a replay puts everybody on the right road
going a plausible-looking wrong way from the wrong place.

### The start line and the direction

Both are set by hand, once per course, at `#/tracks` under **Set start**:
click where the finishing line is, check the arrow is pointing the way you
drive it, hit *flip* if it is not. It saves as you go into
`assets/tracks/starts.json`, which is checked in, and every replay uses it.

The start is stored as a point on the drawing rather than as a distance along
the path, so re-running `build_tracks.py` does not move it. Courses built from
a KMP ignore the file: a course file already knows both.

Automatic detection was tried and does not work. Some drawings mark the
start with a grey band across the road - Mario Circuit and GCN Waluigi Stadium
do - but most do not, and grey pixels inside the road are mostly the
anti-aliased edge of the outline. Direction is not in the drawing at all.

### Making it exact

Every course on the disc carries a `course.kmp` with its checkpoints in it:
pairs of points across the road, in order round the lap, starting at the
finish line. That is the real geometry, the real start line and the real
direction, and `tools/kmp.py` reads it.

There is no public dump of all 32 - the physics reimplementations deliberately
ship no game assets - so this needs the disc. Once, on any machine with the
ISO:

1. Install Wiimm's SZS tools (`brew install wiimms-szs-tools`, or from
   szs.wiimm.de).

2. Extract the course files, which takes a couple of minutes and needs no
   Dolphin and no sudo:

```
wszst extract /path/to/RMCP01.iso --dest ./courses --files '+/Race/Course/*.szs'
```

3. Rebuild the outlines from them:

```
python3 -m tools.build_tracks --kmp ./courses
```

Each course then prints how far its real outline sits from the drawing, as a
percentage of the drawing's size, which is the check that the file is the
course the table says it is. `./courses` is game data and does not belong in
the repo; `web/src/data/tracks.ts` is the only output.

The reader was verified against the three vanilla course files that are
published, in `ThomasAlban/kmpeek`'s test fixtures: their checkpoint laps land
on the Coconut Mall, Dry Dry Ruins and DK Summit drawings to within 6.1%, 7.7%
and 3.2%, and on DK Summit the checkpoints are visibly the better of the two.

## Character and item art

`assets/characters/` and `assets/items/` are downloaded once by

```
python3 -m tools.fetch_assets
```

from the Super Mario Wiki (exact known filenames first, search as fallback;
see the script). Anything missing renders as an initials avatar; drop a PNG
with the slug name into the directory and it is used, and never
re-downloaded.

All 25 characters and all the items are present. Koopa Troopa, Dry Bones,
Bowser Jr. and Dry Bowser have no `<Name>MKW.png` face icon on the wiki, only
the character-select render, which is the game's model composited onto black -
`drop_black()` in the script keys that background out. It floods in from the
edges rather than keying every dark pixel, because Dry Bowser's shadows and
Dry Bones' eye sockets are as dark as the backdrop.

The set is not one visual style: five of the older files are 64px game icons
and the rest are artwork on transparency. The wiki has no complete MKW
artwork set to make them match, and it is not worth hand-picking 25 files.
