// The night, on one screen.
//
// The slider is the only global control: everything above the race list is
// "after race N", so moving it back is the same screen the night had at that
// point. Nobody is the subject of this page - the four players are drawn the
// same way, in the same order, everywhere.

import { useEffect, useMemo, useState } from "react";
import { go } from "../App";
import { useSession, useSessions } from "../lib/data";
import {
  awards as computeAwards,
  duelTotals,
  pointsSeries,
  totalsFor,
  type Player,
  type SessionStats,
} from "../lib/stats";
import { CHARACTERS, courseName } from "../data/names";
import { Awards } from "../ui/Awards";
import { Card, Face, colorOf, nameOf, secs, type NameMode } from "../ui/common";
import { PointsChart } from "../ui/PointsChart";
import { RaceList } from "../ui/RaceList";

export function Dashboard({ dir }: { dir: string | null }) {
  const sessions = useSessions();
  const chosen = dir ?? sessions[0]?.dir ?? null;
  const { stats, live, error, loading } = useSession(chosen);
  const [mode, setMode] = useState<NameMode>(
    () => (localStorage.getItem("mkw.mode") as NameMode) ?? "characters",
  );
  useEffect(() => localStorage.setItem("mkw.mode", mode), [mode]);

  // null means "follow the latest race", so a night being recorded keeps
  // moving on its own; dragging the slider back pins it.
  const [pinned, setPinned] = useState<number | null>(null);
  const count = stats?.races.length ?? 0;
  const thru = pinned == null ? count : Math.min(pinned, count);

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6">
      <TopBar
        sessions={sessions}
        chosen={chosen}
        live={live}
        stats={stats}
        mode={mode}
        setMode={setMode}
      />

      {error && (
        <Card className="mt-5 p-4 text-sm text-ink-soft">
          Could not read the races: {error}
        </Card>
      )}
      {loading && !stats && (
        <Card className="mt-5 p-4 text-sm text-muted">Reading the race logs…</Card>
      )}
      {stats && stats.races.length === 0 && (
        <Card className="mt-5 p-4 text-sm text-ink-soft">
          No races stored in this session yet.
          {live && " The one being recorded lands here when it finishes."}
        </Card>
      )}

      {stats && stats.races.length > 0 && (
        <Body stats={stats} mode={mode} thru={thru} pinned={pinned} pin={setPinned} />
      )}

      <footer className="mt-8 pb-4 text-center text-xs text-muted">
        Every number here is computed from the stored race logs by fixed rules
        (<code className="font-mono">web/src/lib/stats.ts</code>). Same files in,
        same numbers out.
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
}: {
  sessions: { dir: string; name: string; started: string; races: number }[];
  chosen: string | null;
  live: { race: number; course: number | null } | null;
  stats: SessionStats | null;
  mode: NameMode;
  setMode: (m: NameMode) => void;
}) {
  return (
    <header className="flex flex-wrap items-center gap-3">
      <div className="mr-auto">
        <h1 className="text-xl font-semibold tracking-tight">
          {stats?.name ?? "Mario Kart"}
        </h1>
        <p className="text-sm text-muted">
          {stats?.started ? new Date(stats.started).toLocaleString() : " "}
          {stats ? ` · ${stats.races.length} race${stats.races.length === 1 ? "" : "s"}` : ""}
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

      <div className="inline-flex overflow-hidden rounded-lg border border-line bg-card text-sm">
        {(["characters", "names"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 capitalize transition ${
              mode === m ? "bg-brand text-white" : "text-ink-soft hover:bg-line-soft"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <select
        value={chosen ?? ""}
        onChange={(e) => go(`/s/${e.target.value}`)}
        className="rounded-lg border border-line bg-card px-3 py-1.5 text-sm"
      >
        {sessions.map((s) => (
          <option key={s.dir} value={s.dir}>
            {s.name} · {s.started.slice(0, 10)} · {s.races} race
            {s.races === 1 ? "" : "s"}
          </option>
        ))}
      </select>
    </header>
  );
}

function Body({
  stats,
  mode,
  thru,
  pinned,
  pin,
}: {
  stats: SessionStats;
  mode: NameMode;
  thru: number;
  pinned: number | null;
  pin: (n: number | null) => void;
}) {
  const upto = useMemo(() => stats.races.slice(0, thru), [stats.races, thru]);
  const totals = useMemo(
    () => stats.players.map((_, i) => totalsFor(upto, i)),
    [stats.players, upto],
  );
  const awards = useMemo(
    () => computeAwards(upto, stats.players),
    [upto, stats.players],
  );
  const duels = useMemo(
    () => duelTotals(upto, stats.players),
    [upto, stats.players],
  );

  const label = (p: Player) =>
    nameOf(p, mode, mode === "characters" ? latestCharacter(stats, p.index) : null);

  const ranked = stats.players
    .map((p, i) => ({ player: p, total: totals[i] }))
    .sort((a, b) => b.total.points - a.total.points);

  const maxRaces = Math.max(stats.plannedRaces ?? 0, stats.races.length);

  return (
    <>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ranked.map(({ player, total }, rank) => (
          <PlayerCard
            key={player.index}
            player={player}
            label={label(player)}
            character={
              latestCharacter(stats, player.index) ?? player.characterName ?? null
            }
            total={total}
            rank={rank + 1}
            nemesis={nemesisOf(player.index, duels, stats, mode)}
          />
        ))}
      </div>

      {stats.teams.length > 0 && (
        <Card title="Constructors" className="mt-4">
          <div className="grid gap-px bg-line-soft sm:grid-cols-2">
            {[...stats.teams]
              .map((t) => ({
                team: t,
                points: t.members.reduce((n, i) => n + (totals[i]?.points ?? 0), 0),
              }))
              .sort((a, b) => b.points - a.points)
              .map(({ team, points }) => (
                <div
                  key={team.name}
                  className="flex items-center gap-3 bg-card px-4 py-3"
                >
                  <div className="flex -space-x-1">
                    {team.members.map((i) => (
                      <span
                        key={i}
                        className="h-3 w-3 rounded-full ring-2 ring-white"
                        style={{ background: colorOf(i) }}
                      />
                    ))}
                  </div>
                  <span className="font-medium">
                    {team.members.map((i) => label(stats.players[i])).join(" + ")}
                  </span>
                  <span className="nums ml-auto text-lg font-semibold">{points}</span>
                </div>
              ))}
          </div>
        </Card>
      )}

      <Card
        title="Points"
        className="mt-4"
        right={
          <span className="text-xs text-muted">
            after race {thru} of {maxRaces}
            {pinned != null && (
              <button
                onClick={() => pin(null)}
                className="ml-2 rounded border border-line px-1.5 py-0.5 hover:bg-line-soft"
              >
                follow latest
              </button>
            )}
          </span>
        }
      >
        <div className="px-3 pt-3">
          <PointsChart
            series={stats.players.map((p) => ({
              player: p.index,
              label: label(p),
              points: pointsSeries(stats.races, p.index),
            }))}
            races={thru}
            maxRaces={maxRaces}
          />
        </div>
        {stats.races.length > 1 && (
          <div className="flex items-center gap-3 border-t border-line-soft px-4 py-3">
            <span className="text-xs whitespace-nowrap text-muted">Race 1</span>
            <input
              type="range"
              min={1}
              max={stats.races.length}
              value={thru}
              onChange={(e) => {
                const n = Number(e.target.value);
                pin(n === stats.races.length ? null : n);
              }}
              className="w-full accent-brand"
            />
            <span className="text-xs whitespace-nowrap text-muted">
              {stats.races.length}
            </span>
          </div>
        )}
      </Card>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card title={`Totals · races 1–${thru}`}>
          <TotalsTable stats={stats} totals={totals} label={label} />
        </Card>
        <Awards awards={awards} players={stats.players} label={label} />
      </div>

      <RaceList stats={stats} mode={mode} thru={thru} />
    </>
  );
}

function PlayerCard({
  player,
  label,
  character,
  total,
  rank,
  nemesis,
}: {
  player: Player;
  label: string;
  character: string | null;
  total: ReturnType<typeof totalsFor>;
  rank: number;
  nemesis: string | null;
}) {
  return (
    <section className="rounded-xl border border-line bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      <div className="flex items-center gap-3">
        <Face character={character} color={colorOf(player.index)} label={label} />
        <div className="min-w-0">
          <div className="truncate font-semibold">{label}</div>
          <div className="text-xs text-muted">
            {rank === 1 ? "leading" : `${rank}${suffix(rank)} on points`}
          </div>
        </div>
        <div className="nums ml-auto text-right">
          <div
            className="text-2xl leading-none font-semibold"
            style={{ color: colorOf(player.index) }}
          >
            {total.points}
          </div>
          <div className="text-[11px] text-muted">points</div>
        </div>
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
}: {
  stats: SessionStats;
  totals: ReturnType<typeof totalsFor>[];
  label: (p: Player) => string;
}) {
  const cols = [
    ["pts", (t: (typeof totals)[0]) => t.points],
    ["wins", (t: (typeof totals)[0]) => t.wins],
    ["avg", (t: (typeof totals)[0]) => t.avgPosition ?? "-"],
    ["led", (t: (typeof totals)[0]) => secs(t.led)],
    ["thrown", (t: (typeof totals)[0]) => t.thrown],
    ["landed", (t: (typeof totals)[0]) => t.landed],
    ["taken", (t: (typeof totals)[0]) => t.taken],
    ["blues", (t: (typeof totals)[0]) => t.blues],
    ["boosts", (t: (typeof totals)[0]) => t.boosts],
  ] as const;

  return (
    <div className="overflow-x-auto">
      <table className="nums w-full text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="px-4 py-2 text-left font-medium">player</th>
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
              <tr key={p.index} className="border-t border-line-soft">
                <td className="px-4 py-2 font-medium whitespace-nowrap">
                  <span
                    className="mr-2 inline-block h-2 w-2 rounded-full align-middle"
                    style={{ background: colorOf(p.index) }}
                  />
                  {label(p)}
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
      <p className="border-t border-line-soft px-4 py-2 text-xs text-muted">
        Boosts are boost items used — mushrooms, golden, star, bullet. Trick and
        drift boosts are not in the logs.
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

/** "Most hit by Waluigi (5)", honest about ties. */
function nemesisOf(
  player: number,
  duels: { from: string; to: string; count: number }[],
  stats: SessionStats,
  mode: NameMode,
): string | null {
  const against = duels.filter((d) => d.to === String(player));
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

const suffix = (n: number) =>
  n === 1 ? "st" : n === 2 ? "nd" : n === 3 ? "rd" : "th";
