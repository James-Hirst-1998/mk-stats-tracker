// Every course outline, with the drawing it was traced from behind it.
//
// This is how the tracing gets checked: tools/build_tracks.py finds the road
// by thinning the drawing, and the only way to know whether it found the road
// or something else is to look at all 32 at once. Reachable at #/tracks.

import { useState } from "react";
import { TRACKS } from "../data/tracks";
import { COURSES } from "../data/names";
import { Card, Segmented } from "../ui/common";
import { TrackShape } from "../ui/TrackShape";

type View = "outline" | "check";

export function Tracks() {
  const [view, setView] = useState<View>("outline");
  const codes = Object.keys(COURSES)
    .map(Number)
    .sort((a, b) => a - b);
  const traced = codes.filter((c) => TRACKS[c]).length;

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
      <a href="#/" className="mb-4 inline-block text-sm text-brand hover:underline">
        ← back to the night
      </a>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="mr-auto">
          <h1 className="text-3xl font-bold tracking-tight text-brand-deep">
            Course outlines
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-soft">
            The road is a path, not a picture, so it stays sharp at any size.
            Check pulls the layout drawing it was traced from up behind it, with
            the centreline a lap is measured along and a dot where that line
            starts.
          </p>
        </div>
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: "outline", label: "Outline" },
            { value: "check", label: "Check" },
          ]}
        />
      </div>

      <p className="mt-3 text-xs text-muted">
        {traced} of {codes.length} courses traced.
      </p>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {codes.map((code) => {
          const t = TRACKS[code];
          return (
            <Card key={code} className="overflow-hidden p-3">
              {t ? (
                <TrackShape
                  track={t}
                  drawing={view === "check"}
                  line={view === "check"}
                  start={view === "check"}
                  className="h-52 w-full"
                />
              ) : (
                <div className="flex h-52 items-center justify-center text-xs text-muted">
                  no outline
                </div>
              )}
              <div className="mt-2 truncate text-sm font-semibold" title={COURSES[code]}>
                {COURSES[code]}
              </div>
              <div className="text-xs text-muted">
                {t
                  ? `${t.source === "course" ? "course file" : "traced"} · ${
                      t.closed ? "loop" : "open"
                    }`
                  : "not traced"}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
