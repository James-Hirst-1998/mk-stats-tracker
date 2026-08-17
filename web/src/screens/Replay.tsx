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
import { trackFor } from "../data/tracks";
import { oriented, useStarts } from "../lib/route";
import { CHARACTERS } from "../data/names";
import {
  Card,
  Face,
  Segmented,
  colorOf,
  faceUrl,
  nameOf,
  secs,
  slug,
  type NameMode,
} from "../ui/common";
import { TrackShape } from "../ui/TrackShape";

const SPEEDS = ["1", "2", "4", "8"] as const;

export function Replay({ dir, file }: { dir: string; file: string }) {
  const { stats, log, error } = useRace(dir, file);
  const [starts] = useStarts();
  const players = stats?.players ?? [];
  const data = useMemo(
    () => (log ? replayData(log, players) : null),
    [log, players],
  );

  // The same Characters/Names choice the dashboard is showing.
  const mode = (localStorage.getItem("mkw.mode") as NameMode) ?? "characters";
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>("2");
  const path = useRef<SVGPathElement>(null);
  const [length, setLength] = useState(0);

  const raw = data?.course != null ? trackFor(data.course) : null;
  const track = useMemo(
    () => (raw ? oriented(raw, starts[raw.course]) : null),
    [raw, starts],
  );

  useEffect(() => {
    if (path.current) setLength(path.current.getTotalLength());
  }, [track]);

  useEffect(() => {
    if (!playing || !data) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = ((now - last) / 1000) * Number(speed);
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
    return (
      <Shell dir={dir}>
        <Card className="p-5 text-sm">{error}</Card>
      </Shell>
    );
  if (!data || !log || !stats)
    return (
      <Shell dir={dir}>
        <Card className="p-5 text-sm text-muted">Loading…</Card>
      </Shell>
    );

  const progress = log.progressAt(t);
  const order = [...progress].sort((a, b) => b[1] - a[1]);
  const leader = order[0]?.[1] ?? 0;
  const slots = slotsOf(players, log);
  const bySlot = new Map([...slots].map(([i, s]) => [s, i]));
  const unit = track ? Math.max(track.size[0], track.size[1]) / 200 : 4;

  // Where a lap fraction puts a kart, and which way is sideways there. The
  // sideways part is only used to keep karts off each other: the logs record
  // how far round the lap somebody is and nothing about which side of the road
  // they were on, so lanes here mean nothing but "not on top of each other".
  const at = (p: number, lane: number) => {
    if (!path.current || !length) return { x: 0, y: 0 };
    const frac = ((p % 1) + 1) % 1;
    const point = path.current.getPointAtLength(frac * length);
    const ahead = path.current.getPointAtLength((frac * length + 2) % length);
    const dx = ahead.x - point.x;
    const dy = ahead.y - point.y;
    const len = Math.hypot(dx, dy) || 1;
    const off = lane * unit * 3.2;
    return { x: point.x - (dy / len) * off, y: point.y + (dx / len) * off };
  };

  const jumps = jumpPoints(data);

  return (
    <Shell dir={dir}>
      <div className="mb-5 flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="mr-auto">
          <h1 className="text-3xl font-bold tracking-tight text-brand-deep">
            {data.courseName}
          </h1>
          <p className="mt-0.5 text-sm text-ink-soft">
            {data.laps ?? "?"} laps · {secs(data.duration)}
            {stats.races.find((r) => r.file === file)?.n
              ? ` · race ${stats.races.find((r) => r.file === file)!.n}`
              : ""}
          </p>
        </div>
        <span className="nums rounded-full border border-line bg-white/80 px-4 py-1.5 text-lg font-semibold">
          {t.toFixed(1)}s
        </span>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[1.25fr_minmax(320px,1fr)]">
        <Card>
          <div className="flex justify-center px-3 pt-3">
            <TrackShape
              track={track}
              lineRef={path}
              start
              className="h-[min(62vh,600px)] w-auto max-w-full"
            >
              {order
                .slice()
                .reverse()
                .map(([slot, p]) => {
                  const player = bySlot.get(slot);
                  const racer = log.racer(slot);
                  const character = racer
                    ? (CHARACTERS[racer.character] ?? null)
                    : null;
                  const place = order.findIndex(([s]) => s === slot) + 1;
                  // Three lanes, by running order, so a pack reads as a pack
                  // rather than as one kart.
                  const point = at(p, ((place - 1) % 3) - 1);
                  return (
                    <Kart
                      key={slot}
                      x={point.x}
                      y={point.y}
                      unit={unit}
                      color={player != null ? colorOf(player) : "#adb5bd"}
                      character={character}
                      tracked={player != null}
                      place={place}
                      slot={slot}
                    />
                  );
                })}
            </TrackShape>
          </div>

          <div className="flex flex-wrap items-center gap-3 px-5 py-3">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="w-24 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep"
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
              className="min-w-40 flex-1"
            />
            <Segmented
              value={speed}
              onChange={setSpeed}
              options={SPEEDS.map((s) => ({ value: s, label: `${s}×` }))}
            />
          </div>

          {jumps.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-line-soft px-5 py-3">
              <span className="text-xs text-muted">jump to</span>
              {jumps.map((j) => (
                <button
                  key={j.t}
                  onClick={() => setT(Math.max(0, j.t - 2))}
                  className="rounded-full border border-line bg-white px-3 py-1 text-xs hover:bg-brand-soft"
                >
                  {j.text}
                </button>
              ))}
            </div>
          )}

          <p className="border-t border-line-soft px-5 py-3 text-xs text-muted">
            {!track ? (
              "No outline for this course yet — a generic loop, so only the order and the gaps mean anything."
            ) : track.source === "course" ? (
              "The course's own checkpoints: real road, real start line, real direction."
            ) : starts[track.course] ? (
              "The real course, traced from its layout drawing, with the start line and direction set by hand at #/tracks."
            ) : (
              <>
                The real course, but nobody has said where its start line is, so
                a lap is measured from wherever the tracing began.{" "}
                <a href="#/tracks" className="text-brand underline">
                  Set it
                </a>
                .
              </>
            )}{" "}
            How far round the lap each kart is comes from the log; which lane it
            sits in does not, and is only there to keep the pack apart.
          </p>
        </Card>

        <div className="space-y-5">
          <Card title="Running order">
            <ol className="divide-y divide-line-soft border-t border-line-soft">
              {order.map(([slot, p], i) => {
                const player = bySlot.get(slot);
                const racer = log.racer(slot);
                const name =
                  player != null
                    ? nameOf(players[player], mode, log.field.name(slot))
                    : log.field.name(slot);
                const gap =
                  i === 0 || !data.avgLap ? null : (leader - p) * data.avgLap;
                return (
                  <li
                    key={slot}
                    className={`flex items-center gap-2 px-4 py-1.5 text-sm ${
                      player == null ? "text-muted" : "bg-brand-soft/30"
                    }`}
                  >
                    <span className="nums w-5 text-right font-semibold">
                      {i + 1}
                    </span>
                    <Face
                      character={racer ? (CHARACTERS[racer.character] ?? null) : null}
                      color={player != null ? colorOf(player) : "#ced4da"}
                      label={name}
                      size={26}
                      ring={player != null}
                    />
                    <span className={player != null ? "font-semibold" : ""}>
                      {name}
                    </span>
                    <span className="nums ml-auto text-xs text-muted">
                      {gap == null ? "" : `+${gap.toFixed(1)}s`}
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="px-4 py-2 text-xs text-muted">
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

/** A racer on the course: a face for the players, a plain dot for the CPUs. */
function Kart({
  x,
  y,
  unit,
  color,
  character,
  tracked,
  place,
  slot,
}: {
  x: number;
  y: number;
  unit: number;
  color: string;
  character: string | null;
  tracked: boolean;
  place: number;
  slot: number;
}) {
  const r = tracked ? 5.6 * unit : 2.8 * unit;
  if (!tracked)
    return (
      <circle cx={x} cy={y} r={r} fill={color} stroke="#fff" strokeWidth={unit} />
    );
  const id = `face-${slot}-${slug(character ?? "x")}`;
  return (
    <g transform={`translate(${x} ${y})`}>
      <clipPath id={id}>
        <circle r={r} />
      </clipPath>
      <circle r={r} fill="#fff" />
      {character && (
        <image
          href={faceUrl(character)}
          x={-r}
          y={-r}
          width={2 * r}
          height={2 * r}
          clipPath={`url(#${id})`}
          preserveAspectRatio="xMidYMid slice"
        />
      )}
      <circle r={r} fill="none" stroke={color} strokeWidth={1.5 * unit} />
      <g transform={`translate(${r * 0.8} ${-r * 0.8})`}>
        <circle r={3.4 * unit} fill={color} stroke="#fff" strokeWidth={0.9 * unit} />
        <text
          y={1.3 * unit}
          textAnchor="middle"
          fill="#fff"
          fontSize={4 * unit}
          fontWeight="700"
        >
          {place}
        </text>
      </g>
    </g>
  );
}

function Shell({ dir, children }: { dir: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
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

function Ticker({
  events,
  t,
}: {
  events: { t: number; text: string }[];
  t: number;
}) {
  const shown = events.filter((e) => e.t <= t).slice(-9).reverse();
  return (
    <ul className="max-h-80 divide-y divide-line-soft overflow-y-auto border-t border-line-soft">
      {shown.length === 0 && (
        <li className="px-4 py-3 text-sm text-muted">Nothing yet.</li>
      )}
      {shown.map((e, i) => (
        <li key={`${e.t}-${i}`} className="flex gap-3 px-4 py-1.5 text-sm">
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
