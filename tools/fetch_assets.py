#!/usr/bin/env python3
"""Download the character and item art the dashboard uses.

    python3 -m tools.fetch_assets

Images come from the Super Mario Wiki via its public MediaWiki API: search the
File: namespace for "<name> MKW artwork", take the top hit, download it. Files
land in assets/characters/ and assets/items/ named by slug ("funky-kong.png"),
which is how the dashboard serves them. Existing files are never
re-downloaded, so hand-picked art survives a re-run - delete a file to refresh
it.

Needs the network; everything else in the dashboard works without it. A name
the search cannot find is reported and skipped, not an error: the frontend
falls back to an initials avatar for anything missing.
"""

import json
import os
import struct
import sys
import time
import urllib.parse
import urllib.request
import zlib
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkw.names import CHARACTERS, ITEMS
from mkw.racelog import slug

API = "https://www.mariowiki.com/api.php"
UA = {"User-Agent": "mk-stats-tracker asset fetch (personal project)"}
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets")

# Item 19 is unused and 20 is "nothing held"; Blooper has no dashboard use yet
# but costs one request, so it stays.
WANTED_ITEMS = [name for i, name in ITEMS.items() if i < 19]


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


# Known-good wiki filenames, exact-title first: search ranking is fuzzy
# enough to hand Mario a Rosalina. "<NameNoSpaces>MKW.png" is the wiki's own
# convention for MKW character art; the odd ones out are listed explicitly.
EXACT = {
    "Baby Luigi": ["Baby Luigi MSS artwork.png", "BabyLuigiMKW.png"],
    "Banana": ["MKW Banana Artwork.png", "BananaMKW.png",
               "MKW Banana Roulette.png"],
    "Mushroom": ["MKW Mushroom Artwork.png", "MKW Mushroom Roulette.png"],
    "POW Block": ["POWBlock-MKWii-Icon.png", "MKW POW Block Roulette.png"],
    # These four have no "<Name>MKW.png" face icon on the wiki, only the
    # character-select render, which is the game's own model on a black
    # background. Keyed out below.
    "Koopa Troopa": ["KoopaTroopaSelectMKW.png"],
    "Dry Bones": ["DryBonesSelectMKW.png"],
    "Dry Bowser": ["DryBowserSelectMKW.png"],
    "Bowser Jr.": ["BowserJrSelect.png"],
}

# Files that arrive as a render composited onto black rather than onto
# nothing. On a white card that is a black rectangle with a character in it.
ON_BLACK = {"Koopa Troopa", "Dry Bones", "Dry Bowser", "Bowser Jr."}


# --- taking a black background off a render ------------------------------
#
# Stdlib only, like everything else here. Enough PNG to read an 8-bit
# non-interlaced file and write an RGBA one back; nothing else is needed.

def _decode(data):
    """(w, h, bytearray of RGBA) for an 8-bit non-interlaced PNG."""
    idat, pal, head = b"", None, None
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
        i += 12 + length
    w, h, depth, color, _, _, interlace = head
    if depth != 8 or interlace:
        raise ValueError("only 8-bit, non-interlaced PNGs")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = w * channels
    raw = zlib.decompress(idat)
    rows, prev, pos = bytearray(stride * h), bytearray(stride), 0
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

    out = bytearray(w * h * 4)
    for i in range(w * h):
        k = i * channels
        if color == 0:
            r = g = b = rows[k]
            a = 255
        elif color == 4:
            r = g = b = rows[k]
            a = rows[k + 1]
        elif color in (2, 6):
            r, g, b = rows[k], rows[k + 1], rows[k + 2]
            a = rows[k + 3] if color == 6 else 255
        else:
            r, g, b = pal[rows[k] * 3:rows[k] * 3 + 3]
            a = 255
        out[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    return w, h, out


def _encode(w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)                       # no filter
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


BLACK = 55         # darker than this, reachable from the edge, is background
FRINGE = 90        # ... and above it, the edge the renderer anti-aliased


def drop_black(data):
    """Make the black a render sits on transparent.

    Background is what a flood fill from the edges reaches through dark
    pixels, not "every dark pixel": Dry Bowser's shadows and Dry Bones' eye
    sockets are as dark as the backdrop and are not it. The anti-aliased edge
    is dark because it was blended into black, so its alpha is read back off
    its brightness and the colour is un-blended by the same amount."""
    w, h, rgba = _decode(data)
    lum = [(rgba[i * 4] * 299 + rgba[i * 4 + 1] * 587 + rgba[i * 4 + 2] * 114)
           // 1000 for i in range(w * h)]

    back = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            k = y * w + x
            if lum[k] < BLACK and not back[k]:
                back[k], _ = 1, q.append(k)
    for y in range(h):
        for x in (0, w - 1):
            k = y * w + x
            if lum[k] < BLACK and not back[k]:
                back[k], _ = 1, q.append(k)
    while q:
        k = q.popleft()
        x, y = k % w, k // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                n = ny * w + nx
                if not back[n] and lum[n] < BLACK:
                    back[n] = 1
                    q.append(n)

    for k in range(w * h):
        if back[k]:
            rgba[k * 4 + 3] = 0
            continue
        x, y = k % w, k // w
        edge = any(0 <= nx < w and 0 <= ny < h and back[ny * w + nx]
                   for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        if edge and lum[k] < FRINGE:
            a = max(1, int(255 * lum[k] / FRINGE))
            rgba[k * 4 + 3] = a
            for c in range(3):
                rgba[k * 4 + c] = min(255, rgba[k * 4 + c] * 255 // a)
    return _encode(w, h, rgba)


def exact_titles(name, kind):
    got = list(EXACT.get(name, []))
    if kind == "character":
        got.append(name.replace(" ", "").replace(".", "") + "MKW.png")
    return ["File:" + t for t in got]


def title_exists(title):
    got = api({"action": "query", "titles": title,
               "prop": "imageinfo", "iiprop": "url"})
    for page in got.get("query", {}).get("pages", {}).values():
        for info in page.get("imageinfo", []):
            return info.get("url")
    return None


def find_file(query):
    got = api({"action": "query", "list": "search", "srnamespace": 6,
               "srsearch": query, "srlimit": 1})
    hits = got.get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def file_url(title):
    got = api({"action": "query", "titles": title,
               "prop": "imageinfo", "iiprop": "url"})
    pages = got.get("query", {}).get("pages", {})
    for page in pages.values():
        for info in page.get("imageinfo", []):
            return info.get("url")
    return None


def fetch(name, dest_dir, query, kind):
    dest = os.path.join(dest_dir, slug(name) + ".png")
    if os.path.exists(dest):
        return "have"
    url = title = None
    for candidate in exact_titles(name, kind):
        url = title_exists(candidate)
        if url:
            title = candidate
            break
    if not url:
        title = find_file(query)
        if not title:
            return None
        url = file_url(title)
    if not url:
        return None
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30) as r:
        data = r.read()
    if name in ON_BLACK:
        data = drop_black(data)
    with open(dest, "wb") as f:
        f.write(data)
    return title


def main():
    jobs = (
        [(n, os.path.join(ASSETS, "characters"), "%s MKW artwork" % n,
          "character") for n in CHARACTERS.values()] +
        [(n, os.path.join(ASSETS, "items"), "%s MKW artwork" % n, "item")
         for n in WANTED_ITEMS]
    )
    missing = []
    for name, dest_dir, query, kind in jobs:
        os.makedirs(dest_dir, exist_ok=True)
        try:
            got = fetch(name, dest_dir, query, kind)
        except Exception as exc:
            print("  %-22s FAILED: %s" % (name, exc))
            missing.append(name)
            continue
        if got == "have":
            print("  %-22s already present" % name)
        elif got:
            print("  %-22s <- %s" % (name, got))
            time.sleep(0.5)             # polite to the wiki
        else:
            print("  %-22s not found" % name)
            missing.append(name)
    if missing:
        print("\nmissing (%d): %s" % (len(missing), ", ".join(missing)))
        print("the dashboard shows an initials avatar for these.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
