// Every course outline with its traced centreline drawn on top of it.
//
// This is how the tracing gets checked: tools/build_tracks.py finds the middle
// of the road by thinning the drawing, and the only way to know whether it
// found the road or something else is to look at all 32 at once. Reachable at
// #/tracks.

import { TRACKS } from "../data/tracks";
import { COURSES } from "../data/names";

export function Tracks() {
  const codes = Object.keys(COURSES).map(Number).sort((a, b) => a - b);
  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6">
      <a href="#/" className="mb-4 inline-block text-sm text-brand hover:underline">
        ← back to the night
      </a>
      <h1 className="text-xl font-semibold tracking-tight">Course outlines</h1>
      <p className="mb-4 max-w-2xl text-sm text-muted">
        The drawing is what the replay shows. The blue line is the centreline
        traced from it, which is what a lap fraction is measured along; the dot
        is where the path starts. A red border means no outline was traced.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        {codes.map((code) => {
          const t = TRACKS[code];
          return (
            <figure
              key={code}
              className={`rounded-lg border bg-card p-2 ${
                t ? "border-line" : "border-red-300"
              }`}
            >
              {t ? (
                <svg
                  viewBox={`0 0 ${t.size[0]} ${t.size[1]}`}
                  className="h-40 w-full"
                >
                  <image
                    href={t.image}
                    width={t.size[0]}
                    height={t.size[1]}
                    opacity={0.5}
                  />
                  <path
                    d={t.d}
                    fill="none"
                    stroke="#1976d2"
                    strokeWidth={2}
                    strokeLinecap="round"
                  />
                  <Start d={t.d} />
                </svg>
              ) : (
                <div className="flex h-40 items-center justify-center text-xs text-muted">
                  no outline
                </div>
              )}
              <figcaption className="mt-1 truncate text-[11px]" title={COURSES[code]}>
                {COURSES[code]}
              </figcaption>
              {t && (
                <div className="text-[10px] text-muted">
                  {t.closed ? "loop" : "open"} · road {t.width}px
                </div>
              )}
            </figure>
          );
        })}
      </div>
    </div>
  );
}

function Start({ d }: { d: string }) {
  const first = d.match(/M\s*([\d.]+)\s+([\d.]+)/);
  if (!first) return null;
  return (
    <circle cx={Number(first[1])} cy={Number(first[2])} r={4} fill="#e03131" />
  );
}
