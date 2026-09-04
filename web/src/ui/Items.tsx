// Items, by name and by picture: what everybody picked up, what they threw,
// and what hit them.
//
// The art in assets/items is named by the same slug the character faces use,
// so an item id becomes a file name with nothing looked up. Anything without
// a picture - a hazard, "a boosted kart" - is drawn as a labelled chip.

import { useState } from "react";
import { ITEMS } from "../data/names";
import { causeRank, itemRank } from "../lib/stats";
import type { HitCause, ItemTally, Player, Scavenge } from "../lib/stats";
import { Face, colorOf, secs, slug } from "./common";

export const itemUrl = (name: string) => `/assets/items/${slug(name)}.png`;

export function ItemIcon({
  name,
  size = 24,
  className = "",
  chip = true,
}: {
  name: string;
  size?: number;
  className?: string;
  /** Draw the name as a chip when there is no picture. Off where the name
   *  is printed beside the icon anyway. */
  chip?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (failed && !chip) return null;
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
 *  many times, and the throw count under each.
 *
 *  Which ones is by count, because a strip this narrow can only show a few and
 *  the few worth showing are the ones they kept getting; the order they are
 *  drawn in is ITEM_ORDER, so every strip reads the same way round. */
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
    .map(([id]) => id)
    .sort((a, b) => itemRank(a) - itemRank(b));
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

/** Players down the side, items across the top: picked up / thrown, with a
 *  red ring round anything knocked out of their hands. */
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
                        <span
                          // The ring says one was lost. The count is in the
                          // tooltip: a "−2" beside two other figures read as
                          // arithmetic on them.
                          className={
                            lost > 0
                              ? "inline-block rounded-full px-1.5 ring-1 ring-red-400"
                              : undefined
                          }
                          title={`${itemName(id)}: picked up ${got}, thrown ${used}${lost ? `, ${lost} knocked out of their hands` : ""}`}
                        >
                          <span className="font-semibold">{got}</span>
                          <span className="text-muted">/{used}</span>
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
        Picked up / thrown. A red ring is an item knocked out of their hands
        before it could be used; hover it for how many. A triple is one pickup
        and one throw.
      </p>
    </div>
  );
}

/** One player's worst enemies among the items, as icons with counts. The
 *  ones they took most, drawn in the order the item columns use. */
export function CauseStrip({ causes, limit = 5 }: { causes: HitCause[]; limit?: number }) {
  if (!causes.length) return <span className="text-xs text-muted">never hit</span>;
  const shown = causes
    .slice(0, limit)
    .sort((a, b) => causeRank(a.cause) - causeRank(b.cause));
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {shown.map((c) => (
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
  // Items first, in the order the item table uses, then everything nobody
  // threw - a Chain Chomp is not somebody's doing (stats.ts::causeRank).
  const columns = [...all.keys()].sort((a, b) => causeRank(a) - causeRank(b));
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

/** One player's items picked up off the road, as icons with counts. */
export function ScavengedStrip({ found }: { found: Scavenge[] }) {
  if (!found.length) return <span className="text-xs text-muted">none</span>;
  const byItem = new Map<number, number>();
  for (const s of found) byItem.set(s.item, (byItem.get(s.item) ?? 0) + 1);
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {[...byItem.keys()]
        .sort((a, b) => itemRank(a) - itemRank(b))
        .map((id) => (
          <span key={id} className="inline-flex items-center gap-1" title={itemName(id)}>
            <ItemIcon name={itemName(id)} size={22} />
            <span className="nums text-sm font-semibold">{byItem.get(id)}</span>
          </span>
        ))}
    </span>
  );
}

/** Every pickup off the road, with what made it one. */
export function ScavengedList({
  players,
  found,
  label,
  face,
}: {
  players: Player[];
  found: Scavenge[][];
  label: (p: Player) => string;
  face: (p: Player) => string | null;
}) {
  const rows = players.flatMap((p, i) => found[i].map((s) => ({ p, i, s })));
  if (!rows.length) return <ScavengedNote />;
  return (
    <>
      <ul className="divide-y divide-line-soft">
        {rows.map(({ p, i, s }) => (
          <li key={`${i}-${s.race}-${s.t}`} className="flex items-center gap-3 px-4 py-2 text-sm">
            <Face character={face(p)} color={colorOf(p.index)} label={label(p)} size={24} />
            <span className="w-20 shrink-0 truncate font-medium">{label(p)}</span>
            <span className="nums w-14 shrink-0 text-xs text-muted">race {s.race}</span>
            <span className="w-36 shrink-0 truncate text-xs text-muted">{s.courseName}</span>
            <span className="nums w-14 shrink-0 text-right text-xs text-muted">
              {s.t.toFixed(1)}s
            </span>
            <ItemIcon name={itemName(s.item)} size={20} chip={false} />
            <span className="truncate">{itemName(s.item)}</span>
            <span className="ml-auto shrink-0 text-xs text-muted">
              {s.how === "off-row"
                ? `${Math.round(s.lap * 100)}% round the lap, ${Math.round((s.gap ?? 0) * 100)}% from the nearest item box`
                : "no item box before it"}
            </span>
          </li>
        ))}
      </ul>
      <ScavengedNote short />
    </>
  );
}

/** What the widget is claiming, and what it cannot see. */
export function ScavengedNote({ short = false }: { short?: boolean }) {
  return (
    <p className="px-4 pt-1 pb-4 text-xs text-muted">
      {!short && "Nothing found. "}
      An item counts as picked up off the road when its item box is nowhere
      near where anybody else got one that race — boxes sit in rows, so every
      ordinary pickup has another beside it — or when it lands in somebody's
      hands with no box at all. Both are inference from where and when. A
      pickup the game writes nothing for is invisible to either
      (<code className="font-mono">docs/EXPERIMENTS.md</code>, 2026-09-03).
    </p>
  );
}
