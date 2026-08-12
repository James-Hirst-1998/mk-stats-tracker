# mk-stats-tracker

Race stats for Mario Kart Wii, read live out of a running Dolphin.

It exists to settle arguments. Your friend did not get hit by four blue shells.
He got hit by one blue shell, two bananas he drove into himself, and a Pokey.
Now there is a log.

## What it reads

All twelve racers, every frame, straight from the game's own memory:

- **Position, lap and progress** — ranking racers by progress reproduces the
  game's own reported position 98–99% of the time
- **Lap splits and finish times** — from the game's timers, not a stopwatch
- **Time spent in first place**, and time spent in every other position
- **The race clock** — the game's own, which starts at GO and not at the intro
  camera, so a time in the log is the time on screen
- **Items** — what each racer picked up and when they used it, by name, and
  what the roulette has already secretly decided about 3.5 seconds early
- **Being hit, and what hit you** — spin-out, knockback, launched, crushed,
  POW'd, and which of those came from an item versus a track hazard
- **Which item, by name, and who threw it** — green shell, red shell, fake
  item box, banana, bob-omb, blue shell. 165 of 182 hits across the recordings
- **Who everyone is** — character and vehicle by name, and which racers are
  CPUs. No more "slot 7"
- **Course**

Everything above is validated across seven recorded races from seven separate
Dolphin launches. What is *not* solved yet is listed in
[docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) under "Open".

## Setup

Mario Kart Wii **PAL / RMCP01** in Dolphin, on macOS or Linux. Other regions
have different addresses and will not work without redoing the discovery.

```bash
python3 -m venv mk && mk/bin/pip install dolphin-memory-engine numpy zstandard
```

## Watch a race

Start Dolphin, load the game, then:

```bash
sudo mk/bin/python3 -m tools.live
```

`sudo` is needed to read another process's memory. The view redraws 20 times a
second and prints an event log underneath:

```
   0:00.000  race start - Mushroom Gorge
   0:00.000  you are Luigi on the Mach Bike, starting 12th
   0:00.000  11 CPU: Yoshi, Baby Luigi, Rosalina, Dry Bowser, Toadette, ...
   0:36.917  you were hit - Banana (Baby Luigi's) (spin-out)
   1:05.467  Yoshi was hit - Red Shell (yours) (knockback)
   1:09.717  Toad was hit - Blue Shell (Bowser Jr.'s) (launched)
   1:17.117  Daisy was hit - Green Shell (Rosalina's) (knockback)
   1:33.433  Bowser was hit - Fake Item Box (Dry Bones') (knockback)
```

A hit line appears once the item that caused it has been destroyed, which is
0.33s later for a shell and 1–2s for an explosion. That is the delay that
makes naming it possible, so the line is held back rather than printed twice.

## Keep a race

Every race that starts is written to `races/` as an event log when it ends —
the whole event stream plus the final standings, **about 54 kB**. Nothing else
is needed to say what happened afterwards:

```bash
mk/bin/python3 -m tools.report            # the most recent race
mk/bin/python3 -m tools.report --list     # everything stored
mk/bin/python3 -m tools.report peach      # by name
```

That rebuilds the whole thing from the file — every event, lap splits, who hit
whom with what, items used, hits taken by type, time spent in each position.
No Dolphin, no recording, no sudo.

The format, and how to add a new kind of event to it, is in
[docs/RACE_LOG.md](docs/RACE_LOG.md). It is deliberately dull: JSON Lines, one
event per line, ids rather than names so fixing a name fixes every stored race.

## Record a race to work on offline

Live debugging against a moving race is miserable. Record once, then test
every idea against the recording as many times as you like.

```bash
sudo mk/bin/python3 -m tools.probe     # once per machine
sudo mk/bin/python3 -m tools.record    # ctrl-c to stop
mk/bin/python3 -m tools.verify         # must say USABLE
```

A recording is a 20 Hz page-delta capture of the console's memory, roughly
1–2 GB per race. They live in `recordings/` and are git-ignored. Keep the
screen recording of the same race next to it — the video is often the only
ground truth you have.

Then replay the real reader over it:

```bash
mk/bin/python3 -m tools.replay_live mushroom-gorge
mk/bin/python3 -m tools.replay_live mushroom-gorge --save   # and store it
```

## Layout

| path | what it is |
|---|---|
| `mkw/` | the library: addresses, names, live reads, event stream |
| `mkw/capture/` | the recorder and the offline replay harness |
| `tools/` | things you run: `live`, `report`, `record`, `verify`, `probe`, `replay_live` |
| `races/` | saved races, one small file each. Git-ignored by default |
| `analysis/` | offline checks that produce the evidence for what's claimed |
| `lab/` | exploration, including everything that failed. Kept on purpose |
| `docs/` | how it works, the memory map, and the full experiment log |

## How any of this was found

Short version: record a whole race, then test hypotheses offline against the
recording instead of against a live game. The long version, including the
several approaches that did not work, is in [docs/METHOD.md](docs/METHOD.md)
and [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md). The addresses themselves are
in [docs/MEMORY_MAP.md](docs/MEMORY_MAP.md).

One thing worth knowing up front: the recordings contain the game's
executable, because that lives in the same memory being captured. The hardest
result here — knowing what hit you — came from disassembling the game's own
code out of a recording, after three rounds of searching memory for it had
failed.

## Contributing

Read [CLAUDE.md](CLAUDE.md) first. It is short and mostly about writing things
down.
