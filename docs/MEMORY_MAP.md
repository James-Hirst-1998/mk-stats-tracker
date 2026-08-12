# Memory map

Mario Kart Wii, **PAL / RMCP01**, under Dolphin. Every entry below was checked
on that build against recordings from separate Dolphin launches. The constants
themselves live in [`mkw/addresses.py`](../mkw/addresses.py).

Other regions will have different addresses. Nothing here is transferable
without redoing the work.

## Course

```
course = u8(u32(0x809C27F8) + 0x13)
```

MKW course slot code, not cup order. Ten independent `(pointer, offset)` pairs
were validated together and agreed 10/10 through menu and race transitions;
this one was promoted. See `lab/tracks/`.

## Racers — `RaceinfoPlayer`

```
base = u32(0x809BD730) + 0x120,  12 entries of 0xC4
```

| offset | type | field |
|---|---|---|
| `+0x0C` | f32 | race completion — lap number plus fraction of the current lap |
| `+0x18` | f32 | lap completion, 0..1 |
| `+0x20` | u8 | position, 1..12 |
| `+0x24` | u16 | current lap; becomes `maxLap + 1` on finishing |
| `+0x26` | u8 | laps in this race |
| `+0x2C` | u32 | frame counter at 60 Hz; freezes when that racer finishes |
| `+0x30` | u32 | frames spent in first place |
| `+0x3C` | `Timer*` | lap finish times, one per lap, cumulative |
| `+0x40` | `Timer*` | race finish time |

`Timer`, size `0xC`: `+0x00` vtable, `+0x04` u16 minutes, `+0x06` u8 seconds,
`+0x08` u16 milliseconds, `+0x0A` set-yet flag.

**How.** The layout follows SeekyCt's public `mkw-structures` documentation of
`RaceinfoPlayer`, used as a source of candidates and then checked here. Two
things differ in PAL: the `Timer*` pair sits 4 bytes later than documented,
and `Timer` carries a vtable at `+0x00`.

**Confidence.** Ranking the twelve racers by `+0x0C` reproduces the game's own
reported position 98–99% of the time across four recordings.

**Watch out.** `PLAYER_DELTA` was `0x140` for a while, which is one struct
early — every field read the *next* racer's value and still looked plausible.
The `+0x0B0` progress claim that came from it measured at chance.

## Items — `KartItem`

```
base = u32(u32(0x809C3618) + 0x14),  12 entries of 0x248
```

| offset | type | field |
|---|---|---|
| `+0x077` | u8 | roulette result — what the spin has already chosen |
| `+0x08F` | u8 | held item, 20 = nothing |

**How.** The path is the one the game uses, lifted from the collision code at
`0x805808CC`:

```
lwz  r3, 13848(r4)      ; ItemDirector = *(0x809C3618)
lwz  r3, 20(r3)         ; + 0x14 -> the array
mulli r0, r0, 584       ; 0x248 stride, indexed by player
```

**Roulette vs held.** `+0x077` is non-empty only while the box is spinning and
names the item about 3.5 seconds before the player sees it. `+0x08F` is set
when the spin settles and cleared on use. An earlier version of this repo
mistook the roulette field for the held item; the tell was that its runs were
always exactly 3.55s for the human and 1.15s for every AI — a fixed animation
length, not a player carrying something.

**Known gap.** For a triple, the held id stays put while all three are thrown,
so throws inside a triple are not counted separately.

## Damage — what hit you

`KartItem` is a `KartObjectProxy`, so it can be walked to the object the
collision code writes a hit into:

```
accessor = u32(kartItem)
sub      = u32(accessor + 0x2C)
```

| offset | type | field |
|---|---|---|
| `+0x01C` | s32 | current damage type, `-1` when not hit |
| `+0x0C0` | ptr | `0x808B4C58 + type*12`; survives after the hit ends |
| `+0x0F6` | s16 | priority; a stronger hit overrides a weaker one |

### Damage types

| id | effect | cause | item? |
|---|---|---|---|
| 0 | spin-out | banana | yes |
| 1 | spin-out | enemy (Goomba, Pokey, crab, Shy Guy) | no |
| 2 | knockback | shell or fake item box | yes |
| 3 | knockback | boosted kart, cow, Coconut Mall car | no |
| 4 | knockback | Chain Chomp | no |
| 5 | knockback | Moonview car | no |
| 6 | knockback | Bullet Bill | no |
| 7 | launched | bob-omb or blue shell | yes |
| 8 | launched | Cataquack | no |
| 9 | fiery spin-out | fire ring, Fire Snake, meteor | no |
| 10 | spin-out | Lightning | yes |
| 11 | POW'd | POW Block | yes |
| 12 | crushed | Thwomp | no |
| 13 | crushed | Mega Mushroom | yes |
| 14 | crushed | Moonview truck | no |
| 15 | spin-out | Zapper | no |
| 16 | crushed, then respawn | Thwomp Desert | no |
| 17 | spin-out | Thunder Cloud | yes |

**How.** Not by searching — three rounds of that failed. The community's "Item
Damage Type Modifier" Gecko codes name the PAL call sites that set a hit's
damage type. Those addresses are in MEM1, which the recorder captures, so the
code can be disassembled straight out of a recording:

```
0x805808A4  li r4,10  ; shock
0x805808BC  li r4,17  ; thunder cloud
0x805811A4  li r4,11  ; POW
            bl 0x80590D5C
```

Those three constants match the published enum, which validates the whole
table before a byte is scored. `0x80590D5C` is a thunk — `proxy->[0]`, then
`->[0x2C]`, secondary vtable at `+0x0C`, slot 3. Resolving that statically
(group every pointed-at heap object by the word at `+0x0C`, keep the classes
with exactly twelve instances) gives vtable `0x808B5008`, slot 3
`0x805675DC` — the handler:

```
0x805678D8  stw  r22,28(r21)   ; damage type -> sub+0x1C
0x805678E8  stw  r6,192(r21)   ; table entry -> sub+0xC0
0x805678FC  sth  r5,246(r21)   ; priority    -> sub+0xF6
0x805678AC  stw  r3,28(r21)    ; r3 = -1, on clear
```

**Confidence.** Values never leave `-1..17` for any racer on any frame of
seven recordings. Cross-checked against the item field, which is read from
somewhere else entirely: 254 of 274 item-caused hits (93%) have a matching
item use within 12s. A Lightning marks every racer *except* the one who used
it, in the same frame. A POW marks only the racers ahead of the user. The 20
residuals are bananas lying on the track longer than the window, and Thunder
Clouds, which pass between karts.

**Not available here.** The collision code passes `r8 = 12` to the damage
call, which is the "no attacker" value, so the victim never learns who fired.
The item object does — see "Naming the item behind a hit" below.

## Items in the world

The shells, bananas and boxes actually on the track. One pool per item type,
in a table hanging off `ItemDirector`:

```
entry = u32(0x809C3618) + 0x48 + type*0x24
```

| offset | type | field |
|---|---|---|
| `+0x00` | u32 | item type — equal to the entry's own index |
| `+0x04` | ptr | array of pointers to that type's objects |
| `+0x08` | u32 | capacity |
| `+0x10` | u32 | how many are live right now |

The live objects are `array[0 .. live-1]`, densely packed. Each object:

| offset | type | field |
|---|---|---|
| `+0x04` | u32 | item type again |
| `+0x6C` | u8 | owner: the racer who fired it |

A pool slot keeps its address for the whole race, so an address is a stable
identity and an address leaving the live set is that item being destroyed.

Capacities in a 12-player race: 14 green shells, 10 red, 18 bananas, 6 fake
item boxes, 3 bob-ombs, 1 blue shell.

| type | item | how known |
|---|---|---|
| 0 | green shell | 66/66 spawns follow a green or triple-green use |
| 1 | red shell | 65/65 |
| 2 | banana | 163/163 |
| 5 | blue shell | 15/15, capacity 1 |
| 7 | fake item box | 29/29 |
| 9 | bob-omb | 6/6 |
| 4, 12 | star, golden mushroom | 1 and 3 spawns; they never hit anyone |

**Watch out.** `ItemDirector + 0x264` looks like a live-item array and this
repo read it as one. It is not: `0x80799CAC` fills it with the objects near
**one kart**, capped at 16, and the collision loop consumes it per kart. That
is why it never showed more than three items at once. The pools show up to 22.

Type also indexes a table of 3-word member-pointer descriptors at `0x808B5468`,
stride `0xC`, function at `+8`, so `getDamageType` for type *t* is at
`u32(0x808B5470 + t*0xC)`. Disassembling those gives which object types can
cause which damage type, with no scoring involved:

| damage | object types | handler |
|---|---|---|
| 0 spin-out | 2 | `neg r3,r0` — 0 or -1 |
| 2 knockback | 0, 1, 7 | `li r3,2` |
| 7 launched | 5, 9 | `li r3,7` once it has gone off, else 0 |

## Naming the item behind a hit

The damage field says "knockback" and never says which shell. The object that
did it is destroyed a fixed delay after the hit, while it breaks or explodes,
so the pool that loses an entry names the item — and `+0x6C` names the thrower,
which the damage path deliberately does not carry.

Delay measured across seven recordings, not assumed:

| damage | despawn follows the hit by |
|---|---|
| 0, 2 | 0.25–0.40s, i.e. 20 game frames, sharply peaked |
| 7 | 1–2s, the longer explosion |

**Confidence.** 165 of 182 item-caused hits get a name. 149 of those can be
traced further back to the throw that spawned the object, read from the
held-item field, which is a different field reached by a different path:
**149 agree, 0 disagree**. See `analysis/name_hit_items.py`.

## Code landmarks

Read-only, for anyone re-deriving the above.

| address | what |
|---|---|
| `0x80590D5C` | damage thunk, `(proxy, damageType)` |
| `0x805675DC` | damage handler, stores the type |
| `0x80590A5C` | `proxy -> [0] -> [0] -> u8 at +0x10` = player index |
| `0x805725E8` | collision loop, over the per-kart candidate buffer |
| `0x80799CAC` | fills that buffer from the pools; returns how many |
| `0x808B4C58` | damage type table, stride 12 |
| `0x808B5468` | per-item-type handler table, stride 12 |

`lab/ppc.py` disassembles any of these straight out of a recording.

## Capture coverage

MEM1 `0x80000000–0x81800000` and MEM2 `0x90000000–0x91800000`. MEM2 above
`0x91800000` has never been recorded. Nothing so far has needed it.
