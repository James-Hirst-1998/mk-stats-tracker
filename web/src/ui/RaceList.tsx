// Every race, one line each. A line opens the race's own screen - the numbers,
// the chart of how it unfolded, and the replay.

import type { SessionStats } from "../lib/stats";
import { trackFor } from "../data/tracks";
import { raceHref } from "../screens/Race";
import { Card, Face, colorOf, nameOf, rankColor, secs, type NameMode } from "./common";
import { TrackShape } from "./TrackShape";

export function RaceList({
  stats,
  mode,
  thru,
}: {
  stats: SessionStats;
  mode: NameMode;
  thru: number;
}) {
  return (
    <Card
      title="Races"
      className="mt-4"
      note={`${stats.races.length} stored · open one for the detail`}
    >
      <ul className="divide-y divide-line-soft border-t border-line-soft">
        {stats.races.map((race) => {
          const dimmed = race.n > thru;
          const winner = race.winner;
          const finishes = [...race.rows].sort(
            (a, b) => (a[1].position ?? 99) - (b[1].position ?? 99),
          );
          return (
            <li key={race.file} className={dimmed ? "opacity-40" : ""}>
              <a
                href={raceHref(stats.dir, race)}
                className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-brand-soft/40"
              >
                <span className="nums w-6 text-sm font-semibold text-muted">{race.n}</span>
                <TrackShape
                  track={race.course != null ? trackFor(race.course) : null}
                  className="h-14 w-14 shrink-0"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{race.courseName}</span>
                  <span className="block truncate text-xs text-muted">
                    {race.laps ?? "?"} laps · {secs(race.duration)}
                    {race.firstBlood &&
                      ` · first blood ${
                        race.firstBlood.player != null
                          ? nameOf(stats.players[race.firstBlood.player], mode, null)
                          : race.firstBlood.name
                      } at ${race.firstBlood.t}s`}
                    {race.blueShells.length > 0 &&
                      ` · ${race.blueShells.length} blue${race.blueShells.length === 1 ? "" : "s"}`}
                  </span>
                </span>

                <span className="hidden flex-wrap items-center gap-2 md:flex">
                  {finishes.map(([i, row]) => (
                    <span
                      key={i}
                      className="nums inline-flex items-center gap-1 rounded-full border border-line bg-white px-1.5 py-0.5 text-xs"
                      title={`${nameOf(stats.players[i], mode, row.characterName)}: P${row.position ?? "-"}`}
                    >
                      <Face
                        character={row.characterName}
                        color={colorOf(i)}
                        label={nameOf(stats.players[i], mode, row.characterName)}
                        size={18}
                      />
                      <span className={`font-semibold ${rankColor(row.position)}`}>
                        P{row.position ?? "-"}
                      </span>
                    </span>
                  ))}
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
                      color={winner.player != null ? colorOf(winner.player) : "#ced4da"}
                      label={winner.characterName}
                      size={34}
                    />
                  </span>
                )}
                <span className="w-4 text-center text-lg leading-none text-muted">›</span>
              </a>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
