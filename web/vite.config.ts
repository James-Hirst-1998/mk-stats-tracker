import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
// @ts-expect-error - plain JS, shared with server.mjs
import { racesApi } from "./api.mjs";

// The plugin serves both /api (the race logs) and /assets (character art and
// course outlines, which live in the repo's assets/ so the recorder and the
// dashboard share one copy).
export default defineConfig({
  plugins: [react(), tailwind(), racesApi()],
  publicDir: false,
  server: { port: 8125, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true },
});
