#!/usr/bin/env python3
"""Download the character and item art the dashboard uses.

    python3 -m tools.fetch_assets

Images come from the Super Mario Wiki via its public MediaWiki API: search the
File: namespace for "<name> MKW artwork", take the top hit, download it. Files
land in assets/characters/ and assets/items/ named by slug ("funky-kong.png"),
which is how tools/dashboard.py serves them. Existing files are never
re-downloaded, so hand-picked art survives a re-run - delete a file to refresh
it.

Needs the network; everything else in the dashboard works without it. A name
the search cannot find is reported and skipped, not an error: the frontend
falls back to an initials avatar for anything missing.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

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
    "POW Block": ["MKW POW Block Roulette.png", "POW Block MKW Artwork.png",
                  "MKW POW Block Artwork.png"],
}


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
