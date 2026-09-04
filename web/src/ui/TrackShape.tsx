// A course, drawn from its outline rather than from a picture of it.
//
// tools/build_tracks.py emits the road as a path - both edges, plus a loop
// round anything the course encircles, filled even-odd - so the same course
// draws at 60px in a race list and at 600px in a replay without going soft.
// The drawing it was traced from is still available behind it, which is what
// #/tracks uses to check the tracing.
//
// `rest` - the ink in the drawing the lap does not run through - is drawn
// under the road and paler. Some of it is road the trace missed and some of it
// is not road at all, so it is never the same colour as the road; it is there
// because a lap that jumps over blank paper looks broken, and because a start
// line or a drawn lap often belongs on it.

import type { RefObject } from "react";
import { FALLBACK, type Track } from "../data/tracks";
import { pointsOf } from "../lib/route";

export function TrackShape({
  track,
  drawing = false,
  line = false,
  start = false,
  motion = false,
  lineRef,
  className = "",
  onPick,
  onHover,
  children,
}: {
  track: Track | null;
  /** Show the source drawing faintly behind the outline. */
  drawing?: boolean;
  /** Show the traced centreline. */
  line?: boolean;
  /** Mark the start line, across the road, with a chevron for the direction. */
  start?: boolean;
  /** Run a dot round the lap, which is the quickest way to see the route. */
  motion?: boolean;
  /** Somewhere to measure lap fractions along. */
  lineRef?: RefObject<SVGPathElement | null>;
  className?: string;
  /** Called with a point in the course's own coordinates. */
  onPick?: (x: number, y: number) => void;
  /** The same, as the pointer moves. Null when it leaves. */
  onHover?: (point: [number, number] | null) => void;
  children?: React.ReactNode;
}) {
  const t = track ?? FALLBACK;
  const [w, h] = t.size;
  // One unit is about a pixel of the original drawing, so strokes stay the
  // same visual weight whatever size the drawing happened to be.
  const unit = Math.max(w, h) / 200;
  const pad = Math.max(t.width * 0.6, 4 * unit);
  const view = { x: -pad, y: -pad, w: w + 2 * pad, h: h + 2 * pad };

  // The viewBox is letterboxed into the element by xMidYMid meet, so undo the
  // fit before undoing the scale.
  const pointIn = (e: React.MouseEvent<SVGSVGElement>): [number, number] => {
    const box = e.currentTarget.getBoundingClientRect();
    const scale = Math.min(box.width / view.w, box.height / view.h);
    const left = box.left + (box.width - view.w * scale) / 2;
    const top = box.top + (box.height - view.h * scale) / 2;
    return [
      (e.clientX - left) / scale + view.x,
      (e.clientY - top) / scale + view.y,
    ];
  };

  const pick = onPick
    ? (e: React.MouseEvent<SVGSVGElement>) => {
        const [x, y] = pointIn(e);
        onPick(x, y);
      }
    : undefined;

  return (
    <svg
      viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
      className={className}
      preserveAspectRatio="xMidYMid meet"
      onClick={pick}
      onMouseMove={onHover ? (e) => onHover(pointIn(e)) : undefined}
      onMouseLeave={onHover ? () => onHover(null) : undefined}
    >
      {drawing && t.image && (
        <image href={t.image} width={w} height={h} opacity={0.35} />
      )}

      {t.rest && (
        <path
          d={t.rest}
          fillRule="evenodd"
          fill="var(--color-asphalt)"
          stroke="var(--color-asphalt)"
          strokeWidth={0.6 * unit}
          strokeLinejoin="round"
          opacity={0.5}
        />
      )}

      {t.outline ? (
        <path
          d={t.outline}
          fillRule="evenodd"
          fill="var(--color-asphalt)"
          stroke="var(--color-kerb)"
          strokeWidth={1.1 * unit}
          strokeLinejoin="round"
        />
      ) : (
        // No outline traced: the centreline drawn thick is the best guess at
        // the road, and it is the fallback loop's only shape.
        <path
          d={t.d}
          fill="none"
          stroke="var(--color-asphalt)"
          strokeWidth={t.width}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      <path
        ref={lineRef}
        d={t.d}
        fill="none"
        stroke={line ? "var(--color-brand)" : "none"}
        strokeWidth={line ? 1.4 * unit : 0}
        strokeDasharray={line ? `${3 * unit} ${3 * unit}` : undefined}
        strokeLinecap="round"
        opacity={line ? 0.85 : 1}
      />

      {start && <StartLine d={t.d} unit={unit} width={t.width} />}

      {motion && (
        <circle r={3 * unit} fill="var(--color-brand)" stroke="#fff" strokeWidth={unit}>
          <animateMotion dur="7s" repeatCount="indefinite" path={t.d} />
        </circle>
      )}

      {children}
    </svg>
  );
}

/** The line a lap is measured from, drawn across the road, with a chevron
 *  just past it pointing the way the lap runs. */
function StartLine({ d, unit, width }: { d: string; unit: number; width: number }) {
  const pts = pointsOf(d);
  if (pts.length < 3) return null;
  const [x, y] = pts[0];
  const ahead = pts[Math.min(3, pts.length - 1)];
  const angle = (Math.atan2(ahead[1] - y, ahead[0] - x) * 180) / Math.PI;
  const half = Math.max(width * 0.75, 5 * unit);
  return (
    <g transform={`translate(${x} ${y}) rotate(${angle})`}>
      <line
        x1={0}
        y1={-half}
        x2={0}
        y2={half}
        stroke="#e03131"
        strokeWidth={1.6 * unit}
        strokeLinecap="round"
      />
      <path
        d={`M ${3 * unit} ${-2.6 * unit} L ${7 * unit} 0 L ${3 * unit} ${2.6 * unit}`}
        fill="none"
        stroke="#e03131"
        strokeWidth={1.6 * unit}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </g>
  );
}
