# CLAUDE.md

How to work on this repo. Behaviour and process only — findings go in `docs/`.

## Aim

A Mario Kart Wii stat tracker good enough to race friends and afterwards know
exactly what happened: positions, times, item boxes, what hit who and when.
Reliable enough that nobody can argue with it.

Target is PAL / RMCP01 under Dolphin. Discovery is done offline against
recorded sessions, never by poking at a live race.

## Working rules

- **Never work on `main`.** Branch for everything, push the branch, open a PR.
- One branch at a time. Don't start a second line of work before the first
  lands.
- Nothing enters `mkw/` until it holds across recordings from **separate
  Dolphin launches**. New work starts in `lab/`, graduates to `analysis/` when
  it produces evidence, and only then into the library.
- Prefer validation on this exact setup over addresses copied off the
  internet. Public reverse-engineering work — decomps, symbol maps, Gecko
  codes — is a legitimate source of *candidates* to then verify here.
- Don't retry an approach already logged as failed unless it is materially
  different, and say what's different.
- The emulator is run by a human. Anything needing a live game is a request to
  them, so batch those and keep them short.

## Writing things down

This is the part that matters. The value of this repo is the log, not the code.

- **Every attempt gets one line in `docs/EXPERIMENTS.md`, including the ones
  that fail.** Date it. Say what was tried, what happened, and what it rules
  out. A failure that is written down is worth more than a success that isn't.
- When something is proven, add it to `docs/MEMORY_MAP.md` with *how* it was
  established, not just the address.
- Corrections are first-class. If an earlier claim turns out to be wrong, add
  a new dated line saying so and why. Don't quietly edit the old one.
- Write minimally. Short sentences, no adjectives doing work that evidence
  should be doing. If a number is claimed, the line should say how it was
  measured.

## Code style

- Minimal and plain. No cleverness that needs a comment to survive.
- Comments explain *why* and *how we know*, not what the line does.
- Every address constant lives in `mkw/addresses.py`, never inline.
- A read that can fail returns `None`. Don't guess a value.
- Nothing machine-specific: no absolute paths, no personal directories, no
  hardcoded recording names. `MKW_RECORDINGS` overrides the recordings root.

## Asking the human to do something

- One line first: what we're testing and why.
- Numbered steps. Exact commands, one per code block.
- Say explicitly what they do **not** need for that step (no video, no full
  race, no sudo).
- Say how long it takes and what output you want back.
- Never ask for a long play session against tooling that hasn't been
  smoke-tested on something smaller first.

## Talking to James

- Be brief. No preamble, no recapping what he just said, no restating the plan
  before doing it.
- Cut hedging and filler. Two sentences means two sentences.
- Don't list options he won't take. Pick one and recommend it.
- Answer the question asked before adding anything else.
- A follow-up is a question, not a signal you got it wrong.

## Keeping this file current

- When James gives direction about *how* to work or communicate, add it here
  as a rule, in his words where possible.
- Things learned about the game or the memory layout do **not** belong here.
  They go in `docs/`.
- Ask before removing or weakening an existing rule.
