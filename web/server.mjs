// Serve a built copy: `npm run build && npm run serve`.
//
// Only needed if you want the dashboard up without Vite running - during a
// night of racing, `npm run dev` is the same thing with hot reload. No
// dependencies, so this works on a machine that only has the races directory.

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { handle, RACES, ASSETS } from "./api.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(HERE, "dist");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

function sendFile(res, root, rel) {
  const full = path.normalize(path.join(root, rel));
  if (!full.startsWith(root) || !fs.existsSync(full) || fs.statSync(full).isDirectory())
    return false;
  res.writeHead(200, {
    "Content-Type": MIME[path.extname(full)] || "application/octet-stream",
    // Art never changes; the app files do, and a stale bundle is a confusing
    // afternoon.
    "Cache-Control": root === ASSETS ? "max-age=86400" : "no-cache",
  });
  res.end(fs.readFileSync(full));
  return true;
}

const port = Number(process.argv[2] || process.env.PORT || 8125);

http
  .createServer((req, res) => {
    try {
      if (handle(req, res)) return;
      const url = new URL(req.url, "http://localhost").pathname;
      if (url.startsWith("/assets/") && sendFile(res, ASSETS, url.slice(8))) return;
      if (sendFile(res, DIST, url === "/" ? "index.html" : url)) return;
      sendFile(res, DIST, "index.html"); // client-side routes
    } catch (err) {
      res.writeHead(500, { "Content-Type": "text/plain" });
      res.end(String(err));
    }
  })
  .listen(port, "127.0.0.1", () => {
    console.log(`dashboard -> http://localhost:${port}   (races from ${RACES})`);
  });
