# MK Stats Tracker Agent Notes

## Goal

Build reliable Mario Kart Wii (UK/PAL on local Dolphin) stat tracking by validating memory reads on this exact setup.

## Repository Layout

- `source/`: only proven, repeatable scripts.
- `testers/`: all discovery and experiments.

## Working Rules

- Do not add code to `source/` until it is proven across multiple races/restarts.
- Keep experiments in `testers/` first, then promote when stable.
- After every new attempt, add a short entry to `testers/items/attempts/ATTEMPTS.md`.
- Do not repeat known-failed pointer-chain item approaches recorded in the attempts log.
- Prefer local iterative validation over internet memory-address guesses.
- User can run MK locally on mac laptop on dolphin emulator and pause during race if needed.
