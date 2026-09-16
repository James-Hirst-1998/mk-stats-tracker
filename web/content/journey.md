# How it was built

It started as a way to settle arguments on race night. This is how it went,
including everything that did not work, which is most of it.

## February: a real Wii and some Gecko codes

The first plan was to do it on the console: Homebrew Channel, Gecko codes,
patching memory. Hooking into the game's code on real hardware was too
brittle, so it moved to Dolphin, where a Python script can read the game's
memory from the outside with `dolphin-memory-engine`.

## February: scan, change, scan again

The classic method. Start a race, scan memory for your position, change
position, scan again, keep whatever changed the right way.

- **Position worked.** A pointer at `0x809c27f8` leads to your position, and
  it held across races and restarts.
- **Items did not.** `item_finder.py` narrowed memory down to one byte while
  you swapped items. Next race, the byte had moved. The script's own comment
  from the time: *"if item shows ? next race, re-run item_finder"*.

## March: the course, wohooo

The first thing found properly was which course you are on: ten candidate
addresses, checked against each other across course changes, all ten agreeing.
The commit message was *"race track tracking working wohooo"*.

Then a few days on "is the race running or paused?" Timers, deltas,
hysteresis, debounce. None of it told a pause from a race reliably. It still
has not been solved.

## Then nothing for five months

Last commit in March. Next one in August.

## August: stop playing detective live

The problem with a live race is that every idea costs a whole race, and the
race is never the same twice.

So it flipped round. Instead of hunting for one number while playing,
**record the whole race**:

- a screen recording, for what actually happened
- the Wii's entire memory, 20 times a second, with `tools/record.py`

```bash
sudo mk/bin/python3 -m tools.record
```

That is 1–2 GB a race. `tools/verify.py` checks the recording rebuilds
properly, and it has to say **USABLE** before anything found in it counts.
After that, an idea costs seconds instead of a race, and gets tested against
the same race as many times as it takes.

## 11–12 August: everything at once

With a recording to test against, things that had not worked in weeks took
minutes:

- **Every racer's position**, not only yours: 48 million bytes of memory down
  to 5 candidates.
- **Race progress**, found by its shape: a number that only goes up, from about
  1 on the grid to 4 at the finish.
- **Lap times**, from the game's own clock.
- **Items**, eventually.
- **What hit you, and who threw it.**

### The item box lies

The obvious way to find your item: watch the item box on the video and find
the byte that matches. It failed again and again, because the box appears the
moment you hit an item box and spins through random items for about 3.5
seconds. For that whole spin you are holding nothing.

The byte that did match the box was the roulette. It knows what you are
getting 3.5 seconds before you do. That is in the log now too.

### Reading the game's own code

Three rounds of searching memory for "you got hit" failed. One idea, *a kart
that stops moving has been hit*, looked right for days. It was wrong both ways:
walls, grass and tight corners look like hits, and some hits do not.

What worked: the recording holds the game's code, because the code lives in
the same memory. Community Gecko codes point at the spots that set the damage
type, so those could be disassembled straight out of a recording with a small
PowerPC disassembler (`lab/ppc.py`). Spin-out, knockback, launched, crushed —
all read from the game itself. Watching which shell vanished at the moment you
got hit gives who threw it.

## Race logs, not recordings

A 2 GB recording is for finding things. Knowing what happened in a race takes
about 119 kB: one line per event. `tools/track.py` writes those live, for a
whole VS night, with no recording.

First real night: three races, 1,728 events, 249 kB.

## The dashboard, over and over

- **14 August:** first dashboard, in Python.
- **17 August:** rebuilt in TypeScript, React and Tailwind.
- **3–4 September:** the charts were "massive", so it became a grid of small
  widgets that open up, with a page per race. Courses whose lap traced badly
  got drawn by hand. A scavenger stat that could only ever find one event got
  deleted.

## September: this site

The stats page runs anywhere now. Load a night's folder and everything is
worked out in your browser.

## What it taught me

> **Record once, test forever.** One recording beats a hundred live attempts.

> **Something that moves with the thing is not the thing.** The item box, the
> stalled kart, the byte that followed the roulette.

> **Write the failures down.** Every attempt is logged, wrong ones included,
> so nothing gets tried twice.
