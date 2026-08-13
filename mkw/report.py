"""Rebuild the analysis from a stored race log.

Nothing here reads memory or a recording. Everything comes back out of the
events file, which is the point of storing one: if a number in here cannot be
derived from the events, the events are missing something.

Times spent in a position are reconstructed from the `pos` events; everything
else is a count over the event stream, or a value the game itself reported and
the log kept verbatim.
"""

import os
from collections import Counter, defaultdict

from mkw import addresses as A
from mkw.events import fmt, ordinal, describe, readable, QUIET
from mkw.names import (ITEMS, DAMAGE_TYPES, OBJECT_TYPES, BY_ITEM, CHARACTERS,
                       VEHICLES)


def duration(log):
    """How long the race ran, on the race clock."""
    ends = [s.get("raced") for s in log.standings if s.get("raced")]
    ends += [s["time"] for s in log.standings if s.get("time")]
    if ends:
        return max(ends)
    return max((e["t"] for e in log.events), default=0.0)


def ends_at(log):
    """{slot: when that racer's race ended}. Their finish, or where they got to.

    `raced` is `+0x2C`, which stops when the race ends for that racer whether
    or not they crossed the line - so a racer still on track when the last CPU
    finishes is not credited with the position they were parked in afterwards.
    """
    end = duration(log)
    return {s["slot"]: (s.get("raced") or s.get("time") or end)
            for s in log.standings}


def positions(log):
    """{slot: {position: seconds spent there}}, rebuilt from the `pos` events.

    Seeded from each racer's first swap - its `from` is the position they held
    for the whole of the log before it - rather than from the starting grid,
    which is only the same thing when the log starts at GO. `begins` is where
    the log actually starts, which is not 0 if the race was already running.
    """
    start = log.meta.get("begins") or 0.0
    stop = ends_at(log)
    end = duration(log)
    swaps = sorted(log.of_type("pos"), key=lambda e: e["t"])
    at = {}
    for e in swaps:                        # seed: first `from` seen per slot
        at.setdefault(e["slot"], e["from"])
    for r in log.meta.get("racers", []):   # never swapped: the grid still holds
        at.setdefault(r["slot"], r["grid"])
    out = defaultdict(Counter)
    since = {s: start for s in at}
    for e in swaps:
        s = e["slot"]
        limit = min(e["t"], stop.get(s, end))
        out[s][at[s]] += max(0.0, limit - since[s])
        at[s], since[s] = e["to"], max(since[s], limit)
    for s in at:
        out[s][at[s]] += max(0.0, stop.get(s, end) - since[s])
    return {s: Counter({p: round(v, 2) for p, v in c.items() if v > 0})
            for s, c in out.items()}


def hit_by(e):
    """A short name for whatever caused a hit.

    Most hits name the object that did it. A Star, Mega or Bullet ram leaves no
    object, so all there is to say is what the damage was - and those are 109
    of the hits in a session, so leaving them out of the column made a race
    where somebody starred through the field look uneventful.
    """
    if e.get("object") is not None:
        return OBJECT_TYPES.get(e["object"], "item %d" % e["object"])
    return DAMAGE_TYPES.get(e["damage"], ("?", "something"))[1]


def counts(log):
    """The events the totals are built from: everything that happened while
    the racer it happened to was still racing. A shell that catches somebody
    parked past the finish line is in the log, and is not a statistic."""
    return [e for e in log.events if not e.get("after")]


def summary(log):
    """One dict per racer, keyed by slot."""
    final = {s["slot"]: s for s in log.standings}
    pos_time = positions(log)
    racers = {r["slot"]: r for r in log.meta.get("racers", [])}
    out = {}
    for slot in log.slots():
        f = final.get(slot, {})
        laps = f.get("laps") or []
        r = racers.get(slot, {})
        # +0x30 starts at the intro, so whoever is on pole is credited the
        # countdown as time in first. Taken off here rather than in the reader,
        # which stays a plain read.
        lead = f.get("leading")
        if lead is not None and r.get("grid") == 1:
            lead = max(0.0, lead - A.COUNTDOWN_FRAMES / 60.0)
        out[slot] = {
            "slot": slot,
            "name": log.field.name(slot),
            "character": CHARACTERS.get(r.get("character")),
            "vehicle": VEHICLES.get(r.get("vehicle")),
            "cpu": r.get("cpu"),
            "grid": r.get("grid"),
            "position": f.get("position"),
            "finished": f.get("finished"),
            "time": f.get("time"),
            "laps": laps,
            "best_lap": min(laps) if laps else None,
            "leading": lead,
            "leading_raw": f.get("leading"),
            "raced": f.get("raced"),
            "position_time": dict(pos_time.get(slot, {})),
            "boxes": 0,
            "held": Counter(),
            "used": Counter(),
            # Knocked out of their hands rather than thrown. Kept apart from
            # `used` because a Lightning would otherwise read as eleven racers
            # all choosing to use what they were holding in the same frame.
            "lost": Counter(),
            "hits_taken": 0,
            "hits_by_damage": Counter(),
            "hits_by_item": Counter(),
            "hit_by_racer": Counter(),
            "hits_dealt": Counter(),
            "hazards": 0,
            "caught": 0,
            # Seconds spun out, flipped or flattened, from the damage field's
            # own start and end. Only counts hits whose end was seen.
            "out": 0.0,
        }
    for e in counts(log):
        s = e.get("slot")
        row = out.get(s)
        t = e["type"]
        if row is not None:
            if t == "box":
                row["boxes"] += 1
            elif t == "hold":
                row["held"][e["item"]] += 1
            elif t == "use":
                row["used"][e["item"]] += 1
            elif t == "lost":
                row["lost"][e["item"]] += 1
            elif t == "hit":
                row["hits_taken"] += 1
                row["hits_by_damage"][e["damage"]] += 1
                row["hits_by_item"][hit_by(e)] += 1
                if e.get("for") is not None:
                    row["out"] += e["for"]
                if e.get("caught"):
                    row["caught"] += 1
                if e["damage"] not in BY_ITEM:
                    row["hazards"] += 1
        # Who threw it is only credited when the despawn window named exactly
        # one owner. Two candidate owners is not evidence about either.
        if t == "hit" and len(e.get("by") or []) == 1:
            by = e["by"][0]
            if by in out and by != s:
                out[by]["hits_dealt"][hit_by(e)] += 1
            if by in out and s in out and by != s:
                out[s]["hit_by_racer"][by] += 1
    return out


def render(log, events=True, quiet=True):
    """The whole race as text, rebuilt from the file.

    `quiet` hides the position swaps from the printed stream only. They stay
    in the log and the numbers below are still computed from them.
    """
    m = log.meta
    lines = ["%s   %s laps   %s   %d events"
             % (log.course_name, m.get("laps", "?"), m.get("recorded", "?"),
                len(log.events))]
    if m.get("notes"):
        lines.append("notes: %s" % m["notes"])
    if m.get("source"):
        lines.append("source: %s" % m["source"])
    if m.get("begins"):
        lines.append("picked up %.1fs into the race - nothing before that was "
                     "seen" % m["begins"])
    lines.append("")

    if events:
        shown = readable(log.events) if quiet else log.events
        for e in shown:
            lines.append("  %9s  %s" % (fmt(e["t"]), describe(e, log.field)))
        if quiet and len(shown) != len(log.events):
            after = sum(1 for e in log.events if e.get("after"))
            lines.append("  (%d position swaps hidden%s)"
                         % (len(log.events) - len(shown) - after,
                            ", and %d events after that racer finished" % after
                            if after else ""))
        lines.append("")

    stats = summary(log)
    rows = sorted(stats.values(),
                  key=lambda r: (r["position"] is None, r["position"]))
    row = "%-4s %-19s %-5s %-9s %-9s %-8s %-24s %s"
    lines.append(row % ("pos", "racer", "grid", "total", "best lap", "leading",
                        "lap splits", ""))
    for r in rows:
        lines.append(row % (
            "P%s" % r["position"],
            "%s%s" % (r["name"], " (CPU)" if r["cpu"] else ""),
            ordinal(r["grid"]),
            fmt(r["time"]) if r["finished"] else "(dnf)",
            "%.3f" % r["best_lap"] if r["best_lap"] else "-",
            "%.1fs" % (r["leading"] or 0),
            " ".join("%.3f" % x for x in r["laps"]) or "-",
            "<- you" if r["slot"] == log.local_slot else ""))

    lines.append("")
    row = "%-4s %-19s %-6s %-6s %-6s %-7s %-7s %s"
    lines.append(row % ("pos", "racer", "boxes", "used", "hit", "hazard",
                        "out", "what hit them"))
    for r in rows:
        what = ", ".join("%dx %s" % (n, o)
                         for o, n in r["hits_by_item"].most_common())
        lines.append(row % (
            "P%s" % r["position"], r["name"], r["boxes"],
            sum(r["used"].values()), r["hits_taken"] - r["hazards"],
            r["hazards"], "%.1fs" % r["out"], what or "-"))

    me = stats.get(log.local_slot)
    if me:
        lines.append("")
        lines.append("you (%s):" % me["name"])
        lines.append("  items used:  %s" % (", ".join(
            "%dx %s" % (n, ITEMS.get(i, i)) for i, n in me["used"].most_common())
            or "none"))
        if me["lost"]:
            lines.append("  knocked out of your hands: %s" % ", ".join(
                "%dx %s" % (n, ITEMS.get(i, i)) for i, n in me["lost"].most_common()))
        lines.append("  hits taken:  %s" % (", ".join(
            "%dx %s (%s)" % (n, DAMAGE_TYPES.get(d, ("?", "?"))[0],
                             DAMAGE_TYPES.get(d, ("?", "?"))[1])
            for d, n in me["hits_by_damage"].most_common()) or "none"))
        lines.append("  hit by:      %s" % (", ".join(
            "%dx %s" % (n, log.field.name(s))
            for s, n in me["hit_by_racer"].most_common()) or "nobody"))
        lines.append("  you hit:     %s" % (", ".join(
            "%dx %s" % (n, o) for o, n in me["hits_dealt"].most_common())
            or "nobody"))
        lines.append("  time out of the race: %.1fs%s"
                     % (me["out"], ", %d of them caught in somebody else's "
                        "explosion" % me["caught"] if me["caught"] else ""))
        # Two counts of the same thing from different places: the game's own
        # frames-in-first, and the position events replayed. They should agree.
        lines.append("  time in P1:  %.1fs of %.1fs (from the position events: %.1fs)"
                     % (me["leading"] or 0, duration(log),
                        me["position_time"].get(1, 0.0)))
        lines.append("  positions:   %s" % ", ".join(
            "P%d %.1fs" % (p, v)
            for p, v in sorted(me["position_time"].items())))
    return "\n".join(lines)


def render_replay(log, step=1.0):
    """The race played back, `step` seconds at a time.

    Order and gaps come from the stored progress samples; the events are the
    ones that happened in that second. This is the check that the progress
    track is worth its size: if the order here disagrees with the `pos` events,
    one of the two is wrong.
    """
    lines = ["%s   replay at %.1fs steps   gaps are fractions of a lap"
             % (log.course_name, step), ""]
    times = log.track_times()
    if not times:
        return "\n".join(lines + ["no progress samples stored"])
    end = times[-1]
    t = times[0]
    while t <= end:
        order = log.order_at(t)
        prog = log.progress_at(t)
        lead = prog.get(order[0], 0.0) if order else 0.0
        lines.append("%9s  %s" % (fmt(t), "  ".join(
            "%d.%s%s" % (i + 1, log.field.name(s),
                         "" if i == 0 else "(-%.3f)" % (lead - prog[s]))
            for i, s in enumerate(order))))
        for e in log.events_between(t, t + step):
            if e["type"] not in QUIET:
                lines.append("%9s     %s" % ("", describe(e, log.field)))
        t += step
    return "\n".join(lines)


def render_session(s):
    """A whole sitting: each race, then the standings across all of them."""
    m = s.meta
    lines = ["session %s   %d race%s   %s"
             % (s.name, len(s), "" if len(s) == 1 else "s",
                m.get("started", "")),
             ""]
    if m.get("notes"):
        lines.append("notes: %s" % m["notes"])

    row = "%-3s %-22s %-9s %-9s %-6s %-6s %s"
    lines.append(row % ("#", "course", "your time", "best lap", "you",
                        "boxes", "what hit you"))
    for race, meta in zip(s.races, m.get("races", [])):
        me = summary(race).get(race.local_slot, {})
        what = ", ".join("%dx %s" % (n, o)
                         for o, n in me.get("hits_by_item", {}).most_common())
        lines.append(row % (
            meta["n"], race.course_name,
            fmt(me.get("time")) if me.get("finished") else "(dnf)",
            "%.3f" % me["best_lap"] if me.get("best_lap") else "-",
            "P%s" % me.get("position"), me.get("boxes", 0),
            what or "-"))

    lines.append("")
    if not s.same_field():
        lines.append("the field is not the same in every race, so adding these "
                     "up is not a series - the rows below are by slot, not by "
                     "racer:")
    else:
        lines.append("across the session, on MKW's VS points table:")
    pts = s.points()
    row = "%-4s %-19s %-7s %-8s %s"
    lines.append(row % ("", "racer", "points", "avg", "finishes"))
    ranked = sorted(pts.items(), key=lambda kv: -kv[1]["points"])
    for i, (slot, p) in enumerate(ranked):
        fin = p["finishes"]
        lines.append(row % (
            "%d." % (i + 1), s.field.name(slot), p["points"],
            "%.1f" % (sum(fin) / len(fin)) if fin else "-",
            " ".join("P%d" % f for f in fin)))
    lines.append("")
    lines.append("a race in full:  python3 -m tools.report %s <n>"
                 % os.path.basename(s.path).split("-", 2)[-1])
    return "\n".join(lines)
