# Race logs

What a race is kept as once it has been read out of memory.

A recording is a gigabyte because it is every byte of the console's memory,
twenty times a second. Almost none of that matters once the events have been
pulled out of it. A race log keeps the events, plus every racer's progress five
times a second — **78–155 kB per race, 119 kB on average**, measured over the
seven recordings — and everything `tools/report.py` prints, including a
second-by-second replay, is rebuilt from that file alone.

That is about **8,800 races per gigabyte**. Storage is not a constraint on this
and is not worth optimising; a thousand races is 116 MB.

Written by `mkw/racelog.py`. Read back by the same.

## Sessions

Races are recorded in sittings. `tools/track.py` makes one directory per run
and drops a race into it every time one ends:

```
races/20260812-2013-versus-night/
  session.json          what it was, and a line per race
  01-luigi-circuit.jsonl
  02-moo-moo-meadows.jsonl
  03-mushroom-gorge.jsonl
```

Each race is a complete object on its own — `mkw/racelog.py` reads one without
knowing sessions exist. The session is what makes "how did we all do across the
night" answerable, and `mkw/session.py` adds up MKW's VS points across it. It
checks the field is the same twelve racers in the same slots first, because
adding up unrelated races by slot number would otherwise look like a series.

The index is rewritten after every race, so ctrl-c costs at most the race in
progress. Sessions live in `races/`, or wherever `MKW_RACES` points.

## The file

One race per file, JSON Lines — appendable, greppable, diffable, and readable
without this repo. Three kinds of record:

```
{"type": "race", ...}          exactly one, first
{"t": 12.3, "type": "use", …}  the events, in race order
{"type": "progress", ...}      exactly one: where everyone was, 5 times a second
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
| `settings` | RaceConfig's settings block, raw. Only word 0 is understood — it is the course id. Kept undecoded so a question asked later can be answered from races already stored, rather than needing new ones |

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

### Progress

The one record that is not events: every racer's progress on a fixed 5 Hz grid.

```json
{"type": "progress", "hz": 5, "t0": 0.0,
 "completion": {"0": [0.9812, 0.9903, ...], "1": [...], ...}}
```

Sample `k` is the value at `t0 + k/hz`, interpolated from the frames either
side so it is the value at the time it claims rather than the first read after
it. Progress is lap plus fraction of a lap, so the difference between two
racers is the gap between them, and sorting by it is the running order.

This is what makes a race replayable — `RaceLog.progress_at(t)` and
`order_at(t)` give the state at any moment, and `tools/report.py --replay`
prints it. Measured against the full-rate reads: median error **0.00003 laps**,
99.8–100% of samples within 0.01 of a lap.

Two things to know. Position comes from the `pos` events, not from this —
ranking by progress reproduces the game's own position 98–99% of the time and
no better. And progress **wraps at the finish**: crossing the line puts it back
to the start of the last lap, 3.9994 then 3.0002, so it is not a monotonic
distance travelled. Both the sampler and the reader treat a step of more than
half a lap as the jump it is instead of interpolating through it.

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
- **Which race of a VS sequence this is.** Not decoded. The settings block is
  stored raw so it can be worked out from stored races later; until then a
  session is however many races were played between starting the tool and
  stopping it, which needs nothing read from memory at all.
