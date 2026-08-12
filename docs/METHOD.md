# Method

How anything gets found here, and why it is done this way.

## The problem with a live game

A race lasts two minutes, you cannot pause it usefully, and any hypothesis you
want to test needs the exact same two minutes again. Testing against a live
game means one attempt per race, and the race is never the same twice.

## Record once, test forever

`tools/record` captures the console's memory at 20 Hz for a whole session:

- MEM1 `0x80000000–0x81800000` and MEM2 `0x90000000–0x91800000`
- 4 KiB pages, only the pages that changed since the last frame
- a keyframe every 400 frames so any point can be reconstructed
- zstd level 1, which keeps up with the write rate

That is roughly 1–2 GB per race, and about 730 changed pages per frame in
practice. Every frame also records a few live "anchor" reads.

`tools/verify` then reconstructs sampled frames offline and checks they
reproduce those anchors. **A recording is not evidence until verify says
USABLE.** Anything else means the capture was lossy and every result derived
from it is suspect.

After that, an idea costs seconds instead of a race.

## Ground truth

Memory alone tells you a byte changed, not what it means. Three sources of
truth, in rough order of reliability:

1. **The game's own code.** MEM1 holds the executable, and the recorder
   captures MEM1, so every recording is also a copy of the code. Disassembling
   it gives certainty rather than correlation. This is how the damage field
   was found, and it should be the first resort, not the last.
2. **A different memory field.** If two fields derived independently agree —
   a Lightning marking eleven racers in the same frame somebody uses item 8 —
   that is strong, and needs no video at all.
3. **Video and voice.** Screen recordings sit alongside each capture. The
   audio track is usable as labels: game audio sits at RMS ~227 while spoken
   narration peaks at 3500–10500, so speech bursts fall out of an envelope
   threshold without any transcription.

Ground truth from video is the weakest of the three, because aligning video to
memory is itself a guess. Two claims in this repo were wrong for exactly that
reason, and both are logged in `EXPERIMENTS.md`.

## Searching for a field

When the code route isn't available, search by **shape** before value:

- A race progress field is a float that increases monotonically and lands in a
  known range. That found it, where value-matching had not.
- A countdown timer rests at zero, jumps, then decrements once per frame.
- A per-racer field has **twelve** instances. But twelve alone proves nothing:
  in one race, 37 different classes had exactly twelve live instances. A
  twelve-count is a filter, not an answer.

Then score candidates against labels rather than requiring exact agreement.
One misaligned frame kills a strict intersection, and the labels are the least
reliable part of the whole setup.

## What goes wrong

Recorded here because each of these cost real time:

- **Picking the wrong target.** "Item box drawn on the HUD" seemed like a
  clean label for "has an item". It isn't — the box is drawn all through the
  roulette spin. That one wrong assumption invalidated every item search built
  on it.
- **Trusting a fitted constant.** The item array was reached by an offset that
  had been tuned until it worked. It did work, on every recording. It was
  still 0x73 away from the array the game itself uses.
- **Believing a plausible signal.** A racer who stops advancing has probably
  been hit — except when they hit a wall, or drove onto grass, or the track
  turned. Stall detection looked convincing for days and was wrong in both
  directions.

The pattern is the same each time: a signal that correlates with the thing is
not the thing.
