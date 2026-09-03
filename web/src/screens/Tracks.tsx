// Every course outline, and where its lap starts.
//
// Two jobs. It is how the tracing gets checked - Check puts the layout drawing
// back behind the outline with the traced centreline on top, and the only way
// to know the trace found the road is to look at all 32 at once. And it is
// where the two things no drawing knows get set: where the start line is and
// which way round the course is driven. Without those a replay puts everybody
// on the right road going a plausible-looking wrong way.

import { useState } from "react";
import { TRACKS } from "../data/tracks";
import { COURSES } from "../data/names";
import { oriented, useStarts, type Start } from "../lib/route";
import { Card, Segmented } from "../ui/common";
import { TrackShape } from "../ui/TrackShape";

type View = "route" | "check" | "set";

export function Tracks() {
  const [view, setView] = useState<View>("route");
  const [starts, save] = useStarts();
  const codes = Object.keys(COURSES)
    .map(Number)
    .sort((a, b) => a - b);

  const needed = codes.filter((c) => TRACKS[c]?.source === "drawing");
  const set = needed.filter((c) => starts[c]);

  const put = (code: number, next: Start) => save({ ...starts, [code]: next });

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
      <a href="#/" className="mb-4 inline-block text-sm text-brand hover:underline">
        ← back to stats
      </a>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="mr-auto">
          <h1 className="text-3xl font-bold tracking-tight text-brand-deep">
            Course outlines
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-soft">
            The road is a path, not a picture, so it stays sharp at any size.
            The drawing says nothing about where a lap starts or which way it
            is driven, so those are set here, once, and every replay uses them.
          </p>
        </div>
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: "route", label: "Route" },
            { value: "check", label: "Check" },
            { value: "set", label: "Set start" },
          ]}
        />
      </div>

      {view === "set" ? (
        <p className="mt-4 rounded-xl border border-brand/30 bg-brand-soft/60 px-4 py-3 text-sm">
          <strong>Click the start line on each course</strong> — wherever the
          finishing line actually is — then check the arrow is pointing the way
          you drive it, and hit <em>flip</em> if it is not. Saves as you go.
          <span className="ml-2 text-muted">
            {set.length} of {needed.length} done.
          </span>
        </p>
      ) : (
        <p className="mt-3 text-xs text-muted">
          {set.length} of {needed.length} courses have a start line.
          {set.length < needed.length && (
            <>
              {" "}
              The rest start wherever the tracing did —{" "}
              <button
                onClick={() => setView("set")}
                className="text-brand underline"
              >
                set them
              </button>
              .
            </>
          )}
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {codes.map((code) => {
          const raw = TRACKS[code];
          const t = raw ? oriented(raw, starts[code]) : null;
          const has = Boolean(starts[code]) || raw?.source === "course";
          return (
            <Card
              key={code}
              className={`overflow-hidden p-3 ${
                view === "set" && !has ? "ring-2 ring-brand/40" : ""
              }`}
            >
              {t ? (
                <TrackShape
                  track={t}
                  drawing={view === "check"}
                  line={view === "check"}
                  start={has}
                  motion={view !== "check" && has}
                  className={`h-52 w-full ${view === "set" ? "cursor-crosshair" : ""}`}
                  onPick={
                    view === "set"
                      ? (x, y) =>
                          put(code, {
                            x,
                            y,
                            reverse: starts[code]?.reverse ?? false,
                          })
                      : undefined
                  }
                />
              ) : (
                <div className="flex h-52 items-center justify-center text-xs text-muted">
                  no outline
                </div>
              )}

              <div className="mt-2 flex items-baseline gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-semibold" title={COURSES[code]}>
                  {COURSES[code]}
                </span>
                {view === "set" && starts[code] && (
                  <button
                    onClick={() =>
                      put(code, { ...starts[code], reverse: !starts[code].reverse })
                    }
                    className="rounded-full border border-line bg-white px-2 py-0.5 text-xs font-medium hover:bg-brand-soft"
                  >
                    flip
                  </button>
                )}
              </div>
              <div className="text-xs text-muted">
                {!raw
                  ? "not traced"
                  : raw.source === "course"
                    ? "course file · real start line"
                    : has
                      ? `start set${starts[code]?.reverse ? " · reversed" : ""}`
                      : "no start line yet"}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
