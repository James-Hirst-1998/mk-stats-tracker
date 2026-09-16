// The site and the dashboard under one hash router: the front page, the
// written pages, the session, one race, that race played back, and the course
// outlines.
// A hash keeps the replay linkable without a router or a server that knows
// about routes, so the built site works on any static host.

import { useEffect, useState } from "react";
import { Dashboard } from "./screens/Dashboard";
import { Race } from "./screens/Race";
import { Replay } from "./screens/Replay";
import { Tracks } from "./screens/Tracks";
import { Home } from "./site/Home";
import { SiteNav } from "./site/Nav";
import { Journey, Setup } from "./site/Pages";
import { Updates } from "./site/Updates";

export type Route =
  | { screen: "home" }
  | { screen: "setup" }
  | { screen: "journey" }
  | { screen: "updates" }
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
  if (parts[0] === "stats") return { screen: "dashboard", dir: null };
  if (parts[0] === "setup") return { screen: "setup" };
  if (parts[0] === "journey") return { screen: "journey" };
  if (parts[0] === "updates") return { screen: "updates" };
  return { screen: "home" };
}

export const go = (path: string) => {
  window.location.hash = path;
};

function Screen({ route }: { route: Route }) {
  if (route.screen === "replay") return <Replay dir={route.dir} file={route.file} />;
  if (route.screen === "race") return <Race dir={route.dir} file={route.file} />;
  if (route.screen === "tracks") return <Tracks />;
  if (route.screen === "dashboard") return <Dashboard dir={route.dir} />;
  if (route.screen === "setup") return <Setup />;
  if (route.screen === "journey") return <Journey />;
  if (route.screen === "updates") return <Updates />;
  return <Home />;
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => {
      const next = parse(window.location.hash);
      // A new page starts at its top. Switching session on the stats page
      // is the same screen, so it keeps its place.
      if (next.screen !== route.screen) window.scrollTo(0, 0);
      setRoute(next);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [route.screen]);

  return (
    <>
      <SiteNav route={route} />
      <Screen route={route} />
    </>
  );
}
