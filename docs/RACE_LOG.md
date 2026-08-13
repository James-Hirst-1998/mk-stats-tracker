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
| `use` | `slot`, `item` | they threw it |
| `lost` | `slot`, `item`, `damage` | it was knocked out of their hands — see below |
| `swap` | `slot`, `from`, `to` | held item changed without passing through empty |
| `hit` | `slot`, `damage`, `object`, `by`, `place`, `for`, `guess`, `caught`, `from`, `passed` | see below |
| `cloud` | `slot` | won a Thunder Cloud. It is never held, so it appears nowhere in the item fields — the object in the world is the only thing that says who has one |
| `lap` | `slot`, `lap`, `split`, `total` | crossed the line; `split` is that lap, `total` is cumulative, both from the game's own timers |
| `finish` | `slot`, `position`, `time` | finished the race |
| `pos` | `slot`, `from`, `to` | position change |

Any event can also carry `after: true`, meaning it happened to a racer who had
already crossed the line. It is kept because it happened, and left out of every
total in a report, because a red shell catching somebody parked past the finish
is not part of their race.

`hit`: `damage` is the game's damage type (`DAMAGE_TYPES` in `mkw/names.py`).
`object` is the world-item type that caused it, or `null` when there was no
object — a Star, Mega or Bullet does its damage with the kart itself, and
Lightning and the POW have nothing in the world at all. `by` is the slots
behind it, normally one. `place` is the position the victim was in. `for` is
how long the hit lasted, from the damage field's own start and end, and is
absent if the end was never seen.

`guess: true` marks anything not read directly. Naming the object that hit you
is a read — the pool loses an entry and the object says who owned it. The three
that are not are all marked: a launched hit whose object was missed and is
placed by the timing of a Blue Shell or Bob-omb use; a ram, where the racer
credited is the only one who both used a Star, Mega or Bullet recently and was
within 0.004 laps at the time; and Lightning or a POW, where the racer credited
is the one who used it and is not among the victims.

`caught: true` means the racer was standing in somebody else's explosion rather
than being the one it went for. A Blue Shell aims at whoever is leading, so in
a multi-victim blast the leader is the hit and the rest were caught in it; a
Bob-omb aims at nobody, so everybody it catches was caught in it.

`from` and `passed` appear on a Thunder Cloud strike: `from` is the racer who
won the cloud, read off the object, and `passed: true` means it went off on
somebody else. Who passed it to whom is **not** recorded — the object's owner
never changes as the cloud moves, and no byte in it tracks the carrier.

`lost`: the held item going empty means one of two things, and calling both of
them `use` made a Lightning read as eleven racers all choosing to use what they
were holding in the same frame. Which one it was is a state, not a coincidence
in time: the damage field is still reading the hit at the moment the item goes.
Being flipped, flattened or shocked takes it (`DROPS_ITEM` in `mkw/names.py`);
a spin-out or a knockback does not. 25 of 442 clearings across the seven
recordings are losses. `damage` says what took it.

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
- **Throws inside a triple, and this is on purpose.** A triple's held id clears
  a median 0.05s after it settles — one sample — because the three objects go
  into orbit straight away, so the `use` is the moment they start spinning
  round the kart and not a throw. Getting the three throws would mean watching
  each object's state change in the pools. Decided not worth it: when you got
  them and when they deployed is what the log is for. Same for a Golden
  Mushroom, which is one `use` covering every boost it gave.
- **Which race of a VS sequence this is.** Not decoded. The settings block is
  stored raw so it can be worked out from stored races later; until then a
  session is however many races were played between starting the tool and
  stopping it, which needs nothing read from memory at all.
