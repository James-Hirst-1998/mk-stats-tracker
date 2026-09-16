// Every course outline, where its lap starts, and the lap itself.
//
// Three jobs. Check puts the layout drawing back behind the outline with the
// traced centreline on top, which is how the tracing gets looked at. Set
// start is the cheap fix when the trace is right and only its beginning and
// direction are not. Draw is the honest fix when the trace itself is wrong:
// click round the course and that is the lap, first click on the start line,
// in the direction it is driven.
//
// The pale shape under the road is everything in the drawing the lap does not
// run through, and it is drawn in every view: a lap that steps over blank
// paper looks like a bug in the drawing rather than a fork the trace took
// wrong, and a start line often belongs on one of those sections.

import { useState } from "react";
import { TRACKS } from "../data/tracks";
import { COURSES } from "../data/names";
import {
  useRoutes,
  useStarts,
  withRoute,
  type DrawnRoute,
  type Start,
} from "../lib/route";
import { Card, Segmented } from "../ui/common";
import { RouteOverlay, asRoute, type Draft } from "../ui/DrawRoute";
import { TrackShape } from "../ui/TrackShape";

type View = "route" | "check" | "set" | "draw";

export function Tracks() {
  const [view, setView] = useState<View>("route");
  const [starts, saveStarts] = useStarts();
  const [routes, saveRoutes] = useRoutes();
  const [drawing, setDrawing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>({ points: [], closed: true });
  const [live, setLive] = useState<[number, number] | null>(null);

  const codes = Object.keys(COURSES)
    .map(Number)
    .sort((a, b) => a - b);
  const needed = codes.filter((c) => TRACKS[c]?.source === "drawing");
  const set = needed.filter((c) => starts[c] || routes[c]);
  const drawn = needed.filter((c) => routes[c]);

  const putStart = (code: number, next: Start) =>
    saveStarts({ ...starts, [code]: next });

  const begin = (code: number) => {
    setDrawing(code);
    // Carry the drawn lap in so a course can be corrected rather than redone.
    const had = routes[code];
    setDraft(
      had ? { points: [...had.points], closed: had.closed } : { points: [], closed: true },
    );
    setLive(null);
  };

  const commit = async (code: number, route: DrawnRoute | null) => {
    const next = { ...routes };
    if (route) next[code] = route;
    else delete next[code];
    await saveRoutes(next);
    setDrawing(null);
    setDraft({ points: [], closed: true });
  };

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-8">
      <a href="#/stats" className="mb-4 inline-block text-sm text-brand hover:underline">
        ← back to stats
      </a>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="mr-auto">
          <h1 className="text-3xl font-bold tracking-tight text-brand-deep">
            Course outlines
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-soft">
            The road is a path, not a picture, so it stays sharp at any size.
            The drawing says nothing about where a lap starts or which way it is
            driven, and the tracing has to guess which way a fork goes. Both are
            settled here, once, and every replay uses them.
          </p>
        </div>
        <Segmented
          value={view}
          onChange={(v) => {
            setView(v);
            setDrawing(null);
          }}
          options={[
            { value: "route", label: "Route" },
            { value: "check", label: "Check" },
            { value: "set", label: "Set start" },
            { value: "draw", label: "Draw" },
          ]}
        />
      </div>

      {view === "set" && (
        <p className="mt-4 rounded-xl border border-brand/30 bg-brand-soft/60 px-4 py-3 text-sm">
          <strong>Click the start line on each course</strong> — wherever the
          finishing line actually is — then check the arrow is pointing the way
          you drive it, and hit <em>flip</em> if it is not. Saves as you go. The
          line snaps to the traced lap, so if it lands somewhere else the lap
          does not run where the start is, and the fix is to draw it.
          <span className="ml-2 text-muted">
            {set.length} of {needed.length} done.
          </span>
        </p>
      )}

      {view === "draw" && (
        <p className="mt-4 rounded-xl border border-brand/30 bg-brand-soft/60 px-4 py-3 text-sm">
          <strong>Click round the course to draw the lap</strong> — first click
          on the start line, then follow the road the way you drive it. A drawn
          lap replaces the traced one and needs no start point, because the
          first click is the start and the order is the direction. Hit{" "}
          <em>save</em> when you get back round.
          <span className="ml-2 text-muted">
            {drawn.length} of {needed.length} drawn.
          </span>
        </p>
      )}

      {(view === "route" || view === "check") && (
        <p className="mt-3 text-xs text-muted">
          {set.length} of {needed.length} courses have a start line,{" "}
          {drawn.length} have a lap drawn by hand. The palest shape is drawing
          the lap does not run through — road the trace missed, or scenery.
          {set.length < needed.length && (
            <>
              {" "}
              The rest start wherever the tracing did —{" "}
              <button onClick={() => setView("set")} className="text-brand underline">
                set them
              </button>
              , or{" "}
              <button onClick={() => setView("draw")} className="text-brand underline">
                draw them
              </button>
              .
            </>
          )}
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {codes.map((code) => {
          const raw = TRACKS[code];
          const isDrawing = drawing === code;
          const t = raw ? withRoute(raw, routes[code], starts[code]) : null;
          const has = Boolean(starts[code] || routes[code]) || raw?.source === "course";
          const unit = t ? Math.max(t.size[0], t.size[1]) / 200 : 4;
          return (
            <Card
              key={code}
              className={`overflow-hidden p-3 ${
                isDrawing
                  ? "ring-2 ring-brand"
                  : (view === "set" || view === "draw") && !has
                    ? "ring-2 ring-brand/40"
                    : ""
              }`}
            >
              {t ? (
                <TrackShape
                  track={t}
                  drawing={view === "check" || isDrawing}
                  line={view === "check"}
                  start={has && !isDrawing}
                  motion={view === "route" && has}
                  className={`h-52 w-full ${
                    view === "set" || isDrawing ? "cursor-crosshair" : ""
                  }`}
                  onPick={
                    view === "set"
                      ? (x, y) =>
                          putStart(code, {
                            x,
                            y,
                            reverse: starts[code]?.reverse ?? false,
                          })
                      : isDrawing
                        ? (x, y) =>
                            setDraft((d) => ({
                              ...d,
                              points: [
                                ...d.points,
                                [Math.round(x * 10) / 10, Math.round(y * 10) / 10],
                              ],
                            }))
                        : undefined
                  }
                  onHover={isDrawing ? setLive : undefined}
                >
                  {isDrawing && <RouteOverlay draft={draft} unit={unit} live={live} />}
                </TrackShape>
              ) : (
                <div className="flex h-52 items-center justify-center text-xs text-muted">
                  no outline
                </div>
              )}

              <div className="mt-2 flex items-baseline gap-2">
                <span
                  className="min-w-0 flex-1 truncate text-sm font-semibold"
                  title={COURSES[code]}
                >
                  {COURSES[code]}
                </span>
                {view === "set" && starts[code] && (
                  <button
                    onClick={() =>
                      putStart(code, { ...starts[code], reverse: !starts[code].reverse })
                    }
                    className="rounded-full border border-line bg-white px-2 py-0.5 text-xs font-medium hover:bg-brand-soft"
                  >
                    flip
                  </button>
                )}
              </div>

              {view === "draw" && raw ? (
                isDrawing ? (
                  <DrawControls
                    draft={draft}
                    setDraft={setDraft}
                    onSave={() => commit(code, asRoute(draft))}
                    onCancel={() => setDrawing(null)}
                  />
                ) : (
                  <div className="mt-1 flex items-center gap-2">
                    <button
                      onClick={() => begin(code)}
                      className="rounded-full bg-brand px-3 py-1 text-xs font-semibold text-white hover:bg-brand-deep"
                    >
                      {routes[code] ? "redraw" : "draw the lap"}
                    </button>
                    {routes[code] && (
                      <>
                        <span className="text-xs text-muted">
                          {routes[code].points.length} points
                        </span>
                        <button
                          onClick={() => commit(code, null)}
                          className="ml-auto text-xs text-muted underline hover:text-ink"
                        >
                          remove
                        </button>
                      </>
                    )}
                  </div>
                )
              ) : (
                <div className="text-xs text-muted">
                  {!raw
                    ? "not traced"
                    : raw.source === "course"
                      ? "course file · real start line"
                      : routes[code]
                        ? `lap drawn by hand · ${routes[code].points.length} points`
                        : starts[code]
                          ? `start set${starts[code].reverse ? " · reversed" : ""}`
                          : "no start line yet"}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function DrawControls({
  draft,
  setDraft,
  onSave,
  onCancel,
}: {
  draft: Draft;
  setDraft: (f: (d: Draft) => Draft) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const enough = draft.points.length >= 3;
  return (
    <div className="mt-1 space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          onClick={onSave}
          disabled={!enough}
          className="rounded-full bg-brand px-3 py-1 text-xs font-semibold text-white hover:bg-brand-deep disabled:opacity-40"
        >
          save
        </button>
        <button
          onClick={() => setDraft((d) => ({ ...d, points: d.points.slice(0, -1) }))}
          disabled={!draft.points.length}
          className="rounded-full border border-line bg-white px-2.5 py-1 text-xs hover:bg-line-soft disabled:opacity-40"
        >
          undo
        </button>
        <button
          onClick={() => setDraft((d) => ({ ...d, points: [] }))}
          disabled={!draft.points.length}
          className="rounded-full border border-line bg-white px-2.5 py-1 text-xs hover:bg-line-soft disabled:opacity-40"
        >
          clear
        </button>
        <button
          onClick={onCancel}
          className="ml-auto text-xs text-muted underline hover:text-ink"
        >
          cancel
        </button>
      </div>
      <label className="flex items-center gap-1.5 text-[11px] text-muted">
        <input
          type="checkbox"
          checked={draft.closed}
          onChange={(e) => setDraft((d) => ({ ...d, closed: e.target.checked }))}
        />
        joins back to the start
        <span className="ml-auto nums">{draft.points.length} points</span>
      </label>
    </div>
  );
}
