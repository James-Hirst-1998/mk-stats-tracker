// Blue shells: taken and dodged per player, and every one thrown in a race.
//
// A dodge is a shell that went for somebody who never took the launched hit
// it should have produced - a cannon, a well-timed Mushroom, a Star, a Bill.
// It is derived, not read, and the rule is in stats.ts (`blueShells`).

import type { BlueShell, Player, RaceStats } from "../lib/stats";
import { playerOfSlot } from "../lib/stats";
import { Face, colorOf, nameOf, type NameMode } from "./common";

export interface BlueRow {
  player: number;
  label: string;
  character: string | null;
  taken: number;
  dodged: number;
}

export function BlueBars({ rows }: { rows: BlueRow[] }) {
  const top = Math.max(1, ...rows.map((r) => r.taken + r.dodged));
  if (rows.every((r) => r.taken + r.dodged === 0))
    return (
      <p className="px-4 py-6 text-sm text-muted">
        No blue shell has gone for any of them yet.
      </p>
    );
  return (
    <ul className="space-y-2.5 px-4 py-3">
      {rows.map((r) => (
        <li key={r.player} className="flex items-center gap-3">
          <Face character={r.character} color={colorOf(r.player)} label={r.label} size={30} />
          <span className="w-20 shrink-0 truncate text-sm font-medium">{r.label}</span>
          <span className="flex h-5 flex-1 overflow-hidden rounded-full bg-line-soft">
            <span
              className="h-full"
              style={{ width: `${(r.taken / top) * 100}%`, background: "#4a3aa7" }}
              title={`${r.taken} taken`}
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
          <span className="nums w-24 shrink-0 text-right text-sm">
            <span className="font-semibold">{r.taken}</span>
            <span className="text-xs text-muted"> taken</span>
            {r.dodged > 0 && (
              <>
                <span className="text-muted"> · </span>
                <span className="font-semibold text-brand">{r.dodged}</span>
                <span className="text-xs text-muted"> dodged</span>
              </>
            )}
          </span>
        </li>
      ))}
      <li className="pt-1 text-[11px] text-muted">
        Solid is a shell that landed; hatched is one aimed at them that never
        did.
      </li>
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
        return (
          <li key={`${race.file}-${i}`} className="flex items-center gap-3 px-4 py-2 text-sm">
            {races.length > 1 && (
              <span className="nums w-14 shrink-0 text-xs text-muted">race {race.n}</span>
            )}
            <span className="nums w-14 shrink-0 text-right text-xs text-muted">{b.t.toFixed(1)}s</span>
            <Dot player={from.player} />
            <span className={from.player != null ? "font-medium" : "text-ink-soft"}>{from.name}</span>
            <span className="text-muted">→</span>
            <Dot player={to.player} />
            <span className={to.player != null ? "font-medium" : "text-ink-soft"}>{to.name}</span>
            <span
              className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${
                b.landed ? "bg-[#4a3aa7]/10 text-[#4a3aa7]" : "bg-brand-soft text-brand"
              }`}
            >
              {!b.landed
                ? "dodged"
                : b.victim === b.target
                  ? `landed at ${b.hitT?.toFixed(1)}s`
                  : `landed on ${who(b.victim, race).name} at ${b.hitT?.toFixed(1)}s`}
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
