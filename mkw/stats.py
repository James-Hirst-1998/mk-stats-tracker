"""Everything the dashboard shows, computed from stored race logs.

Nothing here reads memory. Each function takes files `mkw.racelog` and
`mkw.session` already know how to read and returns plain dicts for
`tools/dashboard.py` to serialise. Same files in, same numbers out - the
frontend renders and never calculates.

The unit of identity is the *player*: a person who keeps the same character
for a night. `players.json` in a session directory says who is tracked:

    {"planned_races": 32,
     "players": [{"name": "James", "human": true},
                 {"name": "Shikhar", "character": 22},
                 {"name": "Wang", "character": 2},
                 {"name": "Seb", "character": 18}]}

An entry matches by character id, or - `"human": true` - whichever racer the
game says is human that race, which survives a character change between races.
Without the file, the tracked players are simply the humans found in the
races, named by their characters. CPUs always count as attackers, victims and
opponents; they just don't get a row of their own.
"""

import json
import os

from mkw import report
from mkw.names import (CHARACTERS, COURSES, DAMAGE_TYPES, ITEMS, OBJECT_TYPES,
                       VS_POINTS, course_name)

# Items whose use is a boost. Trick, wheelie and drift boosts are not in the
# logs at all, so "boosts" on the dashboard means exactly these.
BOOST_ITEMS = {i for i, n in ITEMS.items()
               if n in ("Mushroom", "Triple Mushrooms", "Golden Mushroom",
                        "Star", "Bullet Bill")}

BLUE_OBJECT = 5                          # world-object type of the Blue Shell


def player_config(session_dir):
    path = os.path.join(session_dir, "players.json")
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


def tracked_players(session, config):
    """[{name, character?, human?}] - the rows of every dashboard table."""
    players = config.get("players")
    if players:
        return players
    seen = []
    for race in session.races:
        for r in race.meta.get("racers", []):
            if not r.get("cpu") and r["character"] not in [
                    p.get("character") for p in seen]:
                seen.append({"name": CHARACTERS.get(r["character"],
                                                    "racer %d" % r["slot"]),
                             "character": r["character"]})
    return seen


def slot_of(player, race):
    """Which slot this player raced in, or None if they sat it out."""
    for r in race.meta.get("racers", []):
        if player.get("human"):
            if not r.get("cpu"):
                return r["slot"]
        elif r.get("character") == player.get("character"):
            return r["slot"]
    return None


def cause_of(e):
    """Deterministic short name for what a hit was."""
    if e.get("object") is not None:
        return OBJECT_TYPES.get(e["object"], "item %d" % e["object"])
    kind = DAMAGE_TYPES.get(e.get("damage"))
    return kind[1] if isinstance(kind, tuple) else (kind or "something")


def race_rows(race, players):
    """{player index: the numbers for one race}, from `report.summary`."""
    summary = report.summary(race)
    slots = {i: slot_of(p, race) for i, p in enumerate(players)}
    by_slot = {s: i for i, s in slots.items() if s is not None}
    rows = {}
    for i, p in enumerate(players):
        s = slots[i]
        if s is None or s not in summary:
            continue
        r = summary[s]
        hits = [e for e in race.events
                if e.get("type") == "hit" and not e.get("after")]
        uses = [e for e in race.events
                if e.get("type") == "use" and not e.get("after")
                and e.get("slot") == s]
        rows[i] = {
            "slot": s,
            "character": next((x["character"]
                               for x in race.meta.get("racers", [])
                               if x["slot"] == s), None),
            "position": r["position"],
            "points": VS_POINTS.get(r["position"], 0),
            "finished": r["finished"],
            "time": r["time"],
            "laps": r["laps"],
            "led": round(r["leading"] or 0.0, 1),
            "thrown": len(uses),
            "landed": sum(v for v in r["hits_dealt"].values()),
            "taken": r["hits_taken"],
            "caught": r["caught"],
            "blues": sum(1 for e in hits if e.get("slot") == s
                         and e.get("object") == BLUE_OBJECT),
            "boosts": sum(1 for e in uses if e["item"] in BOOST_ITEMS),
            "out": round(r["out"], 1),
        }
    # Who hit whom, in player terms, for the nemesis lines.
    duels = {}
    for e in race.events:
        if e.get("type") != "hit" or e.get("after"):
            continue
        by = e.get("by") or []
        if len(by) != 1:
            continue
        a, v = by[0], e.get("slot")
        duels.setdefault((by_slot.get(a, -1), a, by_slot.get(v, -1), v), 0)
        duels[(by_slot.get(a, -1), a, by_slot.get(v, -1), v)] += 1
    return rows, duels


def session_stats(session_dir, session):
    """The whole dashboard payload for one session."""
    config = player_config(session_dir)
    players = tracked_players(session, config)
    races = []
    duel_total = {}
    for n, race in enumerate(session.races, 1):
        rows, duels = race_rows(race, players)
        chars = {x["slot"]: x["character"]
                 for x in race.meta.get("racers", [])}
        # Keyed by player index where tracked, by character ("c17") where not,
        # so a CPU nemesis keeps one identity across the night too.
        for (ai, a_slot, vi, v_slot), v in duels.items():
            a = ai if ai >= 0 else "c%d" % chars.get(a_slot, -1)
            b = vi if vi >= 0 else "c%d" % chars.get(v_slot, -1)
            duel_total[(a, b)] = duel_total.get((a, b), 0) + v
        win = winner_of(race)
        if win:
            win["player"] = next(
                (int(i) for i, row in rows.items()
                 if row["slot"] == win["slot"]), None)
        races.append({
            "n": n,
            "file": os.path.basename(race.path),
            "course": race.course,
            "course_name": course_name(race.course),
            "laps": race.meta.get("laps"),
            "recorded": race.meta.get("recorded"),
            "winner": win,
            "first_blood": first_blood(race, players),
            "rows": rows,
        })
    return {
        "name": session.name,
        "dir": os.path.basename(session_dir),
        "started": session.meta.get("started"),
        "planned_races": config.get("planned_races"),
        "players": [{"name": p["name"],
                     "character": p.get("character"),
                     "character_name": CHARACTERS.get(p.get("character")),
                     "human": bool(p.get("human"))} for p in players],
        "teams": config.get("teams"),
        "races": races,
        "duels": [{"from": a, "to": b, "count": v}
                  for (a, b), v in sorted(duel_total.items(),
                                          key=lambda kv: -kv[1])],
        "awards": awards(races, players),
        "characters": {str(i): n for i, n in CHARACTERS.items()},
    }


def first_blood(race, players):
    """The first cleanly-attributed hit of the race: who drew it, and when.

    `player` is the tracked-player index when it was one of them, so the
    frontend can honour the character/name toggle; `name` is the character
    for a CPU.
    """
    slots = {i: slot_of(p, race) for i, p in enumerate(players)}
    for e in race.events:
        if e.get("type") == "hit" and not e.get("after"):
            by = e.get("by") or []
            if len(by) == 1:
                owner = next((i for i, s in slots.items() if s == by[0]), None)
                return {"player": owner,
                        "name": attacker_name(by[0], race, players, slots),
                        "t": round(e["t"], 1)}
    return None


def awards(races, players):
    """Whole-night awards. Fixed rules, so the same night gives the same
    winners: ties are shown as ties, not broken arbitrarily."""
    totals = {i: {"blues": 0, "thrown": 0, "landed": 0}
              for i in range(len(players))}
    collapse = None
    for r in races:
        for i, row in r["rows"].items():
            i = int(i)
            totals[i]["blues"] += row["blues"]
            totals[i]["thrown"] += row["thrown"]
            totals[i]["landed"] += row["landed"]
            if row["position"] and row["position"] > 3 and row["led"] >= 10:
                if collapse is None or row["led"] > collapse["led"]:
                    collapse = {"player": i, "led": row["led"],
                                "position": row["position"],
                                "race": r["n"],
                                "course_name": r["course_name"]}
    def tops(key, value):
        best = max((value(v) for v in totals.values()), default=0)
        return ([i for i, v in totals.items() if value(v) == best], best) \
            if best > 0 else ([], 0)

    magnet, magnet_n = tops("blues", lambda v: v["blues"])
    sniper, sniper_rate = [], 0.0
    for i, v in totals.items():
        if v["thrown"] >= 5:
            rate = v["landed"] / v["thrown"]
            if rate > sniper_rate:
                sniper, sniper_rate = [i], rate
            elif rate == sniper_rate and rate > 0:
                sniper.append(i)
    bloods = {}
    for r in races:
        fb = r.get("first_blood")
        if fb:
            key = fb["player"] if fb.get("player") is not None else fb["name"]
            bloods[key] = bloods.get(key, 0) + 1
    blood = max(bloods.items(), key=lambda kv: kv[1]) if bloods else None
    return {
        "blue_magnet": {"players": magnet, "count": magnet_n},
        "sniper": {"players": sniper, "rate": round(sniper_rate, 2),
                   "landed": sum(totals[i]["landed"] for i in sniper),
                   "thrown": sum(totals[i]["thrown"] for i in sniper)}
                  if sniper else None,
        "first_blood": {"player": blood[0] if isinstance(blood[0], int)
                        else None,
                        "name": None if isinstance(blood[0], int)
                        else blood[0],
                        "count": blood[1]} if blood else None,
        "collapse": collapse,
    }


def winner_of(race):
    for s in race.standings:
        if s.get("position") == 1:
            r = next((x for x in race.meta.get("racers", [])
                      if x["slot"] == s["slot"]), {})
            return {"slot": s["slot"],
                    "character": r.get("character"),
                    "character_name": CHARACTERS.get(r.get("character")),
                    "cpu": bool(r.get("cpu")),
                    "time": s.get("time")}
    return None


# --- one race, for the expanded row and its chart -------------------------

SAMPLE_EVERY = 2.0                       # seconds between position samples


def position_series(race):
    """{slot: [position every SAMPLE_EVERY seconds]}, from the pos events."""
    swaps = sorted(race.of_type("pos"), key=lambda e: e["t"])
    end = report.duration(race)
    at = {}
    for e in swaps:
        at.setdefault(e["slot"], e["from"])
    for r in race.meta.get("racers", []):
        at.setdefault(r["slot"], r["grid"])
    series = {s: [] for s in at}
    i = 0
    steps = int(end // SAMPLE_EVERY) + 1
    for k in range(steps + 1):
        t = k * SAMPLE_EVERY
        while i < len(swaps) and swaps[i]["t"] <= t:
            at[swaps[i]["slot"]] = swaps[i]["to"]
            i += 1
        for s in at:
            series[s].append(at[s])
    return series


def race_detail(session_dir, session, filename):
    """One race: series for the chart, markers, and the per-player table."""
    race = next((r for r in session.races
                 if os.path.basename(r.path) == filename), None)
    if race is None:
        return None
    config = player_config(session_dir)
    players = tracked_players(session, config)
    rows, _ = race_rows(race, players)
    series = position_series(race)
    slots = {i: slot_of(p, race) for i, p in enumerate(players)}
    markers = []
    for e in race.events:
        if e.get("type") != "hit" or e.get("after"):
            continue
        s = e.get("slot")
        owner = next((i for i, sl in slots.items() if sl == s), None)
        if owner is None:
            continue
        idx = int(round(e["t"] / SAMPLE_EVERY))
        row = series.get(s) or []
        attackers = [attacker_name(a, race, players, slots)
                     for a in (e.get("by") or [])]
        markers.append({
            "player": owner,
            "t": round(e["t"], 1),
            "index": min(idx, len(row) - 1) if row else 0,
            "position": row[min(idx, len(row) - 1)] if row else None,
            "cause": cause_of(e),
            "blue": e.get("object") == BLUE_OBJECT,
            "by": [a for a in attackers if a],
            "caught": bool(e.get("caught")),
            "guess": bool(e.get("guess")),
        })
    return {
        "file": filename,
        "course_name": race.course_name,
        "laps": race.meta.get("laps"),
        "winner": winner_of(race),
        "duration": round(report.duration(race), 1),
        "sample_every": SAMPLE_EVERY,
        "players": [{"name": p["name"], "slot": slots[i]}
                    for i, p in enumerate(players)],
        "series": {str(i): series[slots[i]]
                   for i in range(len(players))
                   if slots[i] is not None and slots[i] in series},
        "markers": markers,
        "lap_starts": lap_starts(race),
        "rows": rows,
    }


def attacker_name(slot, race, players, slots):
    for i, s in slots.items():
        if s == slot:
            return players[i]["name"]
    r = next((x for x in race.meta.get("racers", [])
              if x["slot"] == slot), None)
    return CHARACTERS.get(r["character"]) if r else None


def lap_starts(race):
    """When each lap after the first began: the first crossing per lap."""
    firsts = {}
    for e in race.of_type("lap"):
        lap = e.get("lap")
        if lap and lap >= 1 and (lap + 1) not in firsts:
            firsts[lap + 1] = round(e["t"], 1)
    return [{"lap": lap, "t": t} for lap, t in sorted(firsts.items())]


# --- the replay screen ----------------------------------------------------

def replay_data(session_dir, session, filename):
    """Progress traces plus a deterministic ticker for one race."""
    race = next((r for r in session.races
                 if os.path.basename(r.path) == filename), None)
    if race is None or not race.track:
        return None
    config = player_config(session_dir)
    players = tracked_players(session, config)
    slots = {i: slot_of(p, race) for i, p in enumerate(players)}
    named = {s: p["name"] for i, p in enumerate(players)
             if (s := slots[i]) is not None}
    step = max(1, int(SAMPLE_EVERY * race.track_hz))
    traces = {str(s): [round(max(v, 0.0), 3) for v in row[::step]]
              for s, row in race.track.items()}
    field = {}
    for r in race.meta.get("racers", []):
        s = r["slot"]
        field[str(s)] = {
            "name": named.get(s, CHARACTERS.get(r["character"],
                                                "slot %d" % s)),
            "character": r["character"],
            "cpu": bool(r.get("cpu")),
            "player": next((i for i, sl in slots.items() if sl == s), None),
        }
    events = []
    for e in race.events:
        if e.get("after"):
            continue
        line = ticker_line(e, race, named)
        if line:
            events.append({"t": round(e["t"], 1), "text": line})
    return {
        "file": filename,
        "course": race.course,
        "course_name": race.course_name,
        "laps": race.meta.get("laps"),
        "duration": round(report.duration(race), 1),
        "sample_every": step / float(race.track_hz),
        "field": field,
        "traces": traces,
        "events": events,
        "avg_lap": avg_lap(race),
    }


def avg_lap(race):
    """Median winning lap, for turning progress gaps into rough seconds."""
    laps = []
    for s in race.standings:
        laps += s.get("laps") or []
    laps.sort()
    return round(laps[len(laps) // 2], 1) if laps else None


def ticker_line(e, race, named):
    """One deterministic sentence, or None for events the ticker skips.

    Position swaps are far too many to narrate; the ticker keeps hits, blue
    shells, lead changes into and out of tracked players, and the flag.
    """
    t = e.get("type")
    who = lambda s: named.get(s) or race.field.name(s)
    if t == "hit":
        victim = who(e["slot"])
        cause = cause_of(e)
        by = e.get("by") or []
        tail = " (%s)" % ", ".join(who(b) for b in by) if by else ""
        if e.get("object") == BLUE_OBJECT:
            return "Blue shell: %s%s" % (victim, tail)
        if e.get("caught"):
            return "%s caught in the blast%s" % (victim, tail)
        return "%s hit by %s%s" % (victim, cause, tail)
    if t == "pos" and e.get("to") == 1:
        return "%s takes the lead" % who(e["slot"])
    if t == "finish" and e.get("position") == 1:
        return "%s takes the flag" % who(e["slot"])
    if t == "finish" and e["slot"] in named:
        return "%s finishes P%d" % (who(e["slot"]), e.get("position", 0))
    return None
