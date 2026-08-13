# analysis/

Offline checks that produce the evidence behind the claims in the README.
Each one runs against the recordings in `recordings/` and prints numbers, not
opinions. Run them from the repo root:

```bash
mk/bin/python3 -m analysis.validate_damage
```

| script | what it establishes |
|---|---|
| `validate_damage.py` | the damage type reads back in range for all 12 racers, every frame, every recording |
| `cross_check_damage.py` | hits agree with item uses read from a different field: 254 of 274 (93%) |
| `name_hit_items.py` | names the item behind 165 of 182 hits, and the thrower; 149 of those trace back to the throw with 0 disagreements |
| `validate_item_loss.py` | which hits knock the item out of your hands: 25 of 442 held-item clearings are losses, not throws |
| `name_blue_shell.py` | blue shell flight time is 3.9–6.8s, the fallback when an explosion's object is missed |
| `find_item_objects.py` | superseded — kept as the record of reading `ItemDirector + 0x264` as a world item list, which it is not |
| `validate_racers.py` | character and vehicle tables agree with each other on 84/84 racers, and with 17/17 labels from the recording notes |
| `validate_progress.py` | ranking by race progress reproduces reported position 98–99% |
| `validate_held_item.py` | held-item ids are clean for all 12 racers across recordings |
| `verify_raceinfo.py` | the racer struct and Timer layout in PAL |
| `validate_race_clock.py` | `Raceinfo + 0xA98` is the race clock: 0 through the countdown, exactly 412 frames behind `+0x2C`, and agrees with the game's lap timers |
| `validate_race_log.py` | a stored race log renders every event identically to the live view, and time in first rebuilt from it matches the game's own counter |
| `validate_session.py` | several recordings played back to back come out as separate races in one session, with every event kept and progress reproducing the full-rate reads |
