// How one race unfolded: position against time, with what happened on top.
//
// The line is stepped because position is a step function - the game reports a
// swap, not a slide - and drawing it sloped would invent moments that never
// happened. Crosses are hits taken, triangles are blue shells.

import { useState } from "react";
import { SAMPLE_EVERY, type Marker, type RaceDetail } from "../lib/stats";
import { colorOf } from "./common";

// Two sizes: the full chart, and one for a widget a third of the screen wide,
// where a smaller viewBox keeps the text readable.
const SIZES = {
  full: { W: 1000, H: 300, PAD: { top: 14, right: 116, bottom: 28, left: 34 } },
  compact: { W: 560, H: 280, PAD: { top: 14, right: 84, bottom: 26, left: 30 } },
};

export function PositionWorm({
  detail,
  labels,
  duration,
  field,
  compact = false,
}: {
  detail: RaceDetail;
  labels: Map<number, string>;
  duration: number;
  field: number;
  compact?: boolean;
}) {
  const [hover, setHover] = useState<Marker | null>(null);
  const { W, H, PAD } = SIZES[compact ? "compact" : "full"];
  const end = Math.max(duration, detail.steps * SAMPLE_EVERY);

  const x = (t: number) => PAD.left + ((W - PAD.left - PAD.right) * t) / (end || 1);
  const y = (p: number) =>
    PAD.top + ((H - PAD.top - PAD.bottom) * (p - 1)) / Math.max(field - 1, 1);

  const rows = [...detail.series].sort(
    (a, b) => (a[1].at(-1) ?? 99) - (b[1].at(-1) ?? 99),
  );

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
        {[1, 4, 8, 12].filter((p) => p <= field).map((p) => (
          <g key={p}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(p)}
              y2={y(p)}
              stroke="#f1f3f5"
            />
            <text
              x={PAD.left - 8}
              y={y(p) + 4}
              textAnchor="end"
              className="fill-muted text-[11px]"
            >
              {p}
            </text>
          </g>
        ))}

        {detail.lapStarts.map((l) => (
          <g key={l.lap}>
            <line
              x1={x(l.t)}
              x2={x(l.t)}
              y1={PAD.top}
              y2={H - PAD.bottom}
              stroke="#ced4da"
              strokeDasharray="2 4"
            />
            <text x={x(l.t) + 4} y={PAD.top + 10} className="fill-muted text-[10px]">
              lap {l.lap}
            </text>
          </g>
        ))}

        {rows.map(([player, row]) => (
          <polyline
            key={player}
            points={stepped(row, x, y)}
            fill="none"
            stroke={colorOf(player)}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        ))}

        {detail.markers.map((m, i) => {
          const px = x(m.t);
          const py = y(m.position ?? 1);
          const color = colorOf(m.player);
          return (
            <g
              key={i}
              onMouseEnter={() => setHover(m)}
              onMouseLeave={() => setHover(null)}
              className="cursor-default"
            >
              <circle cx={px} cy={py} r={9} fill="transparent" />
              {m.blue ? (
                <polygon
                  points={`${px},${py - 6} ${px + 6},${py + 5} ${px - 6},${py + 5}`}
                  fill={color}
                  stroke="#4a3aa7"
                  strokeWidth={1.5}
                />
              ) : (
                <g stroke={color} strokeWidth={2.2} strokeLinecap="round">
                  <line x1={px - 4} y1={py - 4} x2={px + 4} y2={py + 4} />
                  <line x1={px - 4} y1={py + 4} x2={px + 4} y2={py - 4} />
                </g>
              )}
            </g>
          );
        })}

        {rows.map(([player, row]) => (
          <text
            key={player}
            x={W - PAD.right + 10}
            y={y(row.at(-1) ?? 1) + 4}
            className="fill-ink text-[12px] font-medium"
          >
            {labels.get(player) ?? ""}
          </text>
        ))}

        <text
          x={W - PAD.right}
          y={H - 8}
          textAnchor="end"
          className="fill-muted text-[11px]"
        >
          {Math.round(end)}s
        </text>
      </svg>

      {hover && (
        <div className="pointer-events-none absolute top-0 right-0 rounded-lg border border-line bg-card/95 px-3 py-2 text-xs shadow-sm">
          <div className="font-semibold" style={{ color: colorOf(hover.player) }}>
            {labels.get(hover.player)} · P{hover.position} · {hover.t.toFixed(1)}s
          </div>
          <div className="text-ink-soft">
            {hover.caught ? "caught in the blast from " : "hit by "}
            {hover.cause}
            {hover.by.length ? ` (${hover.by.join(", ")})` : ""}
          </div>
          {hover.guess && (
            <div className="text-muted">attribution not certain</div>
          )}
        </div>
      )}
    </div>
  );
}

function stepped(
  row: number[],
  x: (t: number) => number,
  y: (p: number) => number,
): string {
  const pts: string[] = [];
  row.forEach((p, i) => {
    const t = i * SAMPLE_EVERY;
    if (i) pts.push(`${x(t)},${y(row[i - 1])}`);
    pts.push(`${x(t)},${y(p)}`);
  });
  return pts.join(" ");
}
