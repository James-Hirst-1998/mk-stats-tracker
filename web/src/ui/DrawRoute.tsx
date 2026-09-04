// Drawing a lap by hand.
//
// The tracing gets the shape of the road right and still has to guess which
// way a fork goes, where a bridge cuts the road, and which end of a gap joins
// which. A drawn lap is somebody saying. Click round the course, first click
// on the start line, and that is the line a lap fraction is measured along -
// no start point and no reverse flag, because the first point and the order
// are both of those.

import type { DrawnRoute } from "../lib/route";

export interface Draft {
  points: [number, number][];
  closed: boolean;
}

export const asRoute = (draft: Draft): DrawnRoute => ({
  points: draft.points,
  closed: draft.closed,
});

/** The lap being drawn, over the course. Goes inside a TrackShape, so it is
 *  in the drawing's own coordinates. */
export function RouteOverlay({
  draft,
  unit,
  live,
}: {
  draft: Draft;
  unit: number;
  /** Where the pointer is, so the next segment is visible before the click. */
  live?: [number, number] | null;
}) {
  const pts = draft.points;
  if (!pts.length) return null;
  const line = pts.map((p) => p.join(",")).join(" ");
  const last = pts[pts.length - 1];
  return (
    <g>
      {draft.closed && pts.length > 2 && (
        <polygon points={line} fill="rgba(25,118,210,0.10)" stroke="none" />
      )}
      <polyline
        points={line}
        fill="none"
        stroke="#1976d2"
        strokeWidth={1.8 * unit}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {draft.closed && pts.length > 2 && (
        <line
          x1={last[0]}
          y1={last[1]}
          x2={pts[0][0]}
          y2={pts[0][1]}
          stroke="#1976d2"
          strokeWidth={1.8 * unit}
          strokeLinecap="round"
        />
      )}
      {live && !draft.closed && (
        <line
          x1={last[0]}
          y1={last[1]}
          x2={live[0]}
          y2={live[1]}
          stroke="#1976d2"
          strokeWidth={1.4 * unit}
          strokeDasharray={`${2 * unit} ${2 * unit}`}
          opacity={0.7}
        />
      )}
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={p[0]}
          cy={p[1]}
          r={(i === 0 ? 3.4 : 1.9) * unit}
          fill={i === 0 ? "#2f9e44" : "#1976d2"}
          stroke="#fff"
          strokeWidth={0.8 * unit}
        />
      ))}
      {pts.length > 1 && <Arrow a={pts[0]} b={pts[1]} unit={unit} />}
    </g>
  );
}

/** Which way the lap runs, on the first segment. */
function Arrow({
  a,
  b,
  unit,
}: {
  a: [number, number];
  b: [number, number];
  unit: number;
}) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const at = [a[0] + (dx / len) * 7 * unit, a[1] + (dy / len) * 7 * unit];
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  return (
    <g transform={`translate(${at[0]} ${at[1]}) rotate(${angle})`}>
      <path
        d={`M ${-2.4 * unit} ${-2.4 * unit} L ${2.6 * unit} 0 L ${-2.4 * unit} ${2.4 * unit} Z`}
        fill="#2f9e44"
        stroke="#fff"
        strokeWidth={0.6 * unit}
      />
    </g>
  );
}
