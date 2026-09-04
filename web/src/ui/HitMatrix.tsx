// Who hit whom. Attackers down the side, victims across the top.
//
// The small version keeps the tracked players and folds every CPU into one
// row and one column, because on a four-player night that is the argument
// being settled. The large version has every CPU character as its own line.

import type { HitMatrix as Matrix, Identity } from "../lib/stats";
import { CHARACTERS } from "../data/names";
import { Face, colorOf } from "./common";

const CPU_KEY = "cpus";

export function HitMatrixTable({
  matrix,
  nameOf,
  full,
}: {
  matrix: Matrix;
  /** What to call a player, honouring the Characters/Names toggle. */
  nameOf: (id: Identity) => string;
  full: boolean;
}) {
  const players = matrix.identities.filter((i) => !i.cpu);
  const cpus = matrix.identities.filter((i) => i.cpu);

  const rows: Identity[] = full
    ? [...players, ...cpus.filter((c) => matrix.dealt(c.key) > 0 || matrix.taken(c.key) > 0)]
    : [...players, ...(cpus.length ? [cpuIdentity(cpus.length)] : [])];
  const cols = rows;

  const count = (from: Identity, to: Identity) => {
    const froms = from.key === CPU_KEY ? cpus.map((c) => c.key) : [from.key];
    const tos = to.key === CPU_KEY ? cpus.map((c) => c.key) : [to.key];
    let n = 0;
    for (const f of froms) for (const t of tos) n += matrix.counts.get(`${f}>${t}`) ?? 0;
    return n;
  };
  // Row and column sums of what is on screen, so the margins always add up
  // to the cells beside them. Dealt leaves out the diagonal, because driving
  // into your own banana is not a hit dealt; taken keeps it, because it was
  // still a hit taken.
  const dealt = (id: Identity) =>
    cols.reduce((n, c) => n + (c.key === id.key && id.key !== CPU_KEY ? 0 : count(id, c)), 0);
  const taken = (id: Identity) => rows.reduce((n, r) => n + count(r, id), 0);

  const most = Math.max(1, ...rows.flatMap((r) => cols.map((c) => count(r, c))));
  if (rows.every((r) => dealt(r) === 0 && taken(r) === 0))
    return <p className="px-5 py-6 text-sm text-muted">Nobody has hit anybody yet.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="nums text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="px-3 py-2 text-left font-normal">
              <span className="text-[10px] tracking-wide uppercase">hit by ↓ · hit →</span>
            </th>
            {cols.map((c) => (
              <th key={c.key} className="px-1 py-2 text-center font-medium">
                <Head id={c} name={nameOf(c)} small={!full && cols.length > 6} />
              </th>
            ))}
            <th className="px-2 py-2 text-right font-medium">dealt</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-line-soft">
              <td className="px-3 py-1 whitespace-nowrap">
                <span className="flex items-center gap-2">
                  <Head id={r} name={nameOf(r)} small={false} />
                  <span className={r.cpu ? "text-ink-soft" : "font-medium"}>{nameOf(r)}</span>
                </span>
              </td>
              {cols.map((c) => {
                const n = count(r, c);
                const self = r.key === c.key && r.key !== CPU_KEY;
                return (
                  <td
                    key={c.key}
                    className={`px-1 py-1 text-center ${self ? "text-muted" : ""}`}
                    title={
                      self
                        ? `${nameOf(r)} hit by their own item: ${n}`
                        : `${nameOf(r)} hit ${nameOf(c)} ${n} time${n === 1 ? "" : "s"}`
                    }
                  >
                    <span
                      className="inline-block min-w-8 rounded-md px-1.5 py-0.5 font-semibold"
                      style={{
                        background: n
                          ? `rgba(25, 118, 210, ${0.08 + 0.5 * (n / most)})`
                          : undefined,
                        color: n / most > 0.55 ? "#fff" : undefined,
                      }}
                    >
                      {n || <span className="text-line">·</span>}
                    </span>
                  </td>
                );
              })}
              <td className="px-2 py-1 text-right font-semibold">{dealt(r)}</td>
            </tr>
          ))}
          <tr className="border-t border-line text-xs text-muted">
            <td className="px-3 py-1.5 text-right font-medium">taken</td>
            {cols.map((c) => (
              <td key={c.key} className="px-1 py-1.5 text-center font-semibold text-ink">
                {taken(c)}
              </td>
            ))}
            <td />
          </tr>
        </tbody>
      </table>
      <p className="px-4 py-3 text-xs text-muted">
        Only hits whose thrower was read cleanly are counted. The diagonal is
        people driving into their own items.
        {!full && cpus.length > 0 && " Expand for every CPU on its own line."}
      </p>
    </div>
  );
}

function cpuIdentity(n: number): Identity {
  return { key: CPU_KEY, name: `CPUs (${n})`, character: null, player: null, cpu: true };
}

function Head({ id, name, small }: { id: Identity; name: string; small: boolean }) {
  if (id.key === CPU_KEY)
    return (
      <span className="inline-flex h-6 items-center justify-center rounded-md border border-line bg-line-soft px-1.5 text-[10px] text-ink-soft">
        CPUs
      </span>
    );
  const character = id.character != null ? (CHARACTERS[id.character] ?? null) : null;
  return (
    <Face
      character={character}
      color={id.player != null ? colorOf(id.player) : "#ced4da"}
      label={name}
      size={small ? 22 : 26}
      ring={id.player != null}
    />
  );
}
