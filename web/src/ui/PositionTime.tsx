// How long each player spent in each position, as one bar per player.
//
// First, second and third get their metals; the rest fade from blue to grey
// so the eye reads "how much of that bar is at the front" without a legend.

import { Face, colorOf, secs } from "./common";

export interface PositionRow {
  player: number;
  label: string;
  character: string | null;
  time: Map<number, number>;
}

export function positionColor(p: number, field = 12): string {
  if (p === 1) return "#e0b93c";
  if (p === 2) return "#a8adb3";
  if (p === 3) return "#c48a52";
  const f = Math.min(1, Math.max(0, (p - 4) / Math.max(field - 4, 1)));
  const from = [93, 140, 200];
  const to = [222, 226, 230];
  const c = from.map((a, i) => Math.round(a + (to[i] - a) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function PositionTime({ rows, field = 12 }: { rows: PositionRow[]; field?: number }) {
  if (rows.every((r) => r.time.size === 0))
    return <p className="px-4 py-6 text-sm text-muted">No position data yet.</p>;
  return (
    <div className="space-y-3 px-4 py-3">
      {rows.map((r) => {
        const total = [...r.time.values()].reduce((a, b) => a + b, 0) || 1;
        const parts = [...r.time].sort((a, b) => a[0] - b[0]);
        return (
          <div key={r.player}>
            <div className="mb-1 flex items-center gap-2 text-sm">
              <Face character={r.character} color={colorOf(r.player)} label={r.label} size={22} />
              <span className="font-medium">{r.label}</span>
              <span className="nums ml-auto text-xs text-muted">
                P1 for {secs(Math.round((r.time.get(1) ?? 0) * 10) / 10)}
              </span>
            </div>
            <div className="flex h-5 w-full overflow-hidden rounded-md bg-line-soft">
              {parts.map(([p, t]) => (
                <span
                  key={p}
                  className="flex items-center justify-center text-[10px] font-semibold text-white/90"
                  style={{
                    width: `${(t / total) * 100}%`,
                    background: positionColor(p, field),
                    textShadow: "0 0 2px rgba(0,0,0,.4)",
                  }}
                  title={`P${p}: ${secs(Math.round(t * 10) / 10)}`}
                >
                  {t / total > 0.08 ? `P${p}` : ""}
                </span>
              ))}
            </div>
          </div>
        );
      })}
      <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1 text-[11px] text-muted">
        {[1, 2, 3, 6, 12].filter((p) => p <= field).map((p) => (
          <span key={p} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: positionColor(p, field) }}
            />
            P{p}
          </span>
        ))}
        <span>· share of their race, by the game's position events</span>
      </div>
    </div>
  );
}
