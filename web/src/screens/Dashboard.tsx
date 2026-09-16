// The whole session, on one screen.
//
// The slider is the only global control: everything above the race list is
// "after race N", so moving it back is the screen these races gave at that
// point. Nobody is the subject of this page - the players are drawn the same
// way, in the same order, everywhere.

import { useEffect, useMemo, useState } from "react";
import { go } from "../App";
import {
  useHasApi,
  useSession,
  useSessions,
  type SessionListing,
} from "../lib/data";
import {
  awards as computeAwards,
  cpuTotals,
  duelTotals,
  hitMatrix,
  hitsTakenBy,
  itemTally,
  itemsSeen,
  pointsSeries,
  totalsFor,
  type Player,
  type SessionStats,
  type Totals,
} from "../lib/stats";
import { CHARACTERS, courseName } from "../data/names";
import { AwardList } from "../ui/Awards";
import { BlueBars, BlueList } from "../ui/BlueShells";
import { HitMatrixTable } from "../ui/HitMatrix";
import {
  CauseStrip,
  CausesTable,
  ItemStrip,
  ItemsTable,
} from "../ui/Items";
import { LoadRaces } from "../ui/LoadRaces";
import { Players } from "../ui/Players";
import {
  Card,
  Face,
  Rank,
  Segmented,
  colorOf,
  nameOf,
  secs,
  suffix,
  type NameMode,
} from "../ui/common";
import { PointsChart } from "../ui/PointsChart";
import { RaceList } from "../ui/RaceList";
import { Widget, WidgetGrid } from "../ui/Widget";
import { PerPlayer } from "./Race";

export function Dashboard({ dir }: { dir: string | null }) {
  const { list: sessions, ready } = useSessions();
  const api = useHasApi();
  const chosen = dir ?? sessions[0]?.dir ?? null;
  const { stats, live, error, loading } = useSession(chosen);
  const [mode, setMode] = useState<NameMode>(
    () => (localStorage.getItem("mkw.mode") as NameMode) ?? "characters",
  );
  useEffect(() => localStorage.setItem("mkw.mode", mode), [mode]);

  // null means "follow the latest race", so a session being recorded keeps
  // moving on its own; dragging the slider back pins it.
  const [pinned, setPinned] = useState<number | null>(null);
  const count = stats?.races.length ?? 0;
  const thru = pinned == null ? count : Math.min(pinned, count);
  const [naming, setNaming] = useState(false);
  const [picking, setPicking] = useState(false);
  const empty = ready && sessions.length === 0;

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
      <TopBar
        sessions={sessions}
        chosen={chosen}
        live={live}
        stats={stats}
        mode={mode}
        setMode={setMode}
        naming={naming}
        setNaming={setNaming}
        picking={picking}
        setPicking={setPicking}
      />

      {empty && (
        <p className="mt-4 max-w-2xl text-sm text-ink-soft">
          No races here yet. Load a night you tracked and every number below is
          worked out from those files, in this browser.{" "}
          <a href="#/setup" className="text-brand hover:underline">
            How to track one
          </a>
          .
        </p>
      )}
      {(picking || empty) && (
        <LoadRaces onClose={empty ? undefined : () => setPicking(false)} />
      )}

      {naming && stats && chosen && (
        <Players
          dir={chosen}
          players={stats.players}
          characterOf={(p) =>
            latestCharacter(stats, p.index) ?? p.characterName ?? null
          }
          onSaved={() => {
            setNaming(false);
            setMode("names");
          }}
          onClose={() => setNaming(false)}
        />
      )}

      {stats && stats.races.length > 0 && (
        // The one control over the whole screen, above everything it changes.
        <RaceRange
          thru={thru}
          races={stats.races.length}
          planned={stats.plannedRaces}
          pinned={pinned}
          pin={setPinned}
        />
      )}

      {error && (
        <Card className="mt-6 p-5 text-sm text-ink-soft">
          Could not read the races: {error}
        </Card>
      )}
      {loading && !stats && (
        <Card className="mt-6 p-5 text-sm text-muted">Reading the race logs…</Card>
      )}
      {stats && stats.races.length === 0 && (
        <Card className="mt-6 p-5 text-sm text-ink-soft">
          No races stored in this session yet.
          {live && " The one being recorded lands here when it finishes."}
        </Card>
      )}

      {stats && stats.races.length > 0 && (
        <Body stats={stats} mode={mode} thru={thru} />
      )}

      <footer className="mt-10 pb-6 text-center text-xs text-muted">
        Every number here is computed from the stored race logs by fixed rules
        (<code className="font-mono">web/src/lib/stats.ts</code>). Same files in,
        same numbers out.
        {api && (
          <>
            {" "}·{" "}
            <a href="#/tracks" className="text-brand hover:underline">
              course outlines
            </a>
          </>
        )}
      </footer>
    </div>
  );
}

function TopBar({
  sessions,
  chosen,
  live,
  stats,
  mode,
  setMode,
  naming,
  setNaming,
  picking,
  setPicking,
}: {
  sessions: SessionListing[];
  chosen: string | null;
  live: { race: number; course: number | null } | null;
  stats: SessionStats | null;
  mode: NameMode;
  setMode: (m: NameMode) => void;
  naming: boolean;
  setNaming: (b: boolean) => void;
  picking: boolean;
  setPicking: (b: boolean) => void;
}) {
  return (
    <header className="flex flex-wrap items-end gap-x-4 gap-y-3">
      <div className="mr-auto">
        <h1 className="text-3xl font-bold tracking-tight text-brand-deep">
          {stats?.name ?? "Race stats"}
        </h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          {stats?.started ? new Date(stats.started).toLocaleString() : " "}
          {stats
            ? ` · ${stats.races.length} race${stats.races.length === 1 ? "" : "s"}`
            : ""}
          {stats?.plannedRaces ? ` of ${stats.plannedRaces}` : ""}
        </p>
      </div>

      {live && (
        <span className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700">
          <span className="live-dot inline-block h-2 w-2 rounded-full bg-red-600" />
          Race {live.race}
          {stats?.plannedRaces ? ` of ${stats.plannedRaces}` : ""} in progress
          {live.course != null ? ` — ${courseName(live.course)}` : ""}
        </span>
      )}

      {stats && (
      <>
      <Segmented
        value={mode}
        onChange={setMode}
        options={[
          { value: "characters", label: "Characters" },
          { value: "names", label: "Names" },
        ]}
      />

      <button
        onClick={() => setNaming(!naming)}
        className={`rounded-full border px-4 py-1.5 text-sm ${
          naming
            ? "border-brand bg-brand text-white"
            : "border-line bg-white/80 hover:bg-line-soft"
        }`}
      >
        Who is who
      </button>
      </>
      )}

      {sessions.length > 0 && (
        <select
          value={chosen ?? ""}
          onChange={(e) => go(`/s/${e.target.value}`)}
          className="max-w-full rounded-full border border-line bg-white/80 px-4 py-1.5 text-sm"
        >
          {sessions.map((s) => (
            <option key={s.dir} value={s.dir}>
              {s.name} · {s.started.slice(0, 10)} · {s.races} race
              {s.races === 1 ? "" : "s"}
              {s.local ? " · loaded" : ""}
            </option>
          ))}
        </select>
      )}

      {sessions.length > 0 && (
        <button
          onClick={() => setPicking(!picking)}
          className={`rounded-full border px-4 py-1.5 text-sm ${
            picking
              ? "border-brand bg-brand text-white"
              : "border-line bg-white/80 hover:bg-line-soft"
          }`}
        >
          Load races
        </button>
      )}
    </header>
  );
}

/** How many races the screen is showing.
 *
 *  It sits above everything it changes and stays there when the page scrolls,
 *  because the thing it does is change every number below it. 0 is before the
 *  first race, so a session can be watched from nothing. */
function RaceRange({
  thru,
  races,
  planned,
  pinned,
  pin,
}: {
  thru: number;
  races: number;
  planned: number | null;
  pinned: number | null;
  pin: (n: number | null) => void;
}) {
  return (
    <div className="sticky top-0 z-20 mt-5">
      <div className="card flex flex-wrap items-center gap-x-4 gap-y-2 bg-white/95 px-5 py-3">
        <span className="text-sm font-semibold whitespace-nowrap">
          {thru === 0 ? (
            <span className="text-muted">Before the first race</span>
          ) : (
            <>
              After race <span className="nums text-brand">{thru}</span>
              <span className="text-muted"> of {Math.max(planned ?? 0, races)}</span>
            </>
          )}
        </span>

        <span className="flex min-w-56 flex-1 items-center gap-3">
          <span className="text-xs whitespace-nowrap text-muted">start</span>
          <input
            type="range"
            min={0}
            max={races}
            value={thru}
            onChange={(e) => {
              const n = Number(e.target.value);
              pin(n === races ? null : n);
            }}
            className="w-full"
            aria-label="races to include"
          />
          <span className="nums text-xs whitespace-nowrap text-muted">{races}</span>
        </span>

        <button
          onClick={() => pin(null)}
          disabled={pinned == null}
          className="rounded-full border border-line px-3 py-1 text-xs whitespace-nowrap hover:bg-line-soft disabled:opacity-40"
        >
          {pinned == null ? "following the latest" : "follow latest"}
        </button>

        <span className="hidden text-[11px] whitespace-nowrap text-muted xl:inline">
          everything below is how it stood then
        </span>
      </div>
    </div>
  );
}

function Body({
  stats,
  mode,
  thru,
}: {
  stats: SessionStats;
  mode: NameMode;
  thru: number;
}) {
  const upto = useMemo(() => stats.races.slice(0, thru), [stats.races, thru]);
  const totals = useMemo(
    () => stats.players.map((_, i) => totalsFor(upto, i)),
    [stats.players, upto],
  );
  const awards = useMemo(() => computeAwards(upto, stats.players), [upto, stats.players]);
  const duels = useMemo(() => duelTotals(upto, stats.players), [upto, stats.players]);
  const tallies = useMemo(
    () => stats.players.map((_, i) => itemTally(upto, i)),
    [upto, stats.players],
  );
  const items = useMemo(() => itemsSeen(upto, stats.players), [upto, stats.players]);
  const causes = useMemo(
    () => stats.players.map((_, i) => hitsTakenBy(upto, i)),
    [upto, stats.players],
  );
  const matrix = useMemo(() => hitMatrix(upto, stats.players), [upto, stats.players]);
  const cpus = useMemo(() => cpuTotals(upto, stats.players), [upto, stats.players]);

  // Off every time the page loads, deliberately: the players are the subject
  // and the ten CPUs are the detail you go looking for.
  const [showCpus, setShowCpus] = useState(false);

  const label = (p: Player) =>
    nameOf(p, mode, mode === "characters" ? latestCharacter(stats, p.index) : null);
  const face = (p: Player) =>
    latestCharacter(stats, p.index) ?? p.characterName ?? null;
  const idName = (id: { player: number | null; name: string }) =>
    id.player != null ? label(stats.players[id.player]) : id.name;

  // Players and CPUs on one ladder when the CPUs are shown, so their points
  // say where they actually came. Equal points keeps players in front, and
  // sort is stable, so the order is the same every render.
  const standings: Standing[] = [
    ...stats.players.map((p, i) => ({
      key: String(i),
      label: label(p),
      character: face(p),
      color: colorOf(p.index),
      cpu: false,
      total: totals[i],
    })),
    ...(showCpus
      ? cpus.map((c) => ({
          key: c.key,
          label: c.name,
          character: c.name,
          color: CPU_COLOR,
          cpu: true,
          total: c.totals,
        }))
      : []),
  ].sort((a, b) => b.total.points - a.total.points || Number(a.cpu) - Number(b.cpu));

  const maxRaces = Math.max(stats.plannedRaces ?? 0, stats.races.length);
  const points = stats.players.map((p) => ({
    player: p.index,
    label: label(p),
    points: pointsSeries(stats.races, p.index),
  }));
  const hitsTaken = causes.reduce((n, c) => n + c.reduce((m, x) => m + x.count, 0), 0);

  return (
    <>
      <Card
        title="Leaderboard"
        className="mt-4"
        right={
          <button
            onClick={() => setShowCpus(!showCpus)}
            className={`rounded-full border px-3 py-1 text-xs ${
              showCpus
                ? "border-brand bg-brand text-white"
                : "border-line bg-white/80 hover:bg-line-soft"
            }`}
          >
            {showCpus ? "Hide CPUs" : "Show CPUs"}
          </button>
        }
      >
        {/* As many columns as there are cards, up to four. A fixed four
            leaves half the row empty with two players. */}
        <div className={`grid gap-3 px-5 pb-4 sm:grid-cols-2 ${LEADER_COLS[Math.min(standings.length, 4)]}`}>
          {standings.map((s, rank) => (
            <PlayerCard
              key={s.key}
              standing={s}
              rank={rank + 1}
              nemesis={nemesisOf(s.key, duels, stats, mode)}
            />
          ))}
        </div>

        {stats.teams.length > 0 && (
          <>
            <h3 className="px-5 text-xs font-semibold tracking-wide text-muted uppercase">
              Constructors
            </h3>
            <div className="grid gap-3 px-5 pt-2 pb-5 sm:grid-cols-2">
              {[...stats.teams]
                .map((t) => ({
                  team: t,
                  points: t.members.reduce((n, i) => n + (totals[i]?.points ?? 0), 0),
                }))
                .sort((a, b) => b.points - a.points)
                .map(({ team, points }) => (
                  <div
                    key={team.name}
                    className="flex items-center gap-3 rounded-xl border border-line bg-white px-4 py-3"
                  >
                    <div className="flex gap-1.5">
                      {team.members.map((i) => (
                        <Face
                          key={i}
                          character={face(stats.players[i])}
                          color={colorOf(i)}
                          label={label(stats.players[i])}
                          size={34}
                        />
                      ))}
                    </div>
                    <span className="truncate text-sm font-semibold">
                      {team.members.map((i) => label(stats.players[i])).join(" + ")}
                    </span>
                    <span className="nums ml-auto text-lg font-bold text-brand">
                      {points}
                      <span className="ml-1 text-xs font-normal text-muted">pts</span>
                    </span>
                  </div>
                ))}
            </div>
          </>
        )}
      </Card>

      <WidgetGrid className="mt-4">
        {/* Two columns wide and two rows tall, so the chart everything else
            is about is the thing you look at first; blue shells and awards
            stack in the column beside it, and the row under it is three. */}
        <Widget
          title="Points progress"
          className="md:col-span-2 xl:row-span-2"
          expanded={
            <div className="p-4">
              <PointsChart series={points} races={thru} maxRaces={maxRaces} />
            </div>
          }
        >
          <div className="px-2 pb-2">
            <PointsChart series={points} races={thru} maxRaces={maxRaces} compact />
          </div>
        </Widget>

        <Widget
          title="Blue shells"
          expandedTitle="Every blue shell"
          expanded={<BlueList races={upto} players={stats.players} mode={mode} />}
        >
          <BlueBars
            rows={stats.players
              .map((p, i) => ({
                player: p.index,
                label: label(p),
                character: face(p),
                taken: totals[i].blues,
                dodged: totals[i].bluesDodged,
              }))
              .sort((a, b) => b.taken - a.taken || b.dodged - a.dodged)}
          />
        </Widget>

        <Widget title="Awards">
          <AwardList awards={awards} players={stats.players} label={label} />
        </Widget>

        <Widget
          title="Items"
          note="picked up / thrown"
          expanded={
            <ItemsTable
              players={stats.players}
              tallies={tallies}
              items={items}
              label={label}
              face={face}
            />
          }
        >
          <PerPlayer players={stats.players} label={label} face={face}>
            {(i) => <ItemStrip tally={tallies[i]} />}
          </PerPlayer>
        </Widget>

        <Widget
          title="Hit by"
          note={`${hitsTaken} hit${hitsTaken === 1 ? "" : "s"} taken`}
          expanded={
            <CausesTable players={stats.players} causes={causes} label={label} face={face} />
          }
        >
          <PerPlayer players={stats.players} label={label} face={face}>
            {(i) => <CauseStrip causes={causes[i]} />}
          </PerPlayer>
        </Widget>

        {/* Items, hit by and who hit who are the row under the chart. The
            matrix takes both columns on a laptop, where the row is two. */}
        <Widget
          title="Who hit who"
          className="md:col-span-2 xl:col-span-1"
          expanded={<HitMatrixTable matrix={matrix} nameOf={idName} full />}
        >
          <HitMatrixTable matrix={matrix} nameOf={idName} full={false} />
        </Widget>

        <Widget title="Totals" className="md:col-span-2 xl:col-span-3">
          <TotalsTable stats={stats} totals={totals} label={label} face={face} />
        </Widget>
      </WidgetGrid>

      <RaceList stats={stats} mode={mode} thru={thru} />
    </>
  );
}

/** Leaderboard columns by player count. Written out rather than built,
 *  because Tailwind only ships the classes it can see. */
const LEADER_COLS: Record<number, string> = {
  0: "",
  1: "xl:grid-cols-1",
  2: "xl:grid-cols-2",
  3: "xl:grid-cols-3",
  4: "xl:grid-cols-4",
};

/** One card on the leaderboard: a player, or a CPU when they are shown. The
 *  two are the same card so the numbers are comparable at a glance; a CPU is
 *  greyed and tagged rather than given a shape of its own. */
interface Standing {
  key: string;
  label: string;
  character: string | null;
  color: string;
  cpu: boolean;
  total: Totals;
}

/** The colour every CPU card gets. Not one of PLAYER_COLORS, which are
 *  assigned by player index and must not be borrowed. */
const CPU_COLOR = "#adb5bd";

function PlayerCard({
  standing,
  rank,
  nemesis,
}: {
  standing: Standing;
  rank: number;
  nemesis: string | null;
}) {
  const { label, character, color, cpu, total } = standing;
  return (
    <section
      className={`rounded-xl border border-line p-4 ${cpu ? "bg-line-soft/40" : "bg-white"}`}
    >
      <div className="flex items-center gap-3">
        <Rank n={rank} />
        <Face character={character} color={color} label={label} size={52} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-semibold">{label}</span>
            {cpu && (
              <span className="shrink-0 rounded-full border border-line px-1.5 text-[10px] text-muted">
                CPU
              </span>
            )}
          </div>
          <div className="text-xs text-muted">
            {rank === 1 ? "leading" : `${rank}${suffix(rank)} on points`}
          </div>
        </div>
      </div>
      <div className="nums mt-3 flex items-baseline gap-1.5">
        <span className="text-3xl leading-none font-bold" style={{ color }}>
          {total.points}
        </span>
        <span className="text-xs text-muted">points</span>
      </div>
      <dl className="nums mt-3 grid grid-cols-3 gap-2 border-t border-line-soft pt-3 text-center">
        <Stat label="wins" value={total.wins} />
        <Stat label="avg finish" value={total.avgPosition ?? "-"} />
        <Stat label="led" value={secs(total.led)} />
      </dl>
      <p className="mt-3 line-clamp-2 text-xs text-muted" title={nemesis ?? undefined}>
        {nemesis ?? "no hits landed on them yet"}
      </p>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dd className="text-base font-semibold">{value}</dd>
      <dt className="text-[11px] text-muted">{label}</dt>
    </div>
  );
}

function TotalsTable({
  stats,
  totals,
  label,
  face,
}: {
  stats: SessionStats;
  totals: ReturnType<typeof totalsFor>[];
  label: (p: Player) => string;
  face: (p: Player) => string | null;
}) {
  const cols = [
    ["pts", (t: (typeof totals)[0]) => t.points],
    ["wins", (t: (typeof totals)[0]) => t.wins],
    ["avg", (t: (typeof totals)[0]) => t.avgPosition ?? "-"],
    ["led", (t: (typeof totals)[0]) => secs(t.led)],
    ["got", (t: (typeof totals)[0]) => t.got],
    ["thrown", (t: (typeof totals)[0]) => t.thrown],
    ["landed", (t: (typeof totals)[0]) => t.landed],
    ["taken", (t: (typeof totals)[0]) => t.taken],
    ["blues", (t: (typeof totals)[0]) => t.blues],
    ["dodged", (t: (typeof totals)[0]) => t.bluesDodged],
    ["boosts", (t: (typeof totals)[0]) => t.boosts],
    ["out", (t: (typeof totals)[0]) => secs(t.out)],
  ] as const;

  return (
    <div className="overflow-x-auto">
      <table className="nums w-full text-sm">
        <thead>
          <tr className="border-y border-line-soft text-xs text-muted">
            <th className="px-5 py-2 text-left font-medium">player</th>
            {cols.map(([name]) => (
              <th key={name} className="px-2 py-2 text-right font-medium">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stats.players
            .map((p, i) => ({ p, t: totals[i] }))
            .sort((a, b) => b.t.points - a.t.points)
            .map(({ p, t }) => (
              <tr key={p.index} className="border-b border-line-soft last:border-0">
                <td className="px-5 py-2 font-medium whitespace-nowrap">
                  <span className="flex items-center gap-2">
                    <Face
                      character={face(p)}
                      color={colorOf(p.index)}
                      label={label(p)}
                      size={24}
                    />
                    {label(p)}
                  </span>
                </td>
                {cols.map(([name, pick]) => (
                  <td key={name} className="px-2 py-2 text-right">
                    {pick(t)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
      <p className="px-5 py-3 text-xs text-muted">
        Got is items that landed in their hands; thrown is items used; landed is
        hits those caused. Dodged is blue shells aimed at them that never
        landed. Boosts are boost items used — mushrooms, golden, star, bullet;
        trick and drift boosts are not in the logs.
      </p>
    </div>
  );
}

function latestCharacter(stats: SessionStats, player: number): string | null {
  for (let i = stats.races.length - 1; i >= 0; i--) {
    const row = stats.races[i].rows.get(player);
    if (row) return row.characterName;
  }
  return null;
}

/** "Most hit by Waluigi (5)", honest about ties. `key` is a player index or
 *  a CPU's `c<character>`, the keys `duelTotals` uses. */
function nemesisOf(
  key: string,
  duels: { from: string; to: string; count: number }[],
  stats: SessionStats,
  mode: NameMode,
): string | null {
  const against = duels.filter((d) => d.to === key);
  if (!against.length) return null;
  const top = against[0].count;
  const names = against
    .filter((d) => d.count === top)
    .map((d) => nameOfKey(d.from, stats, mode));
  const shown =
    names.slice(0, 2).join(" and ") +
    (names.length > 2 ? ` +${names.length - 2} more` : "");
  return `Most hit by ${shown} (${top})`;
}

function nameOfKey(key: string, stats: SessionStats, mode: NameMode): string {
  if (/^\d+$/.test(key)) {
    const p = stats.players[Number(key)];
    return nameOf(
      p,
      mode,
      mode === "characters" ? latestCharacter(stats, p.index) : null,
    );
  }
  // A CPU: it has no name to toggle to, so it is always its character.
  const id = Number(key.slice(1));
  return CHARACTERS[id] ?? `character ${id}`;
}
