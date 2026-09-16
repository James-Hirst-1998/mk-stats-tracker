import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
// @ts-expect-error - plain JS, shared with server.mjs
import { racesApi, ASSETS } from "./api.mjs";

/** The art goes into the build, so the built site stands on its own on a
 *  static host. The layout drawings in tracks/source are left out: only the
 *  #/tracks editor shows them, and that needs the local server to save. */
function copyAssets(): Plugin {
  return {
    name: "mkw-copy-assets",
    apply: "build",
    writeBundle(options) {
      fs.cpSync(ASSETS, path.join(options.dir!, "assets"), {
        recursive: true,
        filter: (src) => !src.startsWith(path.join(ASSETS, "tracks", "source")),
      });
    },
  };
}

// The plugin serves both /api (the race logs) and /assets (character art and
// course outlines, which live in the repo's assets/ so the recorder and the
// dashboard share one copy).
export default defineConfig({
  plugins: [react(), tailwind(), racesApi(), copyAssets()],
  // public/ holds the example night the site offers to people with no races
  // of their own; it is served at /examples and copied into the build.
  publicDir: "public",
  server: { port: 8125, strictPort: true },
  // Vite's own bundles go under app/, because assets/ is the repo's art.
  build: { outDir: "dist", emptyOutDir: true, assetsDir: "app" },
});
