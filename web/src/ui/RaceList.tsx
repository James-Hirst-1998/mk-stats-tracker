// Every race, folded up. Opening one gives the per-player numbers for that
// race and the chart of how it unfolded.

import { useMemo, useState } from "react";
import { raceDetail, type Player, type SessionStats } from "../lib/stats";
import { trackFor } from "../data/tracks";
import {
  Card,
  Face,
  colorOf,
  mmss,
  nameOf,
  rankColor,
  secs,
  type NameMode,
} from "./common";
import { TrackShape } from "./TrackShape";
import { PositionWorm } from "./PositionWorm";

export function RaceList({
  stats,
  mode,
  thru,
}: {
  stats: SessionStats;
  mode: NameMode;
  thru: number;
}) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Card title="Races" className="mt-5" note={`${stats.races.length} stored`}>
      <ul className="divide-y divide-line-soft border-t border-line-soft">
        {stats.races.map((race) => {
          const dimmed = race.n > thru;
          const isOpen = open === race.file;
          const winner = race.winner;
          return (
            <li key={race.file} className={dimmed ? "opacity-40" : ""}>
              <button
                onClick={() => setOpen(isOpen ? null : race.file)}
                className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-brand-soft/40"
              >
                <span className="nums w-6 text-sm font-semibold text-muted">
                  {race.n}
                </span>
                <TrackShape
                  track={race.course != null ? trackFor(race.course) : null}
                  className="h-14 w-14 shrink-0"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">
                    {race.courseName}
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {race.laps ?? "?"} laps · {secs(race.duration)}
                    {race.firstBlood &&
                      ` · first blood ${
                        race.firstBlood.player != null
                          ? nameOf(stats.players[race.firstBlood.player], mode, null)
                          : race.firstBlood.name
                      } at ${race.firstBlood.t}s`}
                  </span>
                </span>
                {winner && (
                  <span className="hidden items-center gap-2 sm:flex">
                    <span className="text-right">
                      <span className="block text-[11px] text-muted">won by</span>
                      <span className="block text-sm font-medium">
                        {winner.player != null && mode === "names"
                          ? stats.players[winner.player].name
                          : winner.characterName}
                      </span>
                    </span>
                    <Face
                      character={winner.characterName}
                      color={
                        winner.player != null ? colorOf(winner.player) : "#ced4da"
                      }
                      label={winner.characterName}
                      size={34}
                    />
                  </span>
                )}
                <span className="w-4 text-center text-lg leading-none text-muted">
                  {isOpen ? "−" : "+"}
                </span>
              </button>
              {isOpen && <RaceDetail stats={stats} race={race} mode={mode} />}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function RaceDetail({
  stats,
  race,
  mode,
}: {
  stats: SessionStats;
  race: SessionStats["races"][number];
  mode: NameMode;
}) {
  const detail = useMemo(
    () => raceDetail(race.log, stats.players),
    [race.log, stats.players],
  );
  const label = (p: Player) =>
    nameOf(p, mode, race.rows.get(p.index)?.characterName ?? null);
  const labels = new Map(stats.players.map((p) => [p.index, label(p)]));
  const rows = [...race.rows].sort(
    (a, b) => (a[1].position ?? 99) - (b[1].position ?? 99),
  );

  return (
    <div className="border-t border-line-soft bg-line-soft/40 px-5 py-4">
      <div className="overflow-x-auto rounded-xl border border-line bg-white">
        <table className="nums w-full text-sm">
          <thead>
            <tr className="border-b border-line-soft text-xs text-muted">
              <th className="px-3 py-2 text-left font-medium">player</th>
              <th className="px-2 py-2 text-right font-medium">finish</th>
              <th className="px-2 py-2 text-right font-medium">time</th>
              <th className="px-2 py-2 text-right font-medium">best lap</th>
              <th className="px-2 py-2 text-right font-medium">led</th>
              <th className="px-2 py-2 text-right font-medium">thrown</th>
              <th className="px-2 py-2 text-right font-medium">landed</th>
              <th className="px-2 py-2 text-right font-medium">taken</th>
              <th className="px-2 py-2 text-right font-medium">blues</th>
              <th className="px-2 py-2 text-right font-medium">boosts</th>
              <th className="px-2 py-2 text-right font-medium">out</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([i, row]) => (
              <tr key={i} className="border-b border-line-soft last:border-0">
                <td className="px-3 py-2 whitespace-nowrap">
                  <span className="flex items-center gap-2">
                    <Face
                      character={row.characterName}
                      color={colorOf(i)}
                      label={labels.get(i) ?? ""}
                      size={28}
                    />
                    <span className="font-medium">{labels.get(i)}</span>
                  </span>
                </td>
                <td
                  className={`px-2 py-2 text-right font-semibold ${rankColor(row.position)}`}
                >
                  P{row.position ?? "-"}
                </td>
                <td className="px-2 py-2 text-right">
                  {row.finished ? mmss(row.time) : "dnf"}
                </td>
                <td className="px-2 py-2 text-right">{mmss(row.bestLap)}</td>
                <td
                  className="px-2 py-2 text-right"
                  title={`from the position events: ${row.ledFromEvents}s`}
                >
                  {secs(row.led)}
                </td>
                <td className="px-2 py-2 text-right">{row.thrown}</td>
                <td className="px-2 py-2 text-right">{row.landed}</td>
                <td className="px-2 py-2 text-right">{row.taken}</td>
                <td className="px-2 py-2 text-right">{row.blues}</td>
                <td className="px-2 py-2 text-right">{row.boosts}</td>
                <td className="px-2 py-2 text-right">{secs(row.out)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1fr_240px]">
        <div className="rounded-xl border border-line bg-white p-3">
          <h3 className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">
            How it unfolded
          </h3>
          <PositionWorm
            detail={detail}
            labels={labels}
            duration={race.duration}
            field={race.log.racers.length || 12}
          />
          <p className="mt-1 text-xs text-muted">
            Crosses are hits taken, triangles are blue shells. Hover one to see
            what it was.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-white p-3 text-center">
          <TrackShape
            track={race.course != null ? trackFor(race.course) : null}
            className="mx-auto h-40 w-full"
          />
          <div className="mt-2 text-sm font-medium">{race.courseName}</div>
          <a
            href={`#/replay/${stats.dir}/${encodeURIComponent(race.file)}`}
            className="mt-2 inline-block rounded-full bg-brand px-4 py-1.5 text-xs font-semibold text-white hover:bg-brand-deep"
          >
            Watch the replay →
          </a>
        </div>
      </div>
    </div>
  );
}
