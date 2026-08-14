#!/usr/bin/env python3
"""Serve the stats dashboard for stored (and in-progress) sessions.

    python3 -m tools.dashboard                # http://localhost:8125
    python3 -m tools.dashboard --port 9000 --host 0.0.0.0

No dependencies and no sudo: everything is read from the race logs that
`tools/track.py` writes, so this can run on its own, alongside a live session,
or on a machine that has only the races/ directory.

Endpoints, all JSON:

    /api/sessions                     every session, newest first
    /api/session/<dir>                the dashboard payload (mkw.stats)
    /api/race/<dir>/<file>            one race: chart series, markers, table
    /api/replay/<dir>/<file>          progress traces + ticker for the replay

`/api/session` also carries `live`: the contents of the session's live.json
if a race is being recorded right now (tools/track.py maintains it). The
frontend polls; the payload is re-computed only when the session directory
actually changes.
"""

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkw import racelog, session as sess, stats
from mkw.names import course_name

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets")

MIME = {".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg"}


class Cache:
    """One computed payload per session, rebuilt when its directory changes.

    The fingerprint is every filename and mtime in the directory, so a race
    landing, players.json being edited, or live.json appearing all invalidate
    it. Computing takes well under a second for a night of races; the win is
    not doing it on every 2-second poll.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.got = {}

    def fingerprint(self, path):
        out = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                out.append((name, os.stat(full).st_mtime_ns))
        return tuple(out)

    def payload(self, path):
        fp = self.fingerprint(path)
        with self.lock:
            hit = self.got.get(path)
            if hit and hit[0] == fp:
                return hit[1]
        s = sess.Session(path)
        out = {"session": stats.session_stats(path, s)}
        live = os.path.join(path, "live.json")
        if os.path.isfile(live):
            try:
                with open(live) as f:
                    out["live"] = json.load(f)
                if out["live"].get("course") is not None:
                    out["live"]["course_name"] = \
                        course_name(out["live"]["course"])
            except (OSError, ValueError):
                pass                    # being rewritten; next poll gets it
        with self.lock:
            self.got[path] = (fp, out)
        return out


CACHE = Cache()


def session_dir(name):
    """Resolve a session directory name safely, or None."""
    if not name or "/" in name or name.startswith("."):
        return None
    full = os.path.join(racelog.RACES, name)
    if os.path.isfile(os.path.join(full, "session.json")):
        return full
    return None


def race_file(path, name):
    if not name or "/" in name or not name.endswith(".jsonl"):
        return None
    return name if os.path.isfile(os.path.join(path, name)) else None


class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass                            # the terminal is not an access log

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, root, rel):
        full = os.path.normpath(os.path.join(root, rel))
        if not full.startswith(os.path.abspath(root)) \
                or not os.path.isfile(full):
            return self.send_json({"error": "not found"}, 404)
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(
            os.path.splitext(full)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        # Art never changes; the app files do, and a stale app.js is a
        # confusing afternoon. Only images get told to stick around.
        self.send_header("Cache-Control",
                         "max-age=86400" if root == ASSETS else "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        try:
            return self.route(parts)
        except BrokenPipeError:
            pass
        except Exception as exc:        # a bad race file must not kill the app
            return self.send_json({"error": str(exc)}, 500)

    def route(self, parts):
        if not parts:
            return self.send_file(STATIC, "index.html")
        if parts[0] == "replay":
            return self.send_file(STATIC, "replay.html")
        if parts[0] == "assets":
            return self.send_file(ASSETS, os.path.join(*parts[1:]) if
                                  len(parts) > 1 else "")
        if parts[0] != "api":
            return self.send_file(STATIC, os.path.join(*parts))

        if parts[1:] == ["sessions"]:
            out = []
            for path in reversed(sess.find()):
                with open(os.path.join(path, "session.json")) as f:
                    meta = json.load(f)
                out.append({"dir": os.path.basename(path),
                            "name": meta.get("name"),
                            "started": meta.get("started"),
                            "races": len(meta.get("races", []))})
            return self.send_json(out)

        if len(parts) == 3 and parts[1] == "session":
            path = session_dir(parts[2])
            if not path:
                return self.send_json({"error": "no such session"}, 404)
            return self.send_json(CACHE.payload(path))

        if len(parts) == 4 and parts[1] in ("race", "replay"):
            path = session_dir(parts[2])
            name = race_file(path, parts[3]) if path else None
            if not name:
                return self.send_json({"error": "no such race"}, 404)
            s = sess.Session(path)
            fn = stats.race_detail if parts[1] == "race" else stats.replay_data
            out = fn(path, s, name)
            if out is None:
                return self.send_json({"error": "no data"}, 404)
            return self.send_json(out)

        return self.send_json({"error": "unknown endpoint"}, 404)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8125)
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 to let others on the network open it")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("dashboard -> http://%s:%d   (races from %s)"
          % ("localhost" if args.host == "127.0.0.1" else args.host,
             args.port, racelog.RACES))
    print("ctrl-c to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
