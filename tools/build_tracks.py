#!/usr/bin/env python3
"""Turn the course layout drawings into the centreline the replay drives on.

    python3 -m tools.build_tracks                # all courses
    python3 -m tools.build_tracks luigi          # just the ones that match;
                                                 # the rest stay as they were
    python3 -m tools.build_tracks --check DIR    # ... and one PNG per course
                                                 # with the lap drawn on it

The drawing itself is what the replay shows - it is real line art of the real
course, and nothing here has to be right for the picture to be right. What is
computed here is the *centreline*: the loop up the middle of the road, in the
drawing's own pixel coordinates, so that a racer 40% through a lap can be put
40% of the way along it.

How: the black outline is the road's two edges, so the road is the enclosed
region between them. Thin that region to one pixel wide (Zhang-Suen), throw
away the stubs thinning leaves at corners, and what is left is the middle of
the road. The lap is then the shortest loop through it that goes once round
what the road encircles - shortest, so that where the road forks round an
island it takes one side and carries on - plus any stretch that goes out
and back through one junction. A drawing whose outline has a gap has no
such loop, and its lap is the longest route that passes no junction twice;
where it is drawn in several pieces they are put end to end in the order
that keeps the gaps shortest. Resample evenly and smooth.

Output is web/src/data/tracks.ts, which is checked in: the dashboard never
runs this, and re-running it on the same PNGs gives the same paths. It is
also read before it is written, so a re-traced course keeps running the way
round it did before - the start line and direction set at #/tracks were set
against that - and a filtered run leaves the other courses alone.

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


def holes_of(comp, w, h):
    """What a road piece encircles: every pixel not reachable from the edge of
    the drawing without crossing the piece, as one set.

    The piece is grown a few pixels first so the flood cannot slip along its
    own ink outline. GBA Shy Guy Beach joins the beach's inner and outer edges
    with one drawn line, and without this that line lets the flood in and the
    island reads as outside."""
    grow = 3
    blocked = bytearray(w * h)
    for k in comp:
        x, y = k % w, k // w
        for dy in range(-grow, grow + 1):
            ny = y + dy
            if 0 <= ny < h:
                for dx in range(-grow, grow + 1):
                    nx = x + dx
                    if 0 <= nx < w:
                        blocked[ny * w + nx] = 1
    seen = bytearray(w * h)
    q = deque()
    for k in [y * w + x for x in range(w) for y in (0, h - 1)] + \
             [y * w + x for y in range(h) for x in (0, w - 1)]:
        if not blocked[k] and not seen[k]:
            seen[k] = 1
            q.append(k)
    while q:
        k = q.popleft()
        x, y = k % w, k // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                n = ny * w + nx
                if not blocked[n] and not seen[n]:
                    seen[n] = 1
                    q.append(n)
    inside = bytearray(1 if not blocked[k] and not seen[k] else 0
                       for k in range(w * h))
    return components(inside, w, h)


def shortest(g, start, goal, banned, w):
    """Dijkstra over the skeleton, in pixels of length, keeping off the edges
    in `banned`. Returns the pixel list start..goal, or None."""
    import heapq
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, k = heapq.heappop(heap)
        if k == goal:
            path = [k]
            while path[-1] != start:
                path.append(prev[path[-1]])
            return path[::-1]
        if d > dist[k]:
            continue
        for n in g[k]:
            if (k, n) in banned:
                continue
            step = 1.0 if (k % w == n % w or k // w == n // w) else math.sqrt(2)
            if d + step < dist.get(n, math.inf):
                dist[n] = d + step
                prev[n] = k
                heapq.heappush(heap, (d + step, n))
    return None


def winding_cycle(g, hole, w):
    """The shortest loop in the skeleton that goes once round `hole`, or None.

    Cut the drawing along a ray from a point in the hole to its right-hand
    edge. A loop going once round the hole crosses that ray exactly once, so
    it is the shortest path between the two pixels of one crossing that stays
    off every crossing, plus the crossing itself. Shortest rather than
    longest on purpose: where the road forks round an island, or opens into a
    hedge maze (DS Peach Gardens) or a field of mole holes (Moo Moo Meadows),
    the longest loop goes round the island or zigzags through the obstacles,
    and the shortest takes one side and carries on."""
    cx = sum(k % w for k in hole) / len(hole)
    cy = sum(k // w for k in hole) / len(hole)
    origin = min(hole, key=lambda k: (k % w - cx) ** 2 + (k // w - cy) ** 2)
    px, py = origin % w, origin // w
    cut = set()
    for a, near in g.items():
        if a // w != py or a % w <= px:
            continue
        for b in near:
            if b // w == py + 1 and b % w > px:
                cut.add((a, b))
                cut.add((b, a))
    best = None
    for a, b in cut:
        if a // w != py:
            continue
        path = shortest(g, b, a, cut, w)
        if path and (best is None or len(path) < len(best)):
            best = path
    return best


def longest_simple(g, start=None, back=False, every=False):
    """The longest route through the skeleton that passes no junction twice,
    as pixels: from `start` back to `start` if `back`, otherwise between two
    dead ends. With `every`, the longest route between each pair of dead
    ends, longest first. None if the skeleton has no junctions and no ends.

    Passing no junction twice is what stops the route going round an island
    and carrying on, which is what the old longest route did on Daisy Circuit
    (it reused no chain, but it did reuse junctions). Longest rather than
    shortest for an open stretch because the road can be drawn with a
    shortcut through it: Maple Treeway's cannon is drawn as road from the
    bottom of the treetops to the top, and the shortest way is up that."""
    edges, _ = chains(g)
    if not edges:
        return None
    adj = {}
    for i, e in enumerate(edges):
        adj.setdefault(e[0], []).append((e[-1], i, e))
        adj.setdefault(e[-1], []).append((e[0], i, list(reversed(e))))
    ends = [k for k in adj if len(adj[k]) == 1]
    if start is not None:
        if start not in adj:
            return None
        starts = [start]
    elif back:
        starts = list(adj)
    else:
        starts = ends or list(adj)
    length = lambda route: sum(len(c) for c in route)
    best, budget = {}, 200000
    for s in starts:
        stack = [(s, [], -1, frozenset([s]))]
        while stack and budget > 0:
            budget -= 1
            node, route, last, seen = stack.pop()
            if not back and route and (node in ends or not ends):
                key = (min(s, node), max(s, node))
                if length(route) > length(best.get(key, [])):
                    best[key] = route
            for nxt, i, chain in adj[node]:
                if i == last:
                    continue
                if nxt == s and back:
                    if length(route) + len(chain) > length(best.get(s, [])):
                        best[s] = route + [chain]
                elif nxt not in seen:
                    stack.append((nxt, route + [chain], i, seen | {nxt}))
    routes = sorted(best.values(), key=length, reverse=True)
    if not routes:
        return None
    out = []
    for route in routes:
        pixels = []
        for chain in route:
            pixels += chain[1:] if pixels else chain
        out.append(pixels)
    return out if every else out[0]


def with_hairpins(g, lap, w):
    """Splice in the stretches the lap leaves out because they go out and
    back through one junction.

    GCN Peach Beach's road leaves the ring at one point, goes round two
    islands and comes back to the same point. No route that passes a
    junction once can take that, so: whatever the lap missed that hangs off
    it at exactly one pixel and contains a loop is one of these, and the lap
    goes round it - the longest way, so it takes the outside of the islands -
    and comes back to where it left. A tree hanging off one pixel is a spur
    and is left alone."""
    on = set(lap)
    rest = {k for k in g if k not in on}
    seen = set()
    for k0 in list(rest):
        if k0 in seen:
            continue
        piece, q = {k0}, [k0]
        seen.add(k0)
        while q:
            for n in g[q.pop()]:
                if n in rest and n not in seen:
                    seen.add(n)
                    piece.add(n)
                    q.append(n)
        attach = {n for k in piece for n in g[k] if n in on}
        if len(attach) != 1:
            continue
        a = next(iter(attach))
        sub = {k: [n for n in g[k] if n in piece or n == a] for k in piece}
        sub[a] = [n for n in g[a] if n in piece]
        if sum(len(v) for v in sub.values()) // 2 < len(sub):
            continue                       # a tree: a spur
        # The loop in it, the longest way round, and the stem from the lap
        # to the loop: out along the stem, round, and back along the stem.
        ring = longest_simple(sub, back=True)
        if ring is None:                   # a plain ring touching the lap at a
            ring, prev = [a], None
            while True:
                near = [n for n in sub[ring[-1]] if n != prev]
                if not near:
                    break
                prev = ring[-1]
                ring.append(near[0])
                if near[0] == a:
                    break
        if len(ring) < 3 or ring[0] != ring[-1]:
            continue
        ring = ring[:-1]
        stem, prev, q = None, {a: None}, deque([a])
        while q and stem is None:
            k = q.popleft()
            if k in ring:
                stem = [k]
                while prev[stem[-1]] is not None:
                    stem.append(prev[stem[-1]])
                stem.reverse()
                break
            for n in sub[k]:
                if n not in prev:
                    prev[n] = k
                    q.append(n)
        if stem is None:
            continue
        j = ring.index(stem[-1])
        detour = stem + ring[j + 1:] + ring[:j + 1] + stem[-2::-1]
        i = lap.index(a)
        lap = lap[:i + 1] + detour[1:] + lap[i + 1:]
        on = set(lap)
    return lap


def lap_of(g, hole, w):
    """(pixels, closed) for one road piece: a loop once round what the piece
    encircles if the skeleton has one, otherwise the longest open path.

    A drawing whose outline has a gap - or whose road is cut where it crosses
    over itself, since the bridge is drawn as a break - has no loop, and its
    open path is still one lap long and still the right shape."""
    if not g:
        return [], False, []
    loop = winding_cycle(g, hole, w) if hole else None
    if loop:
        return with_hairpins(g, loop, w), True, []
    paths = longest_simple(g, every=True)
    if paths:
        # An open stretch with more than two dead ends can be crossed more
        # than one way, and which is right depends on where the neighbouring
        # pieces are: the stitching gets the ones nearly as long as the
        # longest to choose from.
        paths = [with_hairpins(g, p, w) for p in paths[:3]
                 if len(p) >= 0.6 * len(paths[0])]
        return paths[0], False, paths[1:]
    start = next(iter(g))                  # no junctions and no ends: a ring
    loop, prev = [start], None
    while True:
        near = [n for n in g[loop[-1]] if n != prev]
        if not near or near[0] == start:
            break
        prev = loop[-1]
        loop.append(near[0])
    return loop, True, []


def medial_width(comp, pixels, w, h):
    """How wide the road is along the lap: twice the typical distance from a
    lap pixel to the edge of the piece. Area over skeleton length says the
    same thing for a ribbon, but a blob thins to a branching skeleton long
    enough to make it look narrow - Koopa Cape's river is a triangle 30px
    across that came out as a 5px road."""
    dist = {}
    q = deque()
    for k in comp:
        x, y = k % w, k // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or ny * w + nx not in comp:
                dist[k] = 1
                q.append(k)
                break
    while q:
        k = q.popleft()
        x, y = k % w, k // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            n = ny * w + nx
            if 0 <= nx < w and 0 <= ny < h and n in comp and n not in dist:
                dist[n] = dist[k] + 1
                q.append(n)
    along = sorted(dist.get(k, 1) for k in pixels)
    return (2 * along[len(along) // 2] if along else 0), 2 * max(dist.values(), default=0)


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
MIN_PIECE = 0.05         # ignore road pieces this much shorter than the longest
MIN_HOLE = 0.30          # a hole this much of the piece's own area is the course interior


def stitch(pieces, w, h):
    """Join the road up where the drawing leaves gaps in it.

    Several courses are not drawn as one continuous ribbon: Rainbow Road and
    Grumble Volcano have gaps you jump, Mushroom Gorge has the bouncy
    mushrooms, Koopa Cape goes into a pipe. Each stretch of road comes back as
    its own piece, and a lap is all of them end to end, in the order and the
    directions that make the distance off the road shortest in total: the
    gaps between pieces, plus whatever road a piece skips when a shorter way
    across it fits its neighbours better. Taking the nearest piece each time
    instead sent Grumble Volcano and Rainbow Road straight across the
    drawing: the nearest piece is not always the next one.

    `pieces[i]` is the ways across piece i, longest first. The tour is a
    round trip, because the course is, and is then cut at its widest gap;
    whether that gap is small enough to call the lap closed is decided by
    the caller. Eight pieces at most, so every order is affordable
    (Held-Karp over piece, way across and direction)."""
    n = len(pieces)
    # A state is (piece, way across, direction); head and tail are where the
    # lap enters and leaves the piece in that state.
    states = [(i, c, o) for i in range(n) for c in range(len(pieces[i])) for o in (0, 1)]
    head = lambda s: pieces[s[0]][s[1]][-s[2]]
    tail = lambda s: pieces[s[0]][s[1]][s[2] - 1]
    skipped = lambda s: len(pieces[s[0]][0]) - len(pieces[s[0]][s[1]])
    step = lambda a, b: math.dist(tail(a), head(b)) + skipped(b)

    tour, tour_cost = None, math.inf
    for first in [s for s in states if s[0] == 0]:
        best = {(1, first): (skipped(first), None)}
        for mask in range(1, 1 << n):
            for a in [s for s in states if mask >> s[0] & 1 and (mask, s) in best]:
                cost = best[mask, a][0]
                for b in [s for s in states if not mask >> s[0] & 1]:
                    key = (mask | 1 << b[0], b)
                    c = cost + step(a, b)
                    if key not in best or c < best[key][0]:
                        best[key] = (c, (mask, a))
        full = (1 << n) - 1
        for last in [s for s in states if (full, s) in best]:
            c = best[full, last][0] + step(last, first)
            if c < tour_cost:
                order, at = [], (full, last)
                while at is not None:
                    order.append(at[1])
                    at = best[at][1]
                tour, tour_cost = order[::-1], c

    gaps = [math.dist(tail(a), head(b)) for a, b in zip(tour, tour[1:] + tour[:1])]
    cut = max(range(n), key=lambda i: gaps[i])
    tour = tour[cut + 1:] + tour[:cut + 1]
    chain = []
    for i, c, o in tour:
        chain += pieces[i][c][::-1] if o else pieces[i][c]
    return chain


def open_ring(ring, others):
    """A piece that is a loop on its own - the corkscrew before the finish of
    N64 Bowser's Castle, the diamond the road forks round in Bowser's Castle -
    is entered from one neighbouring piece and left towards another. Cut it at
    the points nearest those two, keeping the longer way round: for the
    corkscrew both are the same point and that is the whole loop."""
    ends = [e for p in others for e in (p[0], p[-1])]
    near = sorted(range(len(ring)),
                  key=lambda i: min(math.dist(ring[i], e) for e in ends))
    a = near[0]
    b = next((i for i in near if math.dist(ring[i], ring[a]) > 3), a)
    if a == b:
        return ring[a:] + ring[:a + 1]
    a, b = min(a, b), max(a, b)
    inner, outer = ring[a:b + 1], ring[b:] + ring[:a + 1]
    return inner if len(inner) >= len(outer) else outer[::-1]


def duplicate(f, pieces, width):
    """Is piece `f` the other way past something another piece already goes
    past? Decided by where its ends land: both on the middle of another
    piece, well away from that piece's ends, with about as much of that
    piece between them as `f` is long - the other way round an obstacle.
    Mushroom Gorge draws the cave and the road past it side by side, and the
    lap takes one of them.

    Ends landing on another piece's *ends* mean nothing: Koopa Cape's
    hairpin by the start and the straight it hangs off share both ends, and
    both are driven. Nor do ends landing on the middle of a piece with most
    of that piece between them: GCN Waluigi Stadium's middle straight runs
    from one bridge to the other, and the rest of the course is what the
    bridges carry."""
    edge = max(2 * width, 6)
    a, b = f["pts"][0], f["pts"][-1]
    for o in pieces:
        if o is f or o["closed"]:
            continue
        pts = o["pts"]
        near = [min(range(len(pts)), key=lambda i: math.dist(pts[i], e)) for e in (a, b)]
        if any(math.dist(pts[i], e) >= edge for i, e in zip(near, (a, b))):
            continue
        margin = 3 * width
        if all(margin < i < len(pts) - margin for i in near) \
                and abs(near[0] - near[1]) < 2 * len(f["pts"]):
            return True
    return False


def trace(path):
    w, h, gray, alpha = decode_png(path)
    mask = road_mask(w, h, gray, alpha)
    found = []
    for comp in components(mask, w, h)[:8]:
        if len(comp) < 300:
            continue
        skeleton = thin(comp, w, h)
        width = len(comp) / max(len(skeleton), 1)
        holes = holes_of(comp, w, h)
        # The course interior is the biggest thing the piece goes round, and
        # is big; the ring round a roundabout island is neither.
        hole = holes[0] if holes and len(holes[0]) >= MIN_HOLE * len(comp) else None
        holes = {k for hole_ in holes for k in hole_}
        # What the course encircles is wide and encloses nothing. The one
        # road wider than the limit is GBA Shy Guy Beach, a beach the width
        # of the island it goes round, and the island is what lets it in.
        if width > MAX_ROAD_WIDTH and not hole:
            continue
        pixels, closed, others = lap_of(prune(graph_of(skeleton, w, h), w), hole, w)
        if len(pixels) < 40:
            continue
        xy = lambda pixels: [(k % w, k // w) for k in pixels]
        across, deep = medial_width(comp, pixels, w, h)
        found.append({"pts": xy(pixels), "ways": [xy(p) for p in others],
                      "closed": closed, "comp": comp, "skeleton": len(skeleton),
                      "width": width, "holes": holes, "ring": hole is not None,
                      "across": across})
    if not found:
        return None

    main = max(found, key=lambda f: len(f["pts"]))
    if main["closed"]:
        # The longest piece is already a lap, so nothing else in the drawing
        # is road the lap runs through: Daisy Circuit's courtyard and Dry Dry
        # Ruins' interior came out as road pieces and were being stitched on.
        keep = [main]
    else:
        keep = [main]
        for f in found:
            if f is main or len(f["pts"]) < len(main["pts"]) * MIN_PIECE:
                continue
            # Inside what the main piece goes round, or much wider than it:
            # an island, not road. So is a blob: a ribbon's area is about
            # its length times its width, and Koopa Cape's river - the
            # triangle inside the hairpin by the start - is 1.7 times that,
            # against 1.0-1.45 for every real stretch of road. A piece that
            # is a ring round something is measured along the ring and is
            # not a blob whatever that ratio says.
            # "Inside" is measured with the main piece grown a few pixels,
            # which closes the breaks drawn where the road bridges itself,
            # so on GCN Waluigi Stadium the stretch between two bridges
            # reads as inside the rest. A piece whose end meets an end of
            # the main piece is the next stretch of road, wherever it sits.
            inside = sum(1 for k in f["comp"] if k in main["holes"])
            joins = any(math.dist(a, b) < max(2 * main["across"], 6)
                        for a in (f["pts"][0], f["pts"][-1])
                        for b in (main["pts"][0], main["pts"][-1]))
            fill = len(f["comp"]) / (len(f["pts"]) * max(f["across"], 1))
            if (inside > len(f["comp"]) / 2 and not joins) \
                    or f["across"] > 2 * main["across"] \
                    or (fill > 1.6 and not f["ring"]):
                continue
            keep.append(f)
        for f in keep:
            if f["closed"]:
                f["pts"] = open_ring(f["pts"], [o["pts"] for o in keep
                                                if o is not f and not o["closed"]])
        keep = [f for f in keep if f is main or not duplicate(f, keep, main["across"])]
        # A gap bigger than this is not the same road. Rainbow Road has the
        # widest real one, at a third of the drawing's diagonal.
        limit = 0.40 * math.hypot(w, h)
        keep = [f for f in keep if f is main or any(
            math.dist(a, b) <= limit
            for o in keep if o is not f
            for a in (f["pts"][0], f["pts"][-1]) for b in (o["pts"][0], o["pts"][-1]))]

    width = (sum(len(f["comp"]) for f in keep)
             / max(sum(f["skeleton"] for f in keep), 1))
    if len(keep) == 1:
        pts, closed = main["pts"], main["closed"]
    else:
        pts = stitch([[f["pts"]] + f["ways"] for f in keep], w, h)
        closed = False
    if not closed:
        # Two ends that meet are a loop that was cut - by the bridge drawn
        # where a course crosses over itself, or by the start line.
        closed = math.dist(pts[0], pts[-1]) < max(4 * width, 0.08 * math.hypot(w, h))

    raw = pts
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
        "pts": pts,
        "closed": closed,
        "outline": outline_d(loops),
        "width": round(width, 1),
        "length": round(length, 1),
        "pieces": len(keep),
        "loops": len(loops),
        "covers": round(length / max(road, 1), 2),
        # For --check only: the lap before resampling, so a jump between
        # pieces is still a long step, and the road the outline was cut from.
        "raw": raw,
        "road": {k for f in keep for k in f["comp"]},
    }


def same_way(old, new):
    """Does `new` run the same way round the course as `old`?

    The start line and the racing direction are set by hand at #/tracks
    against whichever path tracks.ts held at the time, and the direction is
    kept as a flag meaning "the path runs against the race". That flag only
    survives a re-trace if the new path runs the same way round as the old
    one, so every rebuild is turned to match what was there before.

    Measured by walking the new path and asking where each point's nearest
    old point is: same way round and those land later and later along the
    old path. Not the sign of the enclosed area, because a figure-eight
    (Mario Circuit) has two lobes of opposite sign that nearly cancel."""
    n = len(old)
    forward = backward = 0
    prev = None
    for p in new[::max(1, len(new) // 60)]:
        j = min(range(n), key=lambda i: math.dist(old[i], p))
        if prev is not None:
            step = (j - prev) % n
            if 0 < step < n / 2:
                forward += 1
            elif step > n / 2:
                backward += 1
        prev = j
    return forward >= backward


def read_existing():
    """What tracks.ts holds now, per course, in the shape emit() takes."""
    if not os.path.exists(OUT):
        return {}
    text = open(OUT).read()
    out = {}
    for m in re.finditer(r"^  (\d+): \{\n(.*?)^  \},", text, re.S | re.M):
        code, body = int(m.group(1)), m.group(2)
        field = lambda name: re.search(r"^    %s: (.*),$" % name, body, re.M).group(1)
        size = json.loads(field("size"))
        out[code] = {
            "name": json.loads(field("name")), "source": json.loads(field("source")),
            "image": json.loads(field("image")), "w": size[0], "h": size[1],
            "closed": field("closed") == "true", "width": float(field("width")),
            "outline": json.loads(field("outline")), "d": json.loads(field("d")),
        }
    return out


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
    b = drawing["pts"]
    box = lambda pts, w, h: [(x / w, y / h) for x, y in pts]
    a = box(a, kmp["w"], kmp["h"])
    b = box(b, drawing["w"], drawing["h"])
    return round(100 * sum(min(math.dist(p, q) for q in a) for p in b) / len(b), 1)


def points_of(d):
    return [(float(x), float(y))
            for x, y in re.findall(r"([\d.]+)\s+([\d.]+)", d)]


# --- check images ----------------------------------------------------------
#
# `--check <dir>` writes one PNG per course: the drawing scaled up with the
# traced lap drawn over it, a green dot at the path's first point and the
# 10%..90% marks numbered. Numbers like `covers` cannot tell a lap that goes
# once round from one that goes round an island and back; a picture can.

CHECK_SCALE = 4

DIGITS = {                     # 3x5 bitmap font, one string per row
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"), "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"), "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"), "9": ("111", "101", "111", "001", "111"),
}


def encode_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def check_image(png, result, out):
    w, h, gray, alpha = decode_png(png)
    S = CHECK_SCALE
    W, H = w * S, h * S
    rgb = bytearray(b"\xff" * (W * H * 3))

    def put(x, y, colour):
        if 0 <= x < W and 0 <= y < H:
            k = (y * W + x) * 3
            rgb[k:k + 3] = bytes(colour)

    def blob(x, y, r, colour):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    put(x + dx, y + dy, colour)

    def line(a, b, colour, r=1):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
        for i in range(n + 1):
            f = i / n
            blob(round(a[0] + (b[0] - a[0]) * f),
                 round(a[1] + (b[1] - a[1]) * f), r, colour)

    def text(x, y, s, colour, scale=2):
        for ch in s:
            for row, bits in enumerate(DIGITS.get(ch, ())):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        for dy in range(scale):
                            for dx in range(scale):
                                put(x + col * scale + dx, y + row * scale + dy, colour)
            x += 4 * scale

    road = result.get("road", set())
    for y in range(h):
        for x in range(w):
            k = y * w + x
            if alpha[k] <= INK_ALPHA:
                continue
            g = 40 if gray[k] < INK_LUM else 160 + gray[k] * 95 // 255
            colour = (255, 245, 190) if k in road and g > 40 else (g, g, g)
            for dy in range(S):
                for dx in range(S):
                    put(x * S + dx, y * S + dy, colour)

    scaled = lambda p: (p[0] * S + S / 2, p[1] * S + S / 2)
    pts = [scaled(p) for p in result["pts"]]
    n = len(pts)
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if result["closed"] else [])
    for a, b in segs:
        line(a, b, (220, 40, 40))
    # A jump between pieces is a long step in the lap before resampling
    # spreads it evenly. Drawn in magenta so it cannot hide in the red.
    raw = [scaled(p) for p in result.get("raw", [])]
    jumps = list(zip(raw, raw[1:])) + ([(raw[-1], raw[0])] if result["closed"] and raw else [])
    for a, b in jumps:
        if math.dist(a, b) > 4 * S:
            line(a, b, (255, 0, 255), 2)
    for k in range(1, 10):
        i = k * n // 10
        x, y = round(pts[i][0]), round(pts[i][1])
        blob(x, y, 4, (30, 90, 220))
        text(x + 6, y - 6, str(k), (0, 0, 0), 2)
    x, y = round(pts[0][0]), round(pts[0][1])
    blob(x, y, 7, (20, 170, 60))
    text(x + 9, y - 6, "0", (0, 0, 0), 2)
    encode_png(out, W, H, rgb)


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
    check = None
    if "--check" in args:
        at = args.index("--check")
        check = args[at + 1] if len(args) > at + 1 else "check"
        del args[at:at + 2]
        os.makedirs(check, exist_ok=True)
    which = args[0] if args else ""

    # What is there now: a filtered run keeps the other courses as they were,
    # and every re-traced course is turned to run the way its old path did.
    old = read_existing()
    tracks, missing = {}, []
    for code, name in sorted(COURSES.items()):
        if which and which.lower() not in name.lower():
            if code in old:
                tracks[code] = old[code]
            continue
        png = os.path.join(SOURCE, slug(name) + ".png")
        drawn = trace(png) if os.path.exists(png) else None
        if drawn:
            was = old.get(code)
            if was and was["source"] == "drawing" and \
                    not same_way(points_of(was["d"]), drawn["pts"]):
                drawn["pts"].reverse()
                drawn["raw"].reverse()
            drawn["d"] = path_d(drawn["pts"], drawn["closed"])

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
            if check:
                check_image(png, drawn, os.path.join(check, slug(name) + ".png"))
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
        print("\n(only %r - the other courses are as they were)" % which)
    emit(tracks)
    if missing:
        print("missing (%d): %s" % (len(missing), ", ".join(missing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
