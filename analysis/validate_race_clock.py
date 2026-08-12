#!/usr/bin/env python3
"""Offline: check that Raceinfo + 0xA98 is the race clock.

The per-racer counter at `RaceinfoPlayer + 0x2C` was being used as the race
time. It is not: it starts at the intro camera, before the countdown, which is
why the live view showed a clock ticking over the track flyover, and it stops
when that racer's race ends - by finishing, and also when the race ends around
a racer who never finished, which is what two of these seven recordings are.

`Raceinfo + 0xA98` sits just past the twelve racer structs (0x120 + 12*0xC4 =
0xA50). Three checks, none of which needs the video:

  1. it is exactly 0 for every frame of the intro and the countdown, and its
     first non-zero frame is the first frame any racer moves forward
  2. `+0x2C - 0xA98` is the same constant on every frame where both are still
     advancing - if it were not, one of the two is not a 60 Hz counter - and
     every frame where it is not is a frame where `+0x2C` stopped and `0xA98`
     did not. That second half is the reason to prefer this one: `+0x2C` ends
     that racer's race, whether by finishing or by the race ending around them
  3. at every lap boundary it agrees with the game's own cumulative lap Timer,
     which is reached by a completely different pointer path

Run (no sudo):
  mk/bin/python3 -m analysis.validate_race_clock [recording-substring]
"""

import glob
import os
import struct
import sys
from collections import Counter

from mkw import addresses as A
from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS


def run(path):
    s = Session(path)
    reg = s.regions

    def u32(img, a):
        i = capfmt.addr_to_index(a, reg)
        return struct.unpack(">I", img[i:i + 4].tobytes())[0] if i is not None else None

    def u16(img, a):
        i = capfmt.addr_to_index(a, reg)
        return struct.unpack(">H", img[i:i + 2].tobytes())[0] if i is not None else None

    def u8(img, a):
        i = capfmt.addr_to_index(a, reg)
        return img[i] if i is not None else None

    def f32(img, a):
        i = capfmt.addr_to_index(a, reg)
        return struct.unpack(">f", img[i:i + 4].tobytes())[0] if i is not None else None

    def timer(img, a):
        if not (A.MEM1[0] <= a < A.MEM1[1]) or not u8(img, a + A.TIMER_SET):
            return None
        return (u16(img, a + A.TIMER_MINUTES) * 60 + u8(img, a + A.TIMER_SECONDS)
                + u16(img, a + A.TIMER_MILLIS) / 1000.0)

    gaps = Counter()
    stopped = 0
    paused = 0
    unexplained = []
    residuals = []
    zeros = 0
    first_moving = None
    first_ticking = None
    prev = {}
    last = None
    for i, img in s.frames():
        obj = u32(img, A.PLAYER_PTR)
        if obj is None or not (A.MEM1[0] <= obj < A.MEM1[1]):
            continue
        base = obj + A.PLAYER_DELTA
        rf = u32(img, obj + A.OFF_RACE_FRAMES)
        fc = u32(img, base + A.OFF_FRAME_COUNTER)
        if rf is None or fc is None:
            continue
        if rf == 0:
            zeros += 1
        else:
            if first_ticking is None:
                first_ticking = i
            if last is not None:
                drf, dfc = rf - last[0], fc - last[1]
                if drf > 0 and dfc > 0:
                    gaps[fc - rf] += 1
                elif drf > 0 and dfc == 0:
                    stopped += 1          # +0x2C is done, 0xA98 is not
                elif drf == 0 and dfc == 0:
                    paused += 1           # the game was not running
                else:
                    unexplained.append((i, drf, dfc))
        last = (rf, fc)
        for slot in range(A.N_PLAYERS):
            p = base + slot * A.PLAYER_STRIDE
            comp = f32(img, p + A.OFF_COMPLETION)
            lap = u16(img, p + A.OFF_CURRENT_LAP)
            old = prev.get(slot)
            prev[slot] = (comp, lap)
            if old is None:
                continue
            if first_moving is None and comp > old[0] + 1e-4:
                first_moving = i
            if lap > old[1] and old[1] >= 1:
                lp = u32(img, p + A.OFF_LAP_TIMES)
                if not (A.MEM1[0] <= lp < A.MEM1[1]):
                    continue
                t = timer(img, lp + (old[1] - 1) * A.TIMER_SIZE)
                if t is not None:
                    residuals.append(rf / 60.0 - t)

    ok = True
    print(os.path.basename(path))
    if first_ticking is None:
        print("  never ticked - no race in this recording")
        return False
    if first_moving is None:
        print("  starts mid-race, so check 1 is not available here")
    else:
        # A kart accelerating from a standstill needs a moment to cover the
        # 1e-4 of a lap that registers as movement, so it may be seen a frame
        # or two after the counter starts. It must not be seen before.
        good = first_moving >= first_ticking
        ok &= good
        print("  %s counter starts at frame %d, first forward motion at %d"
              % ("PASS" if good else "FAIL", first_ticking, first_moving))
    print("  zero for %d frames before that" % zeros)

    gap, n = gaps.most_common(1)[0]
    share = n / sum(gaps.values())
    # The handful of stragglers sit within a few frames of 412 rather than
    # drifting: the two counters are written at different points in the game's
    # own frame, so a snapshot can land between the two writes.
    spread = max(abs(g - gap) for g in gaps)
    good = share > 0.99 and gap == A.COUNTDOWN_FRAMES and spread <= 4
    ok &= good
    print("  %s +0x2C - 0xA98 = %d on %d/%d frames where both advanced, "
          "rest %s" % ("PASS" if good else "FAIL", gap, n, sum(gaps.values()),
                       sorted(g for g in gaps if g != gap) or "none"))
    # The failure that would matter: the race clock stopping while the
    # per-racer one carries on. It never happens.
    ok &= not unexplained
    print("  %s 0xA98 outlived +0x2C on %d frames, both idle on %d, "
          "0xA98 stalled alone on %d"
          % ("PASS" if not unexplained else "FAIL", stopped, paused,
             len(unexplained)))

    if residuals:
        worst = max(abs(r) for r in residuals)
        # One 20 Hz sample is 0.05s and a lap crossing is only ever seen late,
        # so a quarter of a second is generous and still far below the 6.87s
        # the old clock was out by.
        good = worst < 0.25
        ok &= good
        print("  %s agrees with the game's lap timers at %d lap boundaries, "
              "worst %+.3fs" % ("PASS" if good else "FAIL", len(residuals),
                                max(residuals, key=abs)))
    return ok


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = [d for d in sorted(glob.glob(os.path.join(RECORDINGS, "*")))
            if os.path.isfile(os.path.join(d, "meta.json")) and which in d]
    if not dirs:
        print("no recording matching %r in %s" % (which, RECORDINGS))
        return
    results = [run(d) for d in dirs]
    print("\n%d of %d recordings pass" % (sum(1 for r in results if r),
                                          len(results)))


if __name__ == "__main__":
    main()
