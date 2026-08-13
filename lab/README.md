# lab/

Exploration. Kept deliberately, including everything that failed — knowing
which approaches are dead ends is most of the value here, and
`docs/EXPERIMENTS.md` refers back to these scripts by name.

Nothing in here is production. Some of it is actively wrong, and where that is
known it is said in the file's own docstring. Run from the repo root:

```bash
mk/bin/python3 -m lab.progress.find_progress
```

| folder | what was being chased |
|---|---|
| `items/` | finding the held item and the item array, then the world item pools. Several dead ends before the roulette/held pair came out, and a wrong "live items" array before the per-type pools |
| `ppc.py` | a small PowerPC disassembler, for reading the game's code out of a recording |
| `events/` | what the next batch of events needed measuring first: explosions with several victims, the Thunder Cloud, ram attribution, Bullet Bill rides and whether a pause is visible. Two of the five came back negative and are written up in `docs/EXPERIMENTS.md` under Open |
| `damage/` | three failed rounds of searching memory for hit state, before the answer came from the game's code instead |
| `progress/` | race progress, and the stall-based hit detection that the damage field later showed to be wrong |
| `players/` | who each racer is: finding RaceConfig in MEM2, and two wrong guesses at the array's phase before the code settled it |
| `race/` | race clock, pause flag, "is a race running" |
| `tracks/` | course code discovery |
| `timer/` | lap and finish timers before the RaceinfoPlayer layout was understood |
