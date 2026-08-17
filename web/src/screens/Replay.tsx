// One race, played back on the course it was raced on.
//
// The only thing stored per racer is progress - lap plus fraction of a lap, at
// 5 Hz - so a kart's position on screen is that fraction along the course
// centreline. That is honest about the lap and about the order, and says
// nothing about which side of the road anybody was on, because the logs do not
// know. Gaps are the progress difference times the race's median lap, which is
// an estimate and is labelled as one.

import { useEffect, useMemo, useRef, useState } from "react";
import { useRace } from "../lib/data";
import { replayData, slotsOf } from "../lib/stats";
import { trackFor, FALLBACK } from "../data/tracks";
import { CHARACTERS } from "../data/names";
import { Card, Face, colorOf, nameOf, secs, type NameMode } from "../ui/common";

const SPEEDS = [1, 2, 4, 8];

export function Replay({ dir, file }: { dir: string; file: string }) {
  const { stats, log, error } = useRace(dir, file);
  const players = stats?.players ?? [];
  const data = useMemo(
    () => (log ? replayData(log, players) : null),
    [log, players],
  );

  // The same Characters/Names choice the dashboard is showing.
  const mode = (localStorage.getItem("mkw.mode") as NameMode) ?? "characters";
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const path = useRef<SVGPathElement>(null);
  const [length, setLength] = useState(0);

  const track = data?.course != null ? trackFor(data.course) : null;
  const shape = track ?? FALLBACK;

  useEffect(() => {
    if (path.current) setLength(path.current.getTotalLength());
  }, [shape.d]);

  useEffect(() => {
    if (!playing || !data) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = ((now - last) / 1000) * speed;
      last = now;
      setT((x) => {
        const next = x + dt;
        if (next >= data.duration) {
          setPlaying(false);
          return data.duration;
        }
        return next;
      });
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, data]);

  if (error)
    return <Shell dir={dir}><p className="p-4 text-sm">{error}</p></Shell>;
  if (!data || !log || !stats)
    return <Shell dir={dir}><p className="p-4 text-sm text-muted">Loading…</p></Shell>;

  const progress = log.progressAt(t);
  const order = [...progress].sort((a, b) => b[1] - a[1]);
  const leader = order[0]?.[1] ?? 0;
  const slots = slotsOf(players, log);
  const bySlot = new Map([...slots].map(([i, s]) => [s, i]));

  const at = (p: number) => {
    if (!path.current || !length) return { x: 0, y: 0 };
    const frac = ((p % 1) + 1) % 1;
    const point = path.current.getPointAtLength(frac * length);
    return { x: point.x, y: point.y };
  };

  const jumps = jumpPoints(data);

  return (
    <Shell dir={dir}>
      <div className="mb-4 flex flex-wrap items-baseline gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{data.courseName}</h1>
        <span className="text-sm text-muted">
          {data.laps ?? "?"} laps · {secs(data.duration)} ·{" "}
          {stats.races.find((r) => r.file === file)?.n
            ? `race ${stats.races.find((r) => r.file === file)!.n}`
            : ""}
        </span>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          <div className="relative">
            <svg
              viewBox={`0 0 ${shape.size[0]} ${shape.size[1]}`}
              className="mx-auto max-h-[460px] w-full"
            >
              {shape.outline ? (
                // The road's own edges, out of the course file.
                <path d={shape.outline} fill="#f8f9fa" stroke="#ced4da" strokeWidth={2} />
              ) : shape.image ? (
                // The drawing itself, not a redrawing of it: whatever the
                // trace made of the course, the picture is the real one.
                <image
                  href={shape.image}
                  width={shape.size[0]}
                  height={shape.size[1]}
                />
              ) : (
                <path
                  d={shape.d}
                  fill="none"
                  stroke="#dee2e6"
                  strokeWidth={shape.width}
                  strokeLinecap="round"
                />
              )}
              <path ref={path} d={shape.d} fill="none" stroke="none" />
              <StartLine path={path.current} length={length} width={shape.width} />
              {order
                .slice()
                .reverse()
                .map(([slot, p]) => {
                  const player = bySlot.get(slot);
                  const point = at(p);
                  const color = player != null ? colorOf(player) : "#adb5bd";
                  const r = Math.max(shape.width * 0.6, 5);
                  return (
                    <g key={slot} transform={`translate(${point.x} ${point.y})`}>
                      <circle
                        r={player != null ? r : r * 0.6}
                        fill={color}
                        stroke="#fff"
                        strokeWidth={r * 0.2}
                        opacity={player != null ? 1 : 0.45}
                      />
                      {player != null && (
                        <text
                          y={r * 0.36}
                          textAnchor="middle"
                          fill="#fff"
                          fontSize={r}
                          fontWeight="700"
                        >
                          {order.findIndex(([s]) => s === slot) + 1}
                        </text>
                      )}
                    </g>
                  );
                })}
            </svg>
          </div>
          <p className="border-t border-line-soft px-4 py-2 text-center text-xs text-muted">
            {!track
              ? "No outline for this course yet — a generic loop, so only the order and the gaps mean anything."
              : track.source === "drawing"
                ? "The real course, traced from its layout drawing. Laps are measured from the bar, which is where the tracing starts and not the real start line."
                : "The course's own checkpoints: real road, real start line, real direction."}
          </p>

          <div className="flex flex-wrap items-center gap-3 border-t border-line-soft px-4 py-3">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="w-20 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white"
            >
              {playing ? "Pause" : t >= data.duration ? "Replay" : "Play"}
            </button>
            <input
              type="range"
              min={0}
              max={data.duration}
              step={0.1}
              value={t}
              onChange={(e) => setT(Number(e.target.value))}
              className="min-w-40 flex-1 accent-brand"
            />
            <span className="nums w-16 text-right text-sm text-muted">
              {t.toFixed(1)}s
            </span>
            <div className="inline-flex overflow-hidden rounded-lg border border-line text-xs">
              {SPEEDS.map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2 py-1 ${
                    speed === s ? "bg-brand text-white" : "text-ink-soft hover:bg-line-soft"
                  }`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>

          {jumps.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-line-soft px-4 py-3">
              <span className="text-xs text-muted">jump to</span>
              {jumps.map((j) => (
                <button
                  key={j.t}
                  onClick={() => setT(Math.max(0, j.t - 2))}
                  className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-line-soft"
                >
                  {j.text}
                </button>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="Running order">
            <ol className="divide-y divide-line-soft">
              {order.map(([slot, p], i) => {
                const player = bySlot.get(slot);
                const racer = log.racer(slot);
                const name =
                  player != null
                    ? nameOf(players[player], mode, log.field.name(slot))
                    : log.field.name(slot);
                const gap =
                  i === 0 || !data.avgLap
                    ? null
                    : (leader - p) * data.avgLap;
                return (
                  <li
                    key={slot}
                    className={`flex items-center gap-2 px-3 py-1.5 text-sm ${
                      player == null ? "text-muted" : ""
                    }`}
                  >
                    <span className="nums w-5 text-right font-semibold">{i + 1}</span>
                    <Face
                      character={
                        racer ? (CHARACTERS[racer.character] ?? null) : null
                      }
                      color={player != null ? colorOf(player) : "#ced4da"}
                      label={name}
                      size={20}
                    />
                    <span className={player != null ? "font-medium" : ""}>{name}</span>
                    <span className="nums ml-auto text-xs text-muted">
                      {gap == null ? "" : `+${gap.toFixed(1)}s`}
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="border-t border-line-soft px-3 py-2 text-xs text-muted">
              Gaps are estimates: progress difference × median lap
              {data.avgLap ? ` (${data.avgLap}s)` : ""}.
            </p>
          </Card>

          <Card title="What happened">
            <Ticker events={data.events} t={t} />
          </Card>
        </div>
      </div>
    </Shell>
  );
}

function Shell({ dir, children }: { dir: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6">
      <a
        href={`#/s/${dir}`}
        className="mb-4 inline-block text-sm text-brand hover:underline"
      >
        ← back to the night
      </a>
      {children}
    </div>
  );
}

/** Where the traced path begins - which is where a lap is measured from. */
function StartLine({
  path,
  length,
  width,
}: {
  path: SVGPathElement | null;
  length: number;
  width: number;
}) {
  if (!path || !length) return null;
  const a = path.getPointAtLength(0);
  const b = path.getPointAtLength(Math.min(6, length));
  const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
  const w = Math.max(width, 8);
  return (
    <g transform={`translate(${a.x} ${a.y}) rotate(${angle})`}>
      <rect x={-w * 0.08} y={-w * 0.7} width={w * 0.16} height={w * 1.4} fill="#495057" />
    </g>
  );
}

function Ticker({
  events,
  t,
}: {
  events: { t: number; text: string }[];
  t: number;
}) {
  const shown = events.filter((e) => e.t <= t).slice(-9).reverse();
  return (
    <ul className="max-h-72 divide-y divide-line-soft overflow-y-auto">
      {shown.length === 0 && (
        <li className="px-3 py-2 text-sm text-muted">Nothing yet.</li>
      )}
      {shown.map((e, i) => (
        <li key={`${e.t}-${i}`} className="flex gap-3 px-3 py-1.5 text-sm">
          <span className="nums w-12 shrink-0 text-right text-xs text-muted">
            {e.t.toFixed(1)}s
          </span>
          <span className={i === 0 ? "font-medium" : "text-ink-soft"}>{e.text}</span>
        </li>
      ))}
    </ul>
  );
}

/** A few places worth jumping to: the blue shells, then the last lap. */
function jumpPoints(data: { events: { t: number; text: string }[]; duration: number }) {
  const blues = data.events
    .filter((e) => e.text.startsWith("Blue shell"))
    .slice(0, 3)
    .map((e) => ({ t: e.t, text: `blue at ${Math.round(e.t)}s` }));
  const flag = data.events.find((e) => e.text.includes("takes the flag"));
  return flag ? [...blues, { t: flag.t, text: "the finish" }] : blues;
}
