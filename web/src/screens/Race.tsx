// One race, in numbers.
//
// The replay shows where everybody was; this shows what it added up to - how
// long each player spent in each position, what they picked up and threw,
// what hit them and who threw it, and every blue shell. Each widget opens
// large for the detail, and the replay is one click away.

import { useMemo } from "react";
import { useRace } from "../lib/data";
import {
  causeOf,
  hitMatrix,
  hitsTakenBy,
  itemTally,
  itemsSeen,
  playerOfSlot,
  raceDetail,
  scavengedBy,
  type Player,
  type RaceStats,
  type SessionStats,
} from "../lib/stats";
import { trackFor } from "../data/tracks";
import { useRoutes, useStarts, withRoute } from "../lib/route";
import {
  Card,
  Face,
  colorOf,
  mmss,
  nameOf,
  rankColor,
  secs,
  type NameMode,
} from "../ui/common";
import { BlueList } from "../ui/BlueShells";
import { HitMatrixTable } from "../ui/HitMatrix";
import {
  CauseStrip,
  CausesTable,
  ItemIcon,
  ItemStrip,
  ItemsTable,
  ScavengedList,
  ScavengedStrip,
} from "../ui/Items";
import { PositionTime } from "../ui/PositionTime";
import { PositionWorm } from "../ui/PositionWorm";
import { TrackShape } from "../ui/TrackShape";
import { Widget, WidgetGrid } from "../ui/Widget";

export function Race({ dir, file }: { dir: string; file: string }) {
  const { stats, log, error } = useRace(dir, file);
  const [starts] = useStarts();
  const [routes] = useRoutes();
  const mode = (localStorage.getItem("mkw.mode") as NameMode) ?? "characters";
  const race = stats?.races.find((r) => r.file === file) ?? null;

  if (error)
    return (
      <Shell dir={dir}>
        <Card className="p-5 text-sm">{error}</Card>
      </Shell>
    );
  if (!stats || !log || !race)
    return (
      <Shell dir={dir}>
        <Card className="p-5 text-sm text-muted">Loading…</Card>
      </Shell>
    );
  return (
    <Shell dir={dir}>
      <Body stats={stats} race={race} mode={mode} starts={starts} routes={routes} />
    </Shell>
  );
}

function Body({
  stats,
  race,
  mode,
  starts,
  routes,
}: {
  stats: SessionStats;
  race: RaceStats;
  mode: NameMode;
  starts: ReturnType<typeof useStarts>[0];
  routes: ReturnType<typeof useRoutes>[0];
}) {
  const players = stats.players;
  const label = (p: Player) =>
    nameOf(p, mode, race.rows.get(p.index)?.characterName ?? null);
  const face = (p: Player) => race.rows.get(p.index)?.characterName ?? p.characterName;
  const labels = new Map(players.map((p) => [p.index, label(p)]));

  const detail = useMemo(() => raceDetail(race.log, players), [race.log, players]);
  const tallies = useMemo(() => players.map((_, i) => itemTally([race], i)), [race, players]);
  const items = useMemo(() => itemsSeen([race], players), [race, players]);
  const causes = useMemo(() => players.map((_, i) => hitsTakenBy([race], i)), [race, players]);
  const scavenge = useMemo(() => players.map((_, i) => scavengedBy([race], i)), [race, players]);
  const offRoad = scavenge.reduce((n, list) => n + list.length, 0);
  const matrix = useMemo(() => hitMatrix([race], players), [race, players]);
  const hitLog = useMemo(
    () =>
      hitsIn(race, (slot) => {
        const p = playerOfSlot(slot, race.log, players);
        return p != null ? label(players[p]) : race.log.field.name(slot);
      }),
    // `label` follows `mode`, which is read once per page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [race, players, mode],
  );

  const raw = race.course != null ? trackFor(race.course) : null;
  const track = raw ? withRoute(raw, routes[raw.course], starts[raw.course]) : null;
  const rows = [...race.rows].sort((a, b) => (a[1].position ?? 99) - (b[1].position ?? 99));
  const prev = stats.races.find((r) => r.n === race.n - 1);
  const next = stats.races.find((r) => r.n === race.n + 1);
  const winnerName =
    race.winner &&
    (race.winner.player != null && mode === "names"
      ? players[race.winner.player].name
      : race.winner.characterName);
  const field = race.log.racers.length || 12;
  const idName = (id: { player: number | null; name: string }) =>
    id.player != null ? label(players[id.player]) : id.name;

  return (
    <>
      <div className="mb-5 flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="mr-auto">
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">
            Race {race.n} of {Math.max(stats.plannedRaces ?? 0, stats.races.length)} · {stats.name}
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-brand-deep">{race.courseName}</h1>
          <p className="mt-0.5 text-sm text-ink-soft">
            {race.laps ?? "?"} laps · {secs(race.duration)}
            {winnerName ? ` · won by ${winnerName}` : ""}
            {race.firstBlood &&
              ` · first blood ${
                race.firstBlood.player != null
                  ? label(players[race.firstBlood.player])
                  : race.firstBlood.name
              } at ${race.firstBlood.t}s`}
          </p>
        </div>
        <nav className="flex items-center gap-2 text-sm">
          {prev && (
            <a href={raceHref(stats.dir, prev)} className="rounded-full border border-line bg-white/80 px-3 py-1.5 hover:bg-line-soft">
              ‹ race {prev.n}
            </a>
          )}
          {next && (
            <a href={raceHref(stats.dir, next)} className="rounded-full border border-line bg-white/80 px-3 py-1.5 hover:bg-line-soft">
              race {next.n} ›
            </a>
          )}
          <a
            href={`#/replay/${stats.dir}/${encodeURIComponent(race.file)}`}
            className="rounded-full bg-brand px-4 py-1.5 font-semibold text-white hover:bg-brand-deep"
          >
            Watch the replay →
          </a>
        </nav>
      </div>

      <Card title="Players">
        <div className="overflow-x-auto">
          <table className="nums w-full text-sm">
            <thead>
              <tr className="border-y border-line-soft text-xs text-muted">
                <th className="px-5 py-2 text-left font-medium">player</th>
                {["finish", "time", "best lap", "led", "got", "thrown", "landed", "taken", "blues", "dodged", "boosts", "out"].map((h) => (
                  <th key={h} className="px-2 py-2 text-right font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([i, row]) => (
                <tr key={i} className="border-b border-line-soft last:border-0">
                  <td className="px-5 py-2 whitespace-nowrap">
                    <span className="flex items-center gap-2">
                      <Face character={row.characterName} color={colorOf(i)} label={labels.get(i) ?? ""} size={28} />
                      <span className="font-medium">{labels.get(i)}</span>
                    </span>
                  </td>
                  <td className={`px-2 py-2 text-right font-semibold ${rankColor(row.position)}`}>P{row.position ?? "-"}</td>
                  <td className="px-2 py-2 text-right">{row.finished ? mmss(row.time) : "dnf"}</td>
                  <td className="px-2 py-2 text-right">{mmss(row.bestLap)}</td>
                  <td className="px-2 py-2 text-right" title={`from the position events: ${row.ledFromEvents}s`}>{secs(row.led)}</td>
                  <td className="px-2 py-2 text-right">{row.got}</td>
                  <td className="px-2 py-2 text-right">{row.thrown}</td>
                  <td className="px-2 py-2 text-right">{row.landed}</td>
                  <td className="px-2 py-2 text-right">{row.taken}</td>
                  <td className="px-2 py-2 text-right">{row.blues}</td>
                  <td className="px-2 py-2 text-right">{row.bluesDodged}</td>
                  <td className="px-2 py-2 text-right">{row.boosts}</td>
                  <td className="px-2 py-2 text-right">{secs(row.out)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <WidgetGrid className="mt-4">
        <Widget
          title="How it unfolded"
          className="md:col-span-2"
          expanded={
            <div className="p-4">
              <PositionWorm detail={detail} labels={labels} duration={race.duration} field={field} />
              <p className="mt-1 text-xs text-muted">
                Crosses are hits taken, triangles are blue shells. Hover one to see what it was.
              </p>
            </div>
          }
        >
          <div className="px-2 pb-2">
            <PositionWorm detail={detail} labels={labels} duration={race.duration} field={field} compact />
          </div>
        </Widget>

        <Widget title="Course">
          <div className="px-3 pb-3 text-center">
            <TrackShape track={track} start={Boolean(track && (routes[track.course] || starts[track.course] || track.source === "course"))} className="mx-auto h-44 w-full" />
            <div className="mt-1 text-sm font-medium">{race.courseName}</div>
            <a
              href={`#/replay/${stats.dir}/${encodeURIComponent(race.file)}`}
              className="mt-2 inline-block rounded-full bg-brand px-4 py-1.5 text-xs font-semibold text-white hover:bg-brand-deep"
            >
              Watch the replay →
            </a>
          </div>
        </Widget>

        <Widget title="Time in each position">
          <PositionTime
            rows={players.map((p) => ({
              player: p.index,
              label: label(p),
              character: face(p),
              time: race.rows.get(p.index)?.positionTime ?? new Map(),
            }))}
            field={field}
          />
        </Widget>

        {/* Two columns on a wide screen, so the row of three under it fills. */}
        <Widget
          title="Blue shells"
          note={`${race.blueShells.length} thrown`}
          className="xl:col-span-2"
        >
          <BlueList races={[race]} players={players} mode={mode} />
        </Widget>

        <Widget
          title="Hit by"
          note={`${hitLog.length} hit${hitLog.length === 1 ? "" : "s"}`}
          expanded={
            <>
              <CausesTable players={players} causes={causes} label={label} face={face} />
              <HitLog hits={hitLog} labels={labels} />
            </>
          }
        >
          <PerPlayer players={players} label={label} face={face}>
            {(i) => <CauseStrip causes={causes[i]} />}
          </PerPlayer>
        </Widget>

        <Widget
          title="Who hit who"
          expanded={<HitMatrixTable matrix={matrix} nameOf={idName} full />}
        >
          <HitMatrixTable matrix={matrix} nameOf={idName} full={false} />
        </Widget>

        <Widget
          title="Scavenger"
          note={offRoad ? `${offRoad} off the road` : "picked up off the road"}
          expanded={<ScavengedList players={players} found={scavenge} label={label} face={face} />}
        >
          {offRoad === 0 ? (
            <ScavengedList players={players} found={scavenge} label={label} face={face} />
          ) : (
            <PerPlayer players={players} label={label} face={face}>
              {(i) => <ScavengedStrip found={scavenge[i]} />}
            </PerPlayer>
          )}
        </Widget>

        {/* The full width of the grid, the way the session screen has it. */}
        <Widget
          title="Items"
          note="picked up / thrown"
          className="md:col-span-2 xl:col-span-3"
          expanded={<ItemsTable players={players} tallies={tallies} items={items} label={label} face={face} />}
        >
          <PerPlayer players={players} label={label} face={face}>
            {(i) => <ItemStrip tally={tallies[i]} limit={19} />}
          </PerPlayer>
        </Widget>
      </WidgetGrid>
    </>
  );
}

export const raceHref = (dir: string, race: { file: string }) =>
  `#/race/${dir}/${encodeURIComponent(race.file)}`;

/** One line per player with whatever the caller puts beside their face. */
export function PerPlayer({
  players,
  label,
  face,
  children,
}: {
  players: Player[];
  label: (p: Player) => string;
  face: (p: Player) => string | null;
  children: (index: number) => React.ReactNode;
}) {
  return (
    <ul className="divide-y divide-line-soft">
      {players.map((p) => (
        <li key={p.index} className="flex items-center gap-3 px-4 py-2">
          <Face character={face(p)} color={colorOf(p.index)} label={label(p)} size={28} />
          <span className="w-20 shrink-0 truncate text-sm font-medium">{label(p)}</span>
          <span className="min-w-0 flex-1">{children(p.index)}</span>
        </li>
      ))}
    </ul>
  );
}

interface HitLine {
  t: number;
  player: number;
  cause: string;
  by: string[];
  caught: boolean;
  guess: boolean;
  out: number | null;
  place: number | null;
}

/** Every hit a tracked player took in this race, in order. `who` names a
 *  slot the way the rest of the page does, so the thrower and the victim
 *  follow the same Characters/Names choice. */
function hitsIn(race: RaceStats, who: (slot: number) => string): HitLine[] {
  const out: HitLine[] = [];
  const players = race.rows;
  for (const e of race.log.events) {
    if (e.type !== "hit" || e.after || e.slot == null) continue;
    const player = [...players].find(([, r]) => r.slot === e.slot)?.[0];
    if (player == null) continue;
    out.push({
      t: e.t,
      player,
      cause: causeOf(e),
      by: (e.by ?? []).map(who),
      caught: Boolean(e.caught),
      guess: Boolean(e.guess),
      out: e.for ?? null,
      place: (e as { place?: number }).place ?? null,
    });
  }
  return out;
}

function HitLog({ hits, labels }: { hits: HitLine[]; labels: Map<number, string> }) {
  if (!hits.length) return null;
  return (
    <div className="border-t border-line-soft">
      <h3 className="px-4 pt-3 pb-1 text-xs font-semibold tracking-wide text-muted uppercase">
        Every hit, in order
      </h3>
      <ul className="divide-y divide-line-soft">
        {hits.map((h, i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-1.5 text-sm">
            <span className="nums w-14 shrink-0 text-right text-xs text-muted">{h.t.toFixed(1)}s</span>
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colorOf(h.player) }} />
            <span className="w-20 shrink-0 truncate font-medium">{labels.get(h.player)}</span>
            {h.place != null && <span className="nums w-8 shrink-0 text-xs text-muted">P{h.place}</span>}
            <ItemIcon name={h.cause} size={20} chip={false} />
            <span className="text-ink-soft">
              {h.caught ? "caught in the blast from " : ""}
              {h.cause}
              {h.by.length ? ` (${h.by.join(", ")})` : ""}
              {h.guess ? <span className="text-muted"> · not certain</span> : null}
            </span>
            <span className="nums ml-auto shrink-0 text-xs text-muted">
              {h.out != null ? `out ${h.out.toFixed(1)}s` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Shell({ dir, children }: { dir: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
      <a href={`#/s/${dir}`} className="mb-4 inline-block text-sm text-brand hover:underline">
        ← back to stats
      </a>
      {children}
    </div>
  );
}
