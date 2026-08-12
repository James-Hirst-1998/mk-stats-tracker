#!/usr/bin/env python3
"""Offline: read the damage type the game itself records, for all twelve racers.

This is a read, not an inference. The path came from the game's own code rather
than from scoring bytes against video:

  0x805808c4  li r4,10 / bl 0x80590d5c      shock passes damage type 10
  0x805811a8  li r4,11 / bl 0x80590d5c      POW passes 11
  0x80590d5c  proxy->[0]->[0x2c], vtable at +0x0c, slot 3
  0x805675dc  the handler: `stw r22,28(r21)` stores the type at sub+0x1C,
              `li r3,-1; stw r3,28(r21)` clears it to -1,
              `mulli r3,r22,12` indexes a per-type table at 0x808B4C58.

Reaching the sub-object re-uses the item array, which is already proven:

  director = u32(0x809C3618); items = u32(director + 0x14)
  kartItem = items + slot * 0x248        (KartItem is a KartObjectProxy)
  accessor = u32(kartItem)
  sub      = u32(accessor + 0x2C)

Confirmed against the twelve objects found independently by their secondary
vtable 0x808B5008: 12/12 addresses agree.

Run (no sudo):
  mk/bin/python3 -m analysis.validate_damage [recording-substring]
"""

import glob
import os
import sys

import numpy as np

from mkw.capture import format as capfmt
from mkw.capture.session import Session, RECORDINGS

ITEM_DIRECTOR = 0x809C3618
OFF_ITEM_ARRAY = 0x14
ITEM_STRIDE = 0x248
OFF_ACCESSOR_SUB = 0x2C
OFF_DAMAGE = 0x1C          # s32, -1 when undamaged
OFF_LAST_ENTRY = 0xC0      # -> DAMAGE_TABLE + type * 12, kept after it clears
OFF_PRIORITY = 0xF6        # s16, table[type] + 8
DAMAGE_TABLE = 0x808B4C58
N_PLAYERS = 12
NONE = -1

# Values 0x00-0x11, from the community's Item Damage Type Modifier codes and
# confirmed here by the three call sites the game itself uses (10, 11, 17).
DAMAGE = {
    0:  ("Spin-out", "Banana"),
    1:  ("Spin-out", "enemy (Goomba, Pokey, Crab, Shy Guy...)"),
    2:  ("Knockback", "Shell or Fake Item Box"),
    3:  ("Knockback", "Star, Cow or car"),
    4:  ("Knockback", "Chain Chomp"),
    5:  ("Knockback", "Moonview car"),
    6:  ("Knockback", "Bullet Bill"),
    7:  ("Launched", "Bob-omb or Blue Shell"),
    8:  ("Launched", "Cataquack"),
    9:  ("Fiery spin-out", "fire ring, Fire Snake or meteor"),
    10: ("Spin-out", "Lightning"),
    11: ("POW'd", "POW Block"),
    12: ("Crushed", "Thwomp"),
    13: ("Crushed", "Mega Mushroom"),
    14: ("Crushed", "Moonview truck"),
    15: ("Spin-out", "Zapper"),
    16: ("Crushed then respawn", "Thwomp Desert"),
    17: ("Spin-out", "Thunder Cloud"),
}

# Which of those can only have come from an item another racer used (or from
# your own). The rest are track hazards or contact with a boosted kart.
BY_ITEM = {0, 2, 7, 10, 11, 13, 17}


def be_u32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">u4")[0])


def be_s32(img, i):
    return int(np.frombuffer(img[i:i + 4].tobytes(), dtype=">i4")[0])


def be_s16(img, i):
    return int(np.frombuffer(img[i:i + 2].tobytes(), dtype=">i2")[0])


def read(s):
    """(t, damage[frame, racer], last[frame, racer], prio[frame, racer])"""
    n = len(s)
    t = np.full(n, np.nan)
    dmg = np.full((n, N_PLAYERS), -2, dtype=np.int32)
    last = np.full((n, N_PLAYERS), -1, dtype=np.int32)
    prio = np.zeros((n, N_PLAYERS), dtype=np.int32)
    di = capfmt.addr_to_index(ITEM_DIRECTOR, s.regions)
    for i, img in s.frames():
        if s.index[i]["position"] is None:
            continue
        d = be_u32(img, di)
        j = capfmt.addr_to_index(d + OFF_ITEM_ARRAY, s.regions)
        if j is None:
            continue
        items = be_u32(img, j)
        ok = True
        row_d, row_l, row_p = [], [], []
        for k in range(N_PLAYERS):
            ki = capfmt.addr_to_index(items + k * ITEM_STRIDE, s.regions)
            if ki is None:
                ok = False
                break
            ai = capfmt.addr_to_index(be_u32(img, ki) + OFF_ACCESSOR_SUB,
                                      s.regions)
            if ai is None:
                ok = False
                break
            si = capfmt.addr_to_index(be_u32(img, ai), s.regions)
            if si is None:
                ok = False
                break
            row_d.append(be_s32(img, si + OFF_DAMAGE))
            e = be_u32(img, si + OFF_LAST_ENTRY)
            row_l.append((e - DAMAGE_TABLE) // 12
                         if DAMAGE_TABLE <= e < DAMAGE_TABLE + 12 * 24 else -1)
            row_p.append(be_s16(img, si + OFF_PRIORITY))
        if not ok:
            continue
        t[i] = s.index[i]["mono"]
        dmg[i] = row_d
        last[i] = row_l
        prio[i] = row_p
    return t, dmg, last, prio


def spans(t, col):
    """Contiguous runs where the damage type is set, as (start, dur, type)."""
    out, st = [], None
    ok = np.nonzero(~np.isnan(t))[0]
    for n, i in enumerate(ok):
        v = int(col[i])
        if v != NONE and v >= 0 and st is None:
            st = (t[i], v)
        elif (v == NONE or v < 0) and st is not None:
            out.append((st[0], t[i] - st[0], st[1]))
            st = None
        elif st is not None and v != st[1]:
            out.append((st[0], t[i] - st[0], st[1]))
            st = (t[i], v)
    if st is not None:
        out.append((st[0], t[ok[-1]] - st[0], st[1]))
    return out


def main():
    root = RECORDINGS
    dirs = [d for d in sorted(glob.glob(os.path.join(root, "*")))
            if os.path.isfile(os.path.join(d, "meta.json"))]
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which:
        dirs = [d for d in dirs if which in d]
    if not dirs:
        print("no recording matching %r" % which)
        return

    for d in dirs:
        s = Session(d)
        t, dmg, last, prio = read(s)
        if np.all(np.isnan(t)):
            print("%s: no readable frames\n" % os.path.basename(d))
            continue
        t0 = np.nanmin(t)
        vals = sorted(set(int(v) for v in np.unique(dmg)) - {-2})
        print("=== %s" % os.path.basename(d))
        print("    values seen across all racers: %s" % vals)

        total = 0
        for k in range(N_PLAYERS):
            ev = spans(t, dmg[:, k])
            total += len(ev)
            if not ev:
                continue
            who = "you" if k == 0 else "slot %d" % k
            print("  %-7s %d" % (who, len(ev)))
            for st, dur, v in ev:
                kind, cause = DAMAGE.get(v, ("?", "?"))
                print("      %6.1fs  %-22s %-38s %.1fs%s"
                      % (st - t0, kind, cause, dur,
                         "" if v in BY_ITEM else "   (not an item)"))
        print("    %d damage events in total\n" % total)


if __name__ == "__main__":
    main()
