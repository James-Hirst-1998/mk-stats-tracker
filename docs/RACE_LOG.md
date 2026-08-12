# Race logs

What a race is kept as once it has been read out of memory.

A recording is a gigabyte because it is every byte of the console's memory,
twenty times a second. Almost none of that matters once the events have been
pulled out of it. A race log keeps the events and nothing else — **34–71 kB per
race, 54 kB on average**, measured over the seven recordings — and everything
`tools/report.py` prints is rebuilt from that file alone.

That is about **20,000 races per gigabyte**. Storage is not a constraint on
this and is not worth optimising; a thousand races is 53 MB.

Written by `mkw/racelog.py`. Read back by the same. Logs go in `races/`, or
wherever `MKW_RACES` points.

## The file

One race per file, JSON Lines — appendable, greppable, diffable, and readable
without this repo. Three kinds of record:

```
{"type": "race", ...}          exactly one, first
{"t": 12.3, "type": "use", …}  the events, in race order
{"type": "standings", ...}     exactly one, last
```

Times are **seconds from GO**, on the game's own race clock (`Raceinfo +
0xA98`, see [MEMORY_MAP.md](MEMORY_MAP.md)). They match the clock on screen.

Ids are stored, never names. `mkw/names.py` turns `7` into `Blue Shell`, so a
name being wrong today does not make a stored race wrong — fix the table and
every old file reads correctly.

### Header

| field | |
|---|---|
| `version` | the format. Goes up only if an existing field changes meaning |
| `recorded` | wall-clock time the file was written |
| `course` | MKW course slot code |
| `laps` | how many laps. Derived — the game has no field for it, see below |
| `begins` | race time of the first frame actually seen. Non-zero means the race was already running and nothing before it was observed |
| `local_slot` | which racer is you |
| `racers` | slot, character, vehicle, type, cpu, grid — one per racer |
| `source` | `live`, or `replay:<recording>` |
| `notes` | free text, carried over from a recording's notes |

### Events

Every event has `t` and `type`. The rest depends on the type.

| type | fields | |
|---|---|---|
| `start` | `course` | the lights went out |
| `field` | `text` | who is racing, as a line of prose |
| `box` | `slot`, `item` | hit an item box; `item` is what the roulette has already decided, about 3.5s before the player sees it |
| `hold` | `slot`, `item` | the roulette settled and they are holding it |
| `use` | `slot`, `item` | it left their hand |
| `swap` | `slot`, `from`, `to` | held item changed without passing through empty |
| `hit` | `slot`, `damage`, `object`, `by`, `guess` | see below |
| `lap` | `slot`, `lap`, `split`, `total` | crossed the line; `split` is that lap, `total` is cumulative, both from the game's own timers |
| `finish` | `slot`, `position`, `time` | finished the race |
| `pos` | `slot`, `from`, `to` | position change |

`hit`: `damage` is the game's damage type (`DAMAGE_TYPES` in `mkw/names.py`).
`object` is the world-item type that caused it, or `null` when it could not be
named; `by` is the slots that owned it, normally one. `guess: true` marks the
one inferred field in the whole format — a launched hit whose object was
missed, named from the timing of a Blue Shell or Bob-omb use instead. Anything
without it came from watching the item that hit them get destroyed.

`pos` is about two thirds of the events in a file and most of them are the
scramble off the grid. They are what "who was in front, and when" is rebuilt
from, so they are kept; `tools/report.py` hides them unless you pass `--all`.

### Standings

The last record: final state per racer, as the game reported it, so a report
does not have to replay the events to get the numbers that matter.

| field | |
|---|---|
| `position`, `finished`, `time` | `time` only when they actually crossed the line |
| `laps` | per-lap splits from the game's timers |
| `lap_reached` | highest lap they got to |
| `leading` | `+0x30` **as read**. It starts at the intro, so the racer on pole is credited about 6.87s of countdown as time in first. `mkw/report.py` takes that off; the file keeps the raw value |
| `raced` | how long their race lasted, from `+0x2C`. Their finish time, or where they had got to when the race ended around them |

## Adding an event

1. detect it in `Race.update` in `mkw/events.py` and `self.log(t, "name", …)`
2. add a line to `describe` so it renders
3. add a row to the table above

Nothing else. A reader ignores record types and fields it does not know, so
old files keep working and a file written by a newer version still reads on an
older one — it just says less.

Store ids, not names, and store what was read rather than what was concluded.
If something is inferred, put the inference in its own field so a later reader
can tell the difference, the way `hit.guess` does.

## What is not in here

- **Lap count is derived, not read.** `RaceinfoPlayer + 0x26` is the highest
  lap that racer has *reached*, not the length of the race, so `laps` is the
  maximum over the field — right whenever somebody finished, and an
  under-report if the race was abandoned first.
- **Anything before `begins`.** Start the tool mid-race and the first part is
  simply not there. The header says how much.
- **Sub-sample detail.** Everything is sampled at 20 Hz, so a position swap is
  seen up to 0.05s late and one that happens and reverses between two samples
  is not seen at all.
- **Throws inside a triple.** The held item id does not change as the second
  and third are thrown, so they are one `use`.
