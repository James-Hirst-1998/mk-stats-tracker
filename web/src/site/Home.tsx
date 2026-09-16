// The front page: what this is, what it reads, and where to go next.
// The event lines are from a real tracked race (the README's example), so the
// page shows what the log actually says rather than a mock of it.

import { faceUrl } from "../ui/common";
import { itemUrl } from "../ui/Items";
import { ExampleButton } from "../ui/LoadRaces";
import { UPDATES, longDate } from "./content";
import { SiteFooter } from "./Footer";

const EVENTS = [
  { t: "0:36.917", who: "Luigi", item: "Banana", by: "Baby Luigi", what: "spin-out", out: "0.7s" },
  { t: "1:05.467", who: "Yoshi", item: "Red Shell", by: "Luigi", what: "knockback", out: "1.7s" },
  { t: "1:09.717", who: "Toad", item: "Blue Shell", by: "Bowser Jr.", what: "launched", out: "2.0s" },
  { t: "1:17.117", who: "Daisy", item: "Green Shell", by: "Rosalina", what: "knockback", out: "1.7s" },
];

const READS = [
  {
    item: "Mushroom",
    title: "Positions and laps",
    text: "Every racer, five times a second. Lap splits and finish times from the game's own clock.",
  },
  {
    item: "Triple Bananas",
    title: "Items",
    text: "What everyone picked up and used, and what the roulette had already chosen 3.5 seconds early.",
  },
  {
    item: "Red Shell",
    title: "What hit who",
    text: "Spin-out, knockback, launched, crushed. Which item, who threw it, and how long it cost.",
  },
  {
    item: "Blue Shell",
    title: "Blue shells",
    text: "Who it was aimed at, and who was only standing nearby.",
  },
  {
    item: "Star",
    title: "Replays",
    text: "Any race played back on its course, second by second.",
  },
  {
    item: "Golden Mushroom",
    title: "The whole night",
    text: "VS points across every race, running totals, and awards.",
  },
];

export function Home() {
  const latest = UPDATES[0];
  return (
    <>
      <main className="mx-auto max-w-[1200px] px-4 sm:px-5">
        <section className="grid items-center gap-10 py-10 sm:py-16 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-brand uppercase">
              Mario Kart Wii · Dolphin
            </p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight text-ink sm:text-5xl">
              Every race, settled.
            </h1>
            <p className="mt-4 max-w-xl text-lg text-ink-soft">
              Positions, lap times, every item box, and what hit who and when — read
              straight out of the game while you play.
            </p>
            <p className="mt-3 max-w-xl text-ink-soft">
              Your friend did not get hit by four blue shells. It was one blue shell, two
              bananas they drove into themselves, and a Pokey. Now there is a log.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <ExampleButton className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-deep disabled:opacity-60">
                See an example night
              </ExampleButton>
              <a
                href="#/stats"
                className="rounded-full border border-line bg-white px-5 py-2.5 text-sm font-semibold text-ink hover:bg-line-soft"
              >
                Load your own races
              </a>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line-soft px-5 py-3">
              <span className="text-[15px] font-bold tracking-tight">Mushroom Gorge</span>
              <span className="text-xs text-muted">from the race log</span>
            </div>
            <ul className="divide-y divide-line-soft">
              {EVENTS.map((e) => (
                <li key={e.t} className="flex items-center gap-3 px-5 py-3">
                  <span className="nums w-16 shrink-0 font-mono text-xs text-muted">{e.t}</span>
                  <img
                    src={faceUrl(e.who)}
                    alt=""
                    className="h-10 w-10 shrink-0 rounded-full bg-line-soft object-contain p-1.5"
                  />
                  <span className="min-w-0 flex-1 text-sm leading-snug text-ink-soft">
                    <b className="font-semibold text-ink">{e.who}</b> hit by {e.by}'s{" "}
                    {e.item}
                    <span className="block text-xs text-muted">
                      {e.what}, out {e.out}
                    </span>
                  </span>
                  <img src={itemUrl(e.item)} alt={e.item} className="h-8 w-8 shrink-0 object-contain" />
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-bold tracking-tight">What it reads</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {READS.map((r) => (
              <div key={r.title} className="card flex gap-4 px-5 py-4">
                <img src={itemUrl(r.item)} alt="" className="h-10 w-10 shrink-0 object-contain" />
                <div>
                  <h3 className="text-[15px] font-bold tracking-tight">{r.title}</h3>
                  <p className="mt-1 text-sm text-ink-soft">{r.text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-10 grid gap-3 md:grid-cols-3">
          <a href="#/setup" className="card group block px-5 py-5 hover:bg-white">
            <p className="text-xs font-semibold tracking-wide text-muted uppercase">Guide</p>
            <h3 className="mt-1 text-lg font-bold tracking-tight group-hover:text-brand">
              Get set up →
            </h3>
            <p className="mt-1 text-sm text-ink-soft">
              Homebrew on the Wii, your disc and Mii into Dolphin, four players set up,
              and tracking.
            </p>
          </a>
          <a href="#/journey" className="card group block px-5 py-5 hover:bg-white">
            <p className="text-xs font-semibold tracking-wide text-muted uppercase">Story</p>
            <h3 className="mt-1 text-lg font-bold tracking-tight group-hover:text-brand">
              How it was built →
            </h3>
            <p className="mt-1 text-sm text-ink-soft">
              A lot of wrong bytes, a five-month break, and the change that made it work.
            </p>
          </a>
          <a href="#/updates" className="card group block px-5 py-5 hover:bg-white">
            <p className="text-xs font-semibold tracking-wide text-muted uppercase">
              Latest update{latest ? ` · ${longDate(latest.date)}` : ""}
            </p>
            <h3 className="mt-1 text-lg font-bold tracking-tight group-hover:text-brand">
              {latest?.title ?? "Updates"} →
            </h3>
            <p className="mt-1 text-sm text-ink-soft">Everything that has changed, newest first.</p>
          </a>
        </section>
      </main>
      <div className="mt-6">
        <SiteFooter />
      </div>
    </>
  );
}
