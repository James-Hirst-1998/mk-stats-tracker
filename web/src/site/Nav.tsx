// The bar across the top of every page. Race and replay count as stats,
// because that is where they are opened from.

import type { Route } from "../App";

const LINKS = [
  { href: "#/stats", label: "Stats", screens: ["dashboard", "race", "replay", "tracks"] },
  { href: "#/setup", label: "Get set up", screens: ["setup"] },
  { href: "#/journey", label: "How it was built", screens: ["journey"] },
  { href: "#/updates", label: "Updates", screens: ["updates"] },
];

export function SiteNav({ route }: { route: Route }) {
  return (
    <nav className="border-b border-white/70 bg-white/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1200px] items-center gap-4 overflow-x-auto px-5 py-2.5">
        <a href="#/" className="mr-auto flex shrink-0 items-center gap-2">
          <img src="/assets/icons/blue-shell.png" alt="" className="h-7 w-7 object-contain" />
          <span className="text-[15px] font-bold tracking-tight text-ink">MK Stats</span>
        </a>
        {LINKS.map((link) => {
          const on = link.screens.includes(route.screen);
          return (
            <a
              key={link.href}
              href={link.href}
              aria-current={on ? "page" : undefined}
              className={`shrink-0 rounded-full px-3 py-1 text-sm whitespace-nowrap ${
                on
                  ? "bg-brand-soft font-semibold text-brand-deep"
                  : "text-ink-soft hover:bg-line-soft hover:text-ink"
              }`}
            >
              {link.label}
            </a>
          );
        })}
      </div>
    </nav>
  );
}
