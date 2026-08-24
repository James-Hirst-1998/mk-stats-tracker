#!/usr/bin/env python3
"""Turn the course layout drawings into the centreline the replay drives on.

    python3 -m tools.build_tracks            # all courses
    python3 -m tools.build_tracks luigi      # just the ones that match

The drawing itself is what the replay shows - it is real line art of the real
course, and nothing here has to be right for the picture to be right. What is
computed here is the *centreline*: the loop up the middle of the road, in the
drawing's own pixel coordinates, so that a racer 40% through a lap can be put
40% of the way along it.

How: the black outline is the road's two edges, so the road is the enclosed
region between them. Thin that region to one pixel wide (Zhang-Suen), throw
away the stubs thinning leaves at corners, and what is left is the middle of
the road. Take the longest closed loop in it - or the longest open path, for
the drawings whose outline has a gap - resample it evenly and smooth it.

Output is web/src/data/tracks.ts, which is checked in: the dashboard never
runs this, and re-running it on the same PNGs gives the same paths.

Nothing here is the game's own geometry. `docs/DASHBOARD.md` says what it
would take to have that instead, and tools/kmp.py is the reader for it.
"""

import json
import re
import math
import os
import struct
import sys
import zlib
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkw.names import COURSES
from mkw.racelog import slug

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "assets", "tracks", "source")
OUT = os.path.join(ROOT, "web", "src", "data", "tracks.ts")

INK_LUM = 110          # darker than this is a drawn line
INK_ALPHA = 100        # ... if it is actually opaque
SPUR = 0.10            # prune branches shorter than this much of the skeleton
SPACING = 3.0          # pixels between output points, before smoothing


# --- PNG, from the standard library ---------------------------------------

def decode_png(path):
    """(width, height, gray[], alpha[]) for an 8-bit non-interlaced PNG."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    idat, pal, trns, head = b"", None, None, None
    i = 8
    while i < len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + length]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"PLTE":
            pal = body
        elif kind == b"tRNS":
            trns = body
        i += 12 + length
    w, h, depth, color, _, _, interlace = head
    if depth != 8 or interlace:
        raise ValueError("only 8-bit, non-interlaced PNGs (got %d-bit%s)"
                         % (depth, ", interlaced" if interlace else ""))

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = w * channels
    raw = zlib.decompress(idat)
    rows = bytearray(stride * h)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f:
            for x in range(stride):
                a = line[x - channels] if x >= channels else 0
                b = prev[x]
                c = prev[x - channels] if x >= channels else 0
                if f == 1:
                    line[x] = (line[x] + a) & 255
                elif f == 2:
                    line[x] = (line[x] + b) & 255
                elif f == 3:
                    line[x] = (line[x] + (a + b) // 2) & 255
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    line[x] = (line[x] + (a if pa <= pb and pa <= pc
                                          else b if pb <= pc else c)) & 255
        rows[y * stride:(y + 1) * stride] = line
        prev = line

    # A colour-type 2 or 0 image has no alpha channel, but tRNS names one
    # colour that is transparent - which is how three of these drawings store
    # their background. Missing that reads the background as ink.
    key = None
    if trns and color in (0, 2):
        vals = struct.unpack(">%dH" % (len(trns) // 2), trns)
        key = tuple(v & 0xFF for v in vals)

    gray, alpha = bytearray(w * h), bytearray(w * h)
    for y in range(h):
        for x in range(w):
            k = y * stride + x * channels
            if color == 0:
                g, a = rows[k], 0 if key and (rows[k],) == key else 255
            elif color == 4:
                g, a = rows[k], rows[k + 1]
            elif color in (2, 6):
                r, gg, bb = rows[k], rows[k + 1], rows[k + 2]
                g = (r * 299 + gg * 587 + bb * 114) // 1000
                a = rows[k + 3] if color == 6 else (
                    0 if key and (r, gg, bb) == key else 255)
            else:
                idx = rows[k]
                r, gg, bb = pal[idx * 3:idx * 3 + 3]
                g = (r * 299 + gg * 587 + bb * 114) // 1000
                a = trns[idx] if trns and idx < len(trns) else 255
            gray[y * w + x], alpha[y * w + x] = g, a
    return w, h, gray, alpha


# --- the road -------------------------------------------------------------

def road_mask(w, h, gray, alpha):
    """The enclosed regions of the drawing: the road, and anything the road
    encircles. Both are kept - which one is the road is decided later, by
    which one has a loop up the middle of it."""
    ink = bytearray(w * h)
    for i in range(w * h):
        ink[i] = 1 if alpha[i] > INK_ALPHA and gray[i] < INK_LUM else 0

    outside = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            k = y * w + x
            if not ink[k] and not outside[k]:
                outside[k] = 1
                q.append(k)
    for y in range(h):
        for x in (0, w - 1):
            k = y * w + x
            if not ink[k] and not outside[k]:
                outside[k] = 1
                q.append(k)
    while q:
        k = q.popleft()
        x, y = k % w, k // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                n = ny * w + nx
                if not ink[n] and not outside[n]:
                    outside[n] = 1
                    q.append(n)

    return bytearray(0 if ink[i] or outside[i] else 1 for i in range(w * h))


def components(mask, w, h):
    """Connected regions of a mask, biggest first, as sets of indexes."""
    seen = bytearray(w * h)
    out = []
    for start in range(w * h):
        if not mask[start] or seen[start]:
            continue
        got, q = [], deque([start])
        seen[start] = 1
        while q:
            k = q.popleft()
            got.append(k)
            x, y = k % w, k // w
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    n = ny * w + nx
                    if mask[n] and not seen[n]:
                        seen[n] = 1
                        q.append(n)
        out.append(set(got))
    out.sort(key=len, reverse=True)
    return out


NEIGHBOURS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))


def thin(pixels, w, h):
    """Zhang-Suen: erode a region to a one-pixel line up its middle."""
    on = set(pixels)
    while True:
        removed = []
        for step in (0, 1):
            marked = []
            for k in on:
                x, y = k % w, k // w
                n = [1 if (0 <= x + dx < w and 0 <= y + dy < h
                           and (y + dy) * w + x + dx in on) else 0
                     for dx, dy in NEIGHBOURS]
                count = sum(n)
                if not 2 <= count <= 6:
                    continue
                # transitions from 0 to 1 going round the neighbours
                trans = sum(1 for i in range(8)
                            if n[i] == 0 and n[(i + 1) % 8] == 1)
                if trans != 1:
                    continue
                p0, p2, p4, p6 = n[0], n[2], n[4], n[6]
                if step == 0 and (p0 * p2 * p4 or p2 * p4 * p6):
                    continue
                if step == 1 and (p0 * p2 * p6 or p0 * p4 * p6):
                    continue
                marked.append(k)
            on.difference_update(marked)
            removed += marked
        if not removed:
            return on


def graph_of(skeleton, w, h):
    """{pixel: [neighbouring pixels]} over the thinned line.

    A diagonal step is dropped when the same two pixels are already joined by
    two straight steps. Without that, every staircase in the line reads as a
    junction, and a plain loop comes back looking like a hundred of them.
    """
    g = {}
    for k in skeleton:
        x, y = k % w, k // w
        near = []
        for dx, dy in NEIGHBOURS:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            n = ny * w + nx
            if n not in skeleton:
                continue
            if dx and dy and (y * w + nx in skeleton or ny * w + x in skeleton):
                continue
            near.append(n)
        g[k] = near
    return g


def chains(g):
    """The skeleton as edges between its junctions and its ends.

    A thinned track is nearly all pixels with two neighbours; the interesting
    ones are the junctions (three or more) and the dead ends (one). Everything
    between two of those is a chain, and it is chains that get pruned, not
    pixels."""
    nodes = [k for k, near in g.items() if len(near) != 2]
    if not nodes:
        return [], []                      # one clean loop, no junctions
    out, seen = [], set()
    for node in nodes:
        for first in g[node]:
            if (node, first) in seen:
                continue
            path = [node, first]
            seen.add((node, first))
            while len(g[path[-1]]) == 2:
                nxt = [n for n in g[path[-1]] if n != path[-2]]
                if not nxt:
                    break
                path.append(nxt[0])
            seen.add((path[-1], path[-2]))
            out.append(path)
    return out, nodes


def prune(g, w):
    """Drop the short stubs thinning leaves at corners and junctions.

    Short is measured against the longest chain, not against the whole
    skeleton: a course with one long lap and three stubs would otherwise set a
    threshold high enough to eat the lap as well."""
    for _ in range(20):
        edges, _ = chains(g)
        if not edges:
            return g
        limit = max(4, len(max(edges, key=len)) * SPUR)
        spurs = [e for e in edges
                 if len(g.get(e[-1], [])) == 1 and len(e) < limit]
        if not spurs:
            return g
        for e in spurs:
            for k in e[1:]:
                for n in g.pop(k, []):
                    if n in g and k in g[n]:
                        g[n].remove(k)
        g = {k: v for k, v in g.items() if v}
        if not g:
            return g
    return g


def longest_loop(g, w, h):
    """The best closed loop in the skeleton, or the longest open path.

    Returns (pixels, closed). A drawing whose outline has a gap - or whose
    road is cut where it crosses over itself - gives an open path, which is
    still one lap long and still the right shape."""
    if not g:
        return [], False
    edges, _ = chains(g)
    if not edges:                          # no junctions and no ends: a loop
        return walk_loop(g), True

    # Each chain is one step between two junctions, so the lap is the longest
    # route through a graph with a handful of nodes in it. Whether that route
    # comes back to where it started is decided by the caller, from how far
    # apart its two ends are: a course crossing over itself is drawn with a
    # bridge, and the bridge cuts the loop.
    adj = {}
    for i, e in enumerate(edges):
        adj.setdefault(e[0], []).append((e[-1], i, e))
        adj.setdefault(e[-1], []).append((e[0], i, list(reversed(e))))

    size = lambda path: sum(len(c) for c in path)
    best, budget = [], 200000
    for start in adj:
        stack = [(start, [], frozenset())]
        while stack and budget > 0:
            budget -= 1
            node, path, used = stack.pop()
            if size(path) > size(best):
                best = path
            if len(path) >= 14:
                continue
            for nxt, i, chain in adj[node]:
                if i not in used:
                    stack.append((nxt, path + [chain], used | {i}))
    if not best:
        return max(edges, key=len), False
    out = []
    for chain in best:
        out += chain[1:] if out else chain
    return out, False


def walk_loop(g):
    start = next(iter(g))
    loop, prev = [start], None
    while True:
        near = [n for n in g[loop[-1]] if n != prev]
        if not near:
            break
        prev, nxt = loop[-1], near[0]
        if nxt == start:
            break
        loop.append(nxt)
    return loop


# --- turning pixels into a path -------------------------------------------

def resample(points, closed, spacing=SPACING):
    """Even spacing, so a fraction along the path is a fraction of a lap."""
    pts = points + [points[0]] if closed else points
    total = 0.0
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        total += math.dist(a, b)
        lengths.append(total)
    if total == 0:
        return points
    n = max(12, int(total / spacing))
    out = []
    j = 0
    for i in range(n):
        want = total * i / n
        while j < len(lengths) - 2 and lengths[j + 1] < want:
            j += 1
        span = lengths[j + 1] - lengths[j]
        f = 0 if span == 0 else (want - lengths[j]) / span
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f,
                    pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f))
    if not closed:
        out.append(pts[-1])
    return out


def smooth(points, closed, rounds=3):
    """Take the staircase off a path traced from pixels."""
    pts = list(points)
    for _ in range(rounds):
        out = []
        for i in range(len(pts)):
            if not closed and i in (0, len(pts) - 1):
                out.append(pts[i])
                continue
            a = pts[(i - 1) % len(pts)]
            b = pts[i]
            c = pts[(i + 1) % len(pts)]
            out.append(((a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4))
        pts = out
    return pts


def path_d(points, closed):
    d = "M %.1f %.1f" % points[0]
    for p in points[1:]:
        d += " L %.1f %.1f" % p
    return d + " Z" if closed else d


def length_of(points, closed):
    pts = points + [points[0]] if closed else points
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def outline_of(pixels, w, h):
    """The edge of a set of pixels, as closed loops in the drawing's own
    coordinates.

    The road is a filled region, so its boundary is the two edges of the road.
    Every side of a pixel facing something outside the set is one unit-long
    edge; chained up, those edges are the outline. Drawn together with an
    even-odd fill, the loops give the road with whatever it encircles left as a
    hole, which is what a course drawn as a ring needs.

    This is what makes the outline resolution-free. The drawings are 100-280px
    and go to mush when a replay draws them at 600; the same shape as a path
    is as sharp as the screen it lands on.
    """
    on = set(pixels)
    out = {}
    for k in on:
        x, y = k % w, k // w
        if y == 0 or (y - 1) * w + x not in on:
            out.setdefault((x, y), []).append((x + 1, y))
        if x + 1 == w or y * w + x + 1 not in on:
            out.setdefault((x + 1, y), []).append((x + 1, y + 1))
        if y + 1 == h or (y + 1) * w + x not in on:
            out.setdefault((x + 1, y + 1), []).append((x, y + 1))
        if x == 0 or y * w + x - 1 not in on:
            out.setdefault((x, y + 1), []).append((x, y))

    loops = []
    while out:
        start = next(iter(out))
        loop, at = [start], start
        while True:
            nxt = out.get(at)
            if not nxt:
                break
            step = nxt.pop()
            if not nxt:
                del out[at]
            at = step
            if at == start:
                break
            loop.append(at)
        # A loop this short is a single stray pixel, not an edge of anything.
        if len(loop) >= 12:
            loops.append(loop)
    return loops


def simplify(points, tol=0.25):
    """Douglas-Peucker. Rounding the staircase off puts a point every pixel or
    so, and most of them sit on a straight: dropping those is most of the size
    of tracks.ts and none of the shape."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = points[i]
        bx, by = points[j]
        dx, dy = bx - ax, by - ay
        span = math.hypot(dx, dy) or 1.0
        worst, at = 0.0, None
        for k in range(i + 1, j):
            x, y = points[k]
            off = abs(dy * (x - ax) - dx * (y - ay)) / span
            if off > worst:
                worst, at = off, k
        if at is not None and worst > tol:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, k in zip(points, keep) if k]


def outline_d(loops):
    """The loops as one path, rounded off so it does not read as pixels."""
    parts = []
    for loop in loops:
        pts = smooth(resample(loop, True, spacing=1.2), True, rounds=2)
        # Douglas-Peucker on a loop, not through it: handing it a path whose
        # two ends are the same point makes every point zero distance from the
        # line between them, and it throws the whole loop away.
        far = max(range(len(pts)), key=lambda i: math.dist(pts[0], pts[i]))
        pts = simplify(pts[:far + 1]) + simplify(pts[far:])[1:]
        parts.append(path_d(pts, True))
    return " ".join(parts)


MAX_ROAD_WIDTH = 30      # wider than this is what the course encircles
MIN_PIECE = 0.15         # ignore road pieces this much shorter than the longest


def stitch(pieces, w, h):
    """Join the road up where the drawing leaves gaps in it.

    Several courses are not drawn as one continuous ribbon: Rainbow Road and
    Grumble Volcano have gaps you jump, Mushroom Gorge has the bouncy
    mushrooms, Koopa Cape goes into a pipe. Each stretch of road comes back as
    its own piece, and a lap is all of them end to end."""
    # A gap bigger than this is not the same road. Rainbow Road has the
    # widest real one, at a third of the drawing's diagonal.
    limit = 0.40 * math.hypot(w, h)
    start = max(range(len(pieces)), key=lambda i: len(pieces[i]))
    chain = list(pieces[start])
    rest = [p for i, p in enumerate(pieces) if i != start]
    while rest:
        best = None
        for i, p in enumerate(rest):
            options = (
                (math.dist(chain[-1], p[0]), i, "tail", p),
                (math.dist(chain[-1], p[-1]), i, "tail", p[::-1]),
                (math.dist(chain[0], p[-1]), i, "head", p),
                (math.dist(chain[0], p[0]), i, "head", p[::-1]),
            )
            for option in options:
                if best is None or option[0] < best[0]:
                    best = option
        gap, i, end, piece = best
        if gap > limit:
            break                        # too far to be the same road
        chain = chain + piece if end == "tail" else piece + chain
        rest.pop(i)
    return chain


def trace(path):
    w, h, gray, alpha = decode_png(path)
    mask = road_mask(w, h, gray, alpha)
    found = []
    for comp in components(mask, w, h)[:8]:
        if len(comp) < 300:
            continue
        skeleton = thin(comp, w, h)
        if len(comp) / max(len(skeleton), 1) > MAX_ROAD_WIDTH:
            continue
        pixels, closed = longest_loop(
            prune(graph_of(skeleton, w, h), w), w, h)
        if len(pixels) < 40:
            continue
        found.append({"pts": [(k % w, k // w) for k in pixels],
                      "closed": closed, "comp": comp, "skeleton": len(skeleton)})
    if not found:
        return None

    longest = max(len(f["pts"]) for f in found)
    keep = [f for f in found if len(f["pts"]) >= longest * MIN_PIECE]
    width = (sum(len(f["comp"]) for f in keep)
             / max(sum(f["skeleton"] for f in keep), 1))

    main = max(keep, key=lambda f: len(f["pts"]))
    if main["closed"]:                   # the longest piece is already a lap
        pts, closed = main["pts"], True
    else:
        pts = stitch([f["pts"] for f in keep], w, h)
        # Two ends that meet are a loop that was cut - by the bridge drawn
        # where a course crosses over itself, or by the start line.
        closed = math.dist(pts[0], pts[-1]) < max(4 * width, 0.08 * math.hypot(w, h))

    pts = smooth(resample(pts, closed), closed)
    length = length_of(pts, closed)
    # The road itself, as a shape rather than a picture: the edge of every
    # piece the lap runs through. Decoration the trace threw away - the
    # mushrooms in Mushroom Gorge, the hedges in Peach Gardens - is not in it,
    # because only the pieces kept above are asked for their edges.
    loops = outline_of([k for f in keep for k in f["comp"]], w, h)
    # How much of the road the lap actually covers. The thinned skeleton is
    # every stretch of road in the drawing, so a lap should be about as long
    # as all of it: well under 1 means the trace missed some, and well over 1
    # means it went up something and back down again.
    road = sum(f["skeleton"] for f in keep)
    return {
        "w": w, "h": h,
        "d": path_d(pts, closed),
        "outline": outline_d(loops),
        "closed": closed,
        "width": round(width, 1),
        "length": round(length, 1),
        "pieces": len(keep),
        "loops": len(loops),
        "covers": round(length / max(road, 1), 2),
    }


# --- the game's own geometry, when there is any ----------------------------

# Course id -> the folder its files sit in on the disc. Public naming, not
# read off anything here; three of them are confirmed, because the checkpoint
# laps out of shopping_course, desert_course and boardcross_course land on the
# Coconut Mall, Dry Dry Ruins and DK Summit drawings (5.8-15.4px mean distance
# on a 200px drawing). The rest are checked the same way when they turn up:
# `--kmp` prints the distance for each and complains about a bad one.
FOLDERS = {
    0x00: "castle_course", 0x01: "farm_course", 0x02: "kinoko_course",
    0x03: "volcano_course", 0x04: "factory_course", 0x05: "shopping_course",
    0x06: "boardcross_course", 0x07: "truck_course", 0x08: "beginner_course",
    0x09: "senior_course", 0x0A: "ridgehighway_course", 0x0B: "treehouse_course",
    0x0C: "koopa_course", 0x0D: "rainbow_course", 0x0E: "desert_course",
    0x0F: "water_course", 0x10: "old_peach_gc", 0x11: "old_mario_gc",
    0x12: "old_waluigi_gc", 0x13: "old_donkey_gc", 0x14: "old_falls_ds",
    0x15: "old_desert_ds", 0x16: "old_peach_ds", 0x17: "old_town_ds",
    0x18: "old_mario_sfc", 0x19: "old_obake_sfc", 0x1A: "old_mario_64",
    0x1B: "old_sherbet_64", 0x1C: "old_koopa_64", 0x1D: "old_donkey_64",
    0x1E: "old_koopa_gba", 0x1F: "old_heyho_gba",
}

BOX = 600                # the game's units are huge; draw courses this big


def find_kmp(root, code):
    """<root>/<folder>/course.kmp, or <root>/<folder>.kmp, or nothing."""
    folder = FOLDERS.get(code)
    if not folder:
        return None
    for candidate in (os.path.join(root, folder, "course.kmp"),
                      os.path.join(root, folder + ".kmp")):
        if os.path.isfile(candidate):
            return candidate
    return None


def from_kmp(path):
    """The real lap and the real road edges, out of the course's own file.

    Checkpoints are pairs of points across the road in order round the lap,
    starting at the finish line, so this needs no tracing and no guessing:
    the centreline is their midpoints and the road is the strip between them.
    """
    from tools.kmp import read
    course = read(path)
    checks = course.checkpoints
    if len(checks) < 4:
        return None
    kinds = [k for _, _, _, _, _, k, _, _ in checks]
    first = kinds.index(0) if 0 in kinds else 0
    checks = checks[first:] + checks[:first]

    left = [(a, b) for a, b, _, _, _, _, _, _ in checks]
    right = [(c, d) for _, _, c, d, _, _, _, _ in checks]
    mid = [((a + c) / 2, (b + d) / 2) for (a, b), (c, d) in zip(left, right)]

    xs = [p[0] for p in left + right]
    ys = [p[1] for p in left + right]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    scale = BOX / span
    pad = 20

    def place(pts):
        return [((x - min(xs)) * scale + pad, (y - min(ys)) * scale + pad)
                for x, y in pts]

    mid, left, right = place(mid), place(left), place(right)
    w = int((max(xs) - min(xs)) * scale) + 2 * pad
    h = int((max(ys) - min(ys)) * scale) + 2 * pad
    lap = smooth(resample(mid, True), True)
    return {
        "w": w, "h": h,
        "d": path_d(lap, True),
        "closed": True,
        # The road itself: out along one edge and back along the other.
        "outline": path_d(left + right[::-1], True),
        "width": round(sum(math.dist(a, b) for a, b in zip(left, right))
                       / len(left), 1),
        "length": round(length_of(lap, True), 1),
        "pieces": 1,
        "covers": 1.0,
    }


def compare(kmp, drawing):
    """Mean distance from the drawn outline to the real one, once both are
    scaled into the same box. Says whether a course file is the course the
    table says it is."""
    if not drawing:
        return None
    a = points_of(kmp["d"])
    b = points_of(drawing["d"])
    box = lambda pts, w, h: [(x / w, y / h) for x, y in pts]
    a = box(a, kmp["w"], kmp["h"])
    b = box(b, drawing["w"], drawing["h"])
    return round(100 * sum(min(math.dist(p, q) for q in a) for p in b) / len(b), 1)


def points_of(d):
    return [(float(x), float(y))
            for x, y in re.findall(r"([\d.]+)\s+([\d.]+)", d)]


HEAD = '''// Generated by tools/build_tracks.py - do not edit.
//
// `d` is the centreline: the line a lap fraction is measured along, so a racer
// 40% through a lap is drawn 40% of the way round it. Everything is in the
// coordinates of `size`.
//
// `outline` is the road as a shape - its two edges, plus a loop round anything
// the course encircles, filled even-odd. It is a path rather than a picture so
// that it stays sharp at any size; `image` is the drawing it came out of, kept
// for #/tracks to check the tracing against.
//
// `source` says where the shape came from:
//
//   "drawing"  traced from the course layout drawing in assets/tracks/source.
//              Right about the shape of the course, and arbitrary about where
//              the lap starts - the path begins wherever the tracing began,
//              not at the start line.
//
//   "course"   the game's own checkpoints, out of that course's KMP. Exact,
//              starts at the finish line, runs in the direction of travel, and
//              its outline is the real edges of the road. docs/DASHBOARD.md
//              says how to get these.

export interface Track {
  course: number;
  name: string;
  source: "drawing" | "course";
  image: string;
  outline: string;
  size: [number, number];
  d: string;
  closed: boolean;
  width: number;
}

'''

TAIL = '''
export const FALLBACK: Track = {
  course: -1,
  name: "(no outline)",
  source: "drawing",
  image: "",
  outline: "",
  size: [900, 440],
  d: "M 260 90 H 640 A 130 130 0 0 1 640 350 H 260 A 130 130 0 0 1 260 90 Z",
  closed: true,
  width: 34,
};

export const trackFor = (course: number): Track | null => TRACKS[course] ?? null;
'''


def emit(tracks):
    lines = [HEAD, "export const TRACKS: Record<number, Track> = {"]
    for code in sorted(tracks):
        t = tracks[code]
        lines.append("  %d: {" % code)
        lines.append("    course: %d," % code)
        lines.append("    name: %s," % json.dumps(t["name"]))
        lines.append("    source: %s," % json.dumps(t["source"]))
        lines.append("    image: %s," % json.dumps(t.get("image", "")))
        lines.append("    size: [%d, %d]," % (t["w"], t["h"]))
        lines.append("    closed: %s," % ("true" if t["closed"] else "false"))
        lines.append("    width: %s," % t["width"])
        lines.append("    outline: %s," % json.dumps(t.get("outline", "")))
        lines.append("    d: %s," % json.dumps(t["d"]))
        lines.append("  },")
    lines.append("};")
    lines.append(TAIL)
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("\nwrote %s (%d courses)" % (os.path.relpath(OUT, ROOT), len(tracks)))


def main():
    args = sys.argv[1:]
    kmp_root = None
    if "--kmp" in args:
        at = args.index("--kmp")
        kmp_root = args[at + 1] if len(args) > at + 1 else "."
        del args[at:at + 2]
    which = args[0] if args else ""

    tracks, missing = {}, []
    for code, name in sorted(COURSES.items()):
        if which and which.lower() not in name.lower():
            continue
        png = os.path.join(SOURCE, slug(name) + ".png")
        drawn = trace(png) if os.path.exists(png) else None

        real = None
        if kmp_root:
            found = find_kmp(kmp_root, code)
            if found:
                real = from_kmp(found)

        if real:
            off = compare(real, drawn)
            tracks[code] = dict(real, name=name, source="course")
            print("  %-24s course file: %d lap points, lap %.0fpx, road %.0fpx"
                  "%s" % (name, len(points_of(real["d"])), real["length"],
                          real["width"],
                          "" if off is None else
                          ", %.1f%% from the drawing%s"
                          % (off, "   <- CHECK, is that the right course?"
                             if off > 12 else "")))
        elif drawn:
            tracks[code] = dict(drawn, name=name, source="drawing",
                                image="/assets/tracks/source/%s.png" % slug(name))
            print("  %-24s drawing:  %3dx%-3d %s %4.0fpx lap, road %2.0fpx wide,"
                  " %d outline loop%s, covers %.2f%s%s"
                  % (name, drawn["w"], drawn["h"],
                     "loop" if drawn["closed"] else "open", drawn["length"],
                     drawn["width"], drawn["loops"],
                     "" if drawn["loops"] == 1 else "s", drawn["covers"],
                     ", %d pieces" % drawn["pieces"] if drawn["pieces"] > 1 else "",
                     "   <- CHECK" if not 0.75 <= drawn["covers"] <= 1.25 else ""))
        else:
            print("  %-24s nothing to build from" % name)
            missing.append(name)

    if which:
        print("\n(only %r - not writing tracks.ts from a partial run)" % which)
        return 0

    emit(tracks)
    if missing:
        print("missing (%d): %s" % (len(missing), ", ".join(missing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
