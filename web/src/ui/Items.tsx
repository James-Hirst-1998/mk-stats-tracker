// Items, by name and by picture: what everybody picked up, what they threw,
// and what hit them.
//
// The art in assets/items is named by the same slug the character faces use,
// so an item id becomes a file name with nothing looked up. Anything without
// a picture - a hazard, "a boosted kart" - is drawn as a labelled chip.

import { useState } from "react";
import { ITEMS } from "../data/names";
import type { HitCause, ItemTally, Player } from "../lib/stats";
import { Face, colorOf, secs, slug } from "./common";

export const itemUrl = (name: string) => `/assets/items/${slug(name)}.png`;

export function ItemIcon({
  name,
  size = 24,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (failed)
    return (
      <span
        className={`inline-flex items-center rounded-md border border-line bg-line-soft px-1.5 text-[10px] leading-5 whitespace-nowrap text-ink-soft ${className}`}
        title={name}
      >
        {name}
      </span>
    );
  return (
    <img
      src={itemUrl(name)}
      alt={name}
      title={name}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className={`inline-block shrink-0 object-contain ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

export const itemName = (id: number) => ITEMS[id] ?? `item ${id}`;

/** One player's items in a line: the icons they picked up most, with how
 *  many times, and the throw count under each. */
export function ItemStrip({
  tally,
  limit = 6,
}: {
  tally: ItemTally;
  limit?: number;
}) {
  const ids = [...tally.got]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .slice(0, limit)
    .map(([id]) => id);
  if (!ids.length) return <span className="text-xs text-muted">nothing yet</span>;
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {ids.map((id) => (
        <span key={id} className="inline-flex items-center gap-1" title={itemName(id)}>
          <ItemIcon name={itemName(id)} size={22} />
          <span className="nums text-sm font-semibold">{tally.got.get(id) ?? 0}</span>
          <span className="nums text-[11px] text-muted">
            /{tally.used.get(id) ?? 0}
          </span>
        </span>
      ))}
    </span>
  );
}

/** Players down the side, items across the top: picked up / thrown, and the
 *  ones knocked out of their hands in a small red figure. */
export function ItemsTable({
  players,
  tallies,
  items,
  label,
  face,
}: {
  players: Player[];
  tallies: ItemTally[];
  items: number[];
  label: (p: Player) => string;
  face: (p: Player) => string | null;
}) {
  if (!items.length)
    return <p className="px-5 py-6 text-sm text-muted">No items picked up yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="nums w-full text-sm">
        <thead>
          <tr className="border-b border-line-soft text-xs text-muted">
            <th className="sticky left-0 bg-white px-4 py-2 text-left font-medium">player</th>
            <th className="px-2 py-2 text-right font-medium">got</th>
            <th className="px-2 py-2 text-right font-medium">used</th>
            {items.map((id) => (
              <th key={id} className="px-1.5 py-2 text-center font-medium">
                <ItemIcon name={itemName(id)} size={26} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map((p, i) => {
            const t = tallies[i];
            const total = (m: Map<number, number>) =>
              [...m.values()].reduce((a, b) => a + b, 0);
            return (
              <tr key={p.index} className="border-b border-line-soft last:border-0">
                <td className="sticky left-0 bg-white px-4 py-1.5 font-medium whitespace-nowrap">
                  <span className="flex items-center gap-2">
                    <Face character={face(p)} color={colorOf(p.index)} label={label(p)} size={24} />
                    {label(p)}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right font-semibold">{total(t.got)}</td>
                <td className="px-2 py-1.5 text-right">{total(t.used)}</td>
                {items.map((id) => {
                  const got = t.got.get(id) ?? 0;
                  const used = t.used.get(id) ?? 0;
                  const lost = t.lost.get(id) ?? 0;
                  return (
                    <td key={id} className="px-1.5 py-1.5 text-center">
                      {got || used ? (
                        <span title={`${itemName(id)}: picked up ${got}, thrown ${used}${lost ? `, lost ${lost}` : ""}`}>
                          <span className="font-semibold">{got}</span>
                          <span className="text-muted">/{used}</span>
                          {lost > 0 && (
                            <span className="ml-0.5 text-[10px] text-red-600">−{lost}</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-line">·</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="px-4 py-3 text-xs text-muted">
        Picked up / thrown. A red figure is an item knocked out of their hands
        before it could be used. A triple is one pickup and one throw.
      </p>
    </div>
  );
}

/** One player's worst enemies among the items, as icons with counts. */
export function CauseStrip({ causes, limit = 5 }: { causes: HitCause[]; limit?: number }) {
  if (!causes.length) return <span className="text-xs text-muted">never hit</span>;
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {causes.slice(0, limit).map((c) => (
        <span key={c.cause} className="inline-flex items-center gap-1" title={c.cause}>
          <ItemIcon name={c.cause} size={22} />
          <span className="nums text-sm font-semibold">{c.count}</span>
        </span>
      ))}
    </span>
  );
}

/** Players down the side, causes across the top. */
export function CausesTable({
  players,
  causes,
  label,
  face,
}: {
  players: Player[];
  causes: HitCause[][];
  label: (p: Player) => string;
  face: (p: Player) => string | null;
}) {
  const all = new Map<string, number>();
  for (const list of causes)
    for (const c of list) all.set(c.cause, (all.get(c.cause) ?? 0) + c.count);
  const columns = [...all].sort((a, b) => b[1] - a[1]).map(([c]) => c);
  if (!columns.length)
    return <p className="px-5 py-6 text-sm text-muted">Nobody has been hit yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="nums w-full text-sm">
        <thead>
          <tr className="border-b border-line-soft text-xs text-muted">
            <th className="sticky left-0 bg-white px-4 py-2 text-left font-medium">player</th>
            <th className="px-2 py-2 text-right font-medium">hits</th>
            <th className="px-2 py-2 text-right font-medium">out</th>
            {columns.map((c) => (
              <th key={c} className="px-1.5 py-2 text-center font-medium">
                <ItemIcon name={c} size={26} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map((p, i) => {
            const mine = new Map(causes[i].map((c) => [c.cause, c]));
            const hits = causes[i].reduce((n, c) => n + c.count, 0);
            const out = causes[i].reduce((n, c) => n + c.out, 0);
            return (
              <tr key={p.index} className="border-b border-line-soft last:border-0">
                <td className="sticky left-0 bg-white px-4 py-1.5 font-medium whitespace-nowrap">
                  <span className="flex items-center gap-2">
                    <Face character={face(p)} color={colorOf(p.index)} label={label(p)} size={24} />
                    {label(p)}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right font-semibold">{hits}</td>
                <td className="px-2 py-1.5 text-right">{secs(Math.round(out * 10) / 10)}</td>
                {columns.map((c) => {
                  const got = mine.get(c);
                  return (
                    <td key={c} className="px-1.5 py-1.5 text-center">
                      {got ? (
                        <span
                          title={`${c}: ${got.count}${got.caught ? `, ${got.caught} caught in the blast` : ""}${got.guessed ? `, ${got.guessed} attribution not certain` : ""}`}
                        >
                          <span className="font-semibold">{got.count}</span>
                          {got.caught > 0 && (
                            <span className="text-[10px] text-muted"> ({got.caught})</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-line">·</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="px-4 py-3 text-xs text-muted">
        A figure in brackets is how many of those were being caught in somebody
        else's blast rather than being the one it went for. "Out" is the seconds
        the hits cost, over the hits whose end was seen.
      </p>
    </div>
  );
}
