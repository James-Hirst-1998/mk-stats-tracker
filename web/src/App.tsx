// Four screens, and the hash says which: the session, one race, that race
// played back, and the course outlines.
// A hash keeps the replay linkable without a router or a server that knows
// about routes.

import { useEffect, useState } from "react";
import { Dashboard } from "./screens/Dashboard";
import { Race } from "./screens/Race";
import { Replay } from "./screens/Replay";
import { Tracks } from "./screens/Tracks";

export type Route =
  | { screen: "dashboard"; dir: string | null }
  | { screen: "race"; dir: string; file: string }
  | { screen: "replay"; dir: string; file: string }
  | { screen: "tracks" };

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "replay" && parts[1] && parts[2])
    return { screen: "replay", dir: parts[1], file: parts[2] };
  if (parts[0] === "race" && parts[1] && parts[2])
    return { screen: "race", dir: parts[1], file: parts[2] };
  if (parts[0] === "tracks") return { screen: "tracks" };
  if (parts[0] === "s" && parts[1]) return { screen: "dashboard", dir: parts[1] };
  return { screen: "dashboard", dir: null };
}

export const go = (path: string) => {
  window.location.hash = path;
};

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  if (route.screen === "replay")
    return <Replay dir={route.dir} file={route.file} />;
  if (route.screen === "race") return <Race dir={route.dir} file={route.file} />;
  if (route.screen === "tracks") return <Tracks />;
  return <Dashboard dir={route.dir} />;
}
