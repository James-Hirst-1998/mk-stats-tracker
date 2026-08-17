// A course, drawn from its outline rather than from a picture of it.
//
// tools/build_tracks.py emits the road as a path - both edges, plus a loop
// round anything the course encircles, filled even-odd - so the same course
// draws at 60px in a race list and at 600px in a replay without going soft.
// The drawing it was traced from is still available behind it, which is what
// #/tracks uses to check the tracing.

import type { RefObject } from "react";
import { FALLBACK, type Track } from "../data/tracks";

export function TrackShape({
  track,
  drawing = false,
  line = false,
  start = false,
  lineRef,
  className = "",
  children,
}: {
  track: Track | null;
  /** Show the source drawing faintly behind the outline. */
  drawing?: boolean;
  /** Show the traced centreline. */
  line?: boolean;
  /** Mark where the path begins, which is where a lap is measured from. */
  start?: boolean;
  /** Somewhere to measure lap fractions along. */
  lineRef?: RefObject<SVGPathElement | null>;
  className?: string;
  children?: React.ReactNode;
}) {
  const t = track ?? FALLBACK;
  const [w, h] = t.size;
  // One unit is about a pixel of the original drawing, so strokes stay the
  // same visual weight whatever size the drawing happened to be.
  const unit = Math.max(w, h) / 200;
  const pad = Math.max(t.width * 0.6, 4 * unit);
  const first = t.d.match(/M\s*([\d.]+)\s+([\d.]+)/);

  return (
    <svg
      viewBox={`${-pad} ${-pad} ${w + 2 * pad} ${h + 2 * pad}`}
      className={className}
      preserveAspectRatio="xMidYMid meet"
    >
      {drawing && t.image && (
        <image href={t.image} width={w} height={h} opacity={0.35} />
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

      {start && first && (
        <circle
          cx={Number(first[1])}
          cy={Number(first[2])}
          r={2.6 * unit}
          fill="#e03131"
          stroke="#fff"
          strokeWidth={unit}
        />
      )}

      {children}
    </svg>
  );
}
