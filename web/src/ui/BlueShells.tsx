// Blue shells: per player, the ones that got them, the ones that caught them
// next to somebody else, and the ones they dodged; and every one thrown.
//
// A shell is aimed at whoever it locked on to, the leader about two seconds
// before it went off. A dodge is a shell that locked on and did not get them -
// a cannon, a well-timed Mushroom, a Star, a Bill, or crossing the line. It is
// derived, not read, and the rules are in stats.ts (`settleLaunches`).

import type { BlueShell, Player, RaceStats } from "../lib/stats";
import { playerOfSlot } from "../lib/stats";
import { Face, colorOf, nameOf, type NameMode } from "./common";

export interface BlueRow {
  player: number;
  label: string;
  character: string | null;
  hit: number;
  caught: number;
  dodged: number;
}

export function BlueBars({ rows }: { rows: BlueRow[] }) {
  const all = (r: BlueRow) => r.hit + r.caught + r.dodged;
  const top = Math.max(1, ...rows.map(all));
  if (rows.every((r) => all(r) === 0))
    return (
      <p className="px-4 py-6 text-sm text-muted">
        No blue shell has gone for any of them yet.
      </p>
    );
  return (
    <ul className="space-y-2.5 px-4 py-3">
      {rows.map((r) => (
        // The bar sits under the name: the widget is a narrow column at every
        // width, and three counts beside it squeezed it to nothing.
        <li key={r.player} className="flex items-center gap-3">
          <Face character={r.character} color={colorOf(r.player)} label={r.label} size={30} />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{r.label}</span>
              <span className="nums shrink-0 text-sm">
                <span className="font-semibold">{r.hit}</span>
                <span className="text-xs text-muted"> hit</span>
                {r.caught > 0 && (
                  <>
                    <span className="text-muted"> · </span>
                    <span className="font-semibold text-[#7a6cc9]">{r.caught}</span>
                    <span className="text-xs text-muted"> caught</span>
                  </>
                )}
                {r.dodged > 0 && (
                  <>
                    <span className="text-muted"> · </span>
                    <span className="font-semibold text-brand">{r.dodged}</span>
                    <span className="text-xs text-muted"> dodged</span>
                  </>
                )}
              </span>
            </div>
            <span className="mt-1 flex h-3 overflow-hidden rounded-full bg-line-soft">
              <span
                className="h-full"
                style={{ width: `${(r.hit / top) * 100}%`, background: "#4a3aa7" }}
                title={`${r.hit} locked on to them and got them`}
              />
              <span
                className="h-full"
                style={{ width: `${(r.caught / top) * 100}%`, background: "#a99ee0" }}
                title={`${r.caught} caught them going off on somebody else`}
              />
              <span
                className="h-full"
                style={{
                  width: `${(r.dodged / top) * 100}%`,
                  background:
                    "repeating-linear-gradient(135deg, #9fb0e8 0 3px, #dfe5f8 3px 6px)",
                }}
                title={`${r.dodged} dodged`}
              />
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Every blue shell in a set of races, newest race first. */
export function BlueList({
  races,
  players,
  mode,
}: {
  races: RaceStats[];
  players: Player[];
  mode: NameMode;
}) {
  const all = races.flatMap((race) =>
    race.blueShells.map((b) => ({ race, b })),
  );
  if (!all.length)
    return <p className="px-4 py-6 text-sm text-muted">No blue shells thrown.</p>;
  const who = (slot: number | null, race: RaceStats) => {
    if (slot == null) return { name: "nobody", player: null as number | null };
    const p = playerOfSlot(slot, race.log, players);
    return {
      name: p != null ? nameOf(players[p], mode, race.log.field.name(slot)) : race.log.field.name(slot),
      player: p,
    };
  };
  return (
    <ul className="divide-y divide-line-soft">
      {all.map(({ race, b }, i) => {
        const from = who(b.thrower, race);
        const to = who(b.target, race);
        const caught = b.caught.map((s) => who(s, race).name).join(", ");
        return (
          // Wraps on a phone: the thrower and target move down as one piece,
          // then the result, rather than squeezing the result off the edge.
          <li
            key={`${race.file}-${i}`}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-sm"
          >
            {races.length > 1 && (
              <span className="nums w-14 shrink-0 text-xs text-muted">race {race.n}</span>
            )}
            <span className="nums w-14 shrink-0 text-right text-xs text-muted">{b.t.toFixed(1)}s</span>
            <span className="flex items-center gap-3 whitespace-nowrap">
              <Dot player={from.player} />
              <span className={from.player != null ? "font-medium" : "text-ink-soft"}>{from.name}</span>
              <span className="text-muted">→</span>
              {b.target == null ? (
                <span className="text-ink-soft" title="the lead changed hands while it was in the air">
                  the lead
                </span>
              ) : (
                <>
                  <Dot player={to.player} />
                  <span className={to.player != null ? "font-medium" : "text-ink-soft"}>{to.name}</span>
                </>
              )}
            </span>
            {caught && <span className="text-xs text-muted">caught {caught}</span>}
            <span
              className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${
                b.hit || b.target == null
                  ? "bg-[#4a3aa7]/10 text-[#4a3aa7]"
                  : "bg-brand-soft text-brand"
              }`}
            >
              {b.hit
                ? `hit at ${b.hitT?.toFixed(1)}s`
                : b.target != null
                  ? "dodged"
                  : "hit nobody"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Dot({ player }: { player: number | null }) {
  return (
    <span
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={{ background: player != null ? colorOf(player) : "#ced4da" }}
    />
  );
}

export type { BlueShell };
