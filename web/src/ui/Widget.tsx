// A widget: a small card that sits in a grid beside the others, and opens
// large when there is more to see.
//
// The screen is a set of these rather than a column of full-width cards so
// that the whole session is visible at once; the expanded view is the drill-
// down, and shows the same numbers with nothing summarised away.

import { useEffect, useState } from "react";

export function Widget({
  title,
  note,
  right,
  expanded,
  expandedTitle,
  className = "",
  children,
}: {
  title: string;
  note?: string;
  right?: React.ReactNode;
  /** The large version. Without it the widget has no expand button. */
  expanded?: React.ReactNode;
  expandedTitle?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    const was = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = was;
    };
  }, [open]);

  return (
    <>
      <section className={`card flex min-w-0 flex-col ${className}`}>
        <header className="flex items-baseline gap-x-3 px-4 pt-3 pb-2">
          <h2 className="min-w-0 flex-1 truncate text-[15px] font-bold tracking-tight">
            {title}
            {note && (
              <span className="ml-2 text-xs font-normal text-muted">{note}</span>
            )}
          </h2>
          {right}
          {expanded && (
            <button
              onClick={() => setOpen(true)}
              title="Expand"
              aria-label={`Expand ${title}`}
              className="-mr-1 rounded-md px-1.5 py-0.5 text-sm leading-none text-muted hover:bg-line-soft hover:text-ink"
            >
              ⤢
            </button>
          )}
        </header>
        <div className="min-h-0 flex-1">{children}</div>
      </section>

      {open && expanded && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/30 p-4 backdrop-blur-[2px] sm:p-8"
          onClick={() => setOpen(false)}
        >
          <section
            className="card my-auto w-full max-w-5xl bg-white"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label={expandedTitle ?? title}
          >
            <header className="flex items-baseline gap-3 border-b border-line-soft px-5 pt-4 pb-3">
              <h2 className="min-w-0 flex-1 text-lg font-bold tracking-tight">
                {expandedTitle ?? title}
                {note && (
                  <span className="ml-2 text-xs font-normal text-muted">{note}</span>
                )}
              </h2>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="rounded-full border border-line px-3 py-1 text-xs hover:bg-line-soft"
              >
                close · esc
              </button>
            </header>
            <div className="max-h-[80vh] overflow-auto">{expanded}</div>
          </section>
        </div>
      )}
    </>
  );
}

/** Where the widgets go: two across on a laptop, three on a wide screen. */
export function WidgetGrid({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`grid items-stretch gap-4 md:grid-cols-2 xl:grid-cols-3 ${className}`}>
      {children}
    </div>
  );
}
