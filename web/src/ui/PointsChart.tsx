// Points across the night, one dotted line per player.
//
// The axes are fixed to the whole sequence rather than to the races played so
// far, so the shape of the night does not change every time a race lands - a
// line growing into the space is the point of the chart.

import { useRef, useState } from "react";
import { colorOf } from "./common";

export interface PointsSeries {
  player: number;
  label: string;
  /** Cumulative points after each race, index 0 = after race 1. */
  points: number[];
}

// Two sizes of the same chart. The small one sits in a widget a third of the
// screen wide, so its drawing space is smaller in viewBox units and the text,
// which is sized in those units, comes out readable rather than a third the
// size.
const SIZES = {
  full: { W: 1000, H: 340, PAD: { top: 16, right: 132, bottom: 34, left: 42 } },
  compact: { W: 520, H: 300, PAD: { top: 14, right: 100, bottom: 30, left: 34 } },
};

export function PointsChart({
  series,
  races,
  maxRaces,
  compact = false,
}: {
  series: PointsSeries[];
  races: number;
  maxRaces: number;
  compact?: boolean;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const { W, H, PAD } = SIZES[compact ? "compact" : "full"];

  const top = Math.max(15, maxRaces * 15);
  const x = (n: number) =>
    PAD.left +
    ((W - PAD.left - PAD.right) * (maxRaces === 1 ? 1 : (n - 1) / (maxRaces - 1)));
  const y = (p: number) =>
    H - PAD.bottom - ((H - PAD.top - PAD.bottom) * p) / top;

  const ticks = niceTicks(top);
  const raceTicks = raceLabels(maxRaces);

  // Direct labels at the end of each line, nudged apart when two players are
  // level - overlapping text is the usual way this chart goes wrong.
  const ends = series
    .map((s) => ({
      player: s.player,
      label: s.label,
      value: s.points[races - 1] ?? 0,
      y: y(s.points[races - 1] ?? 0),
    }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++)
    if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;

  const move = (e: React.MouseEvent) => {
    const rect = svg.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const n = Math.round(
      1 + ((px - PAD.left) / (W - PAD.left - PAD.right)) * (maxRaces - 1),
    );
    setHover(n >= 1 && n <= races ? n : null);
  };

  return (
    <div className="relative">
      <svg
        ref={svg}
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        onMouseMove={move}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              stroke="#f1f3f5"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 8}
              y={y(t) + 4}
              textAnchor="end"
              className="fill-muted text-[11px]"
            >
              {t}
            </text>
          </g>
        ))}
        {raceTicks.map((n) => (
          <text
            key={n}
            x={x(n)}
            y={H - PAD.bottom + 18}
            textAnchor="middle"
            className="fill-muted text-[11px]"
          >
            {n}
          </text>
        ))}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={H - PAD.bottom}
          y2={H - PAD.bottom}
          stroke="#dee2e6"
        />

        {hover != null && (
          <line
            x1={x(hover)}
            x2={x(hover)}
            y1={PAD.top}
            y2={H - PAD.bottom}
            stroke="#adb5bd"
            strokeDasharray="3 3"
          />
        )}

        {series.map((s) => {
          const pts = s.points
            .slice(0, races)
            .map((p, i) => `${x(i + 1)},${y(p)}`)
            .join(" ");
          return (
            <g key={s.player}>
              <polyline
                points={pts}
                fill="none"
                stroke={colorOf(s.player)}
                strokeWidth={2}
                strokeDasharray="4 4"
                strokeLinecap="round"
              />
              {s.points.slice(0, races).map((p, i) => (
                <circle
                  key={i}
                  cx={x(i + 1)}
                  cy={y(p)}
                  r={hover === i + 1 ? 5 : 3}
                  fill={colorOf(s.player)}
                  stroke="#fff"
                  strokeWidth={1.5}
                />
              ))}
            </g>
          );
        })}

        {ends.map((e) => (
          <g key={e.player}>
            <line
              x1={W - PAD.right + 2}
              x2={W - PAD.right + 10}
              y1={y(e.value)}
              y2={e.y}
              stroke={colorOf(e.player)}
              strokeWidth={1}
            />
            <text x={W - PAD.right + 14} y={e.y + 4} className="text-[12px]">
              <tspan className="fill-ink font-medium">{e.label}</tspan>
              <tspan className="fill-muted nums"> {e.value}</tspan>
            </text>
          </g>
        ))}
      </svg>

      {hover != null && (
        <div className="pointer-events-none absolute top-2 left-12 rounded-lg border border-line bg-card/95 px-3 py-2 text-xs shadow-sm">
          <div className="mb-1 font-semibold">After race {hover}</div>
          {[...series]
            .sort(
              (a, b) => (b.points[hover - 1] ?? 0) - (a.points[hover - 1] ?? 0),
            )
            .map((s) => (
              <div key={s.player} className="flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: colorOf(s.player) }}
                />
                <span className="text-ink-soft">{s.label}</span>
                <span className="nums ml-auto font-medium">
                  {s.points[hover - 1] ?? 0}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function niceTicks(top: number): number[] {
  const step = top <= 60 ? 15 : top <= 200 ? 30 : Math.ceil(top / 8 / 15) * 15;
  const out: number[] = [];
  for (let t = 0; t <= top; t += step) out.push(t);
  return out;
}

function raceLabels(max: number): number[] {
  const step = max <= 12 ? 1 : max <= 24 ? 2 : 4;
  const out: number[] = [];
  for (let n = 1; n <= max; n += step) out.push(n);
  if (out[out.length - 1] !== max) out.push(max);
  return out;
}
