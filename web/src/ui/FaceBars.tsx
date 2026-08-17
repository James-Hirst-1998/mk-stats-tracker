// One bar per player, with their face on it. The same chart the older viewer
// puts its points and blue shells on.
//
// The scale is fixed by the caller rather than by the data, so a bar growing
// into empty space is the thing you read.

import { Face, colorOf } from "./common";

export interface BarRow {
  player: number;
  label: string;
  character: string | null;
  value: number;
}

export function FaceBars({
  rows,
  max,
  unit,
  empty = "Nothing yet.",
}: {
  rows: BarRow[];
  max: number;
  unit: string;
  empty?: string;
}) {
  const top = Math.max(max, 1);
  if (rows.every((r) => r.value === 0))
    return <p className="px-5 py-8 text-center text-sm text-muted">{empty}</p>;

  return (
    <ul className="space-y-3 px-5 py-4">
      {rows.map((r) => (
        <li key={r.player} className="flex items-center gap-3">
          <Face
            character={r.character}
            color={colorOf(r.player)}
            label={r.label}
            size={44}
          />
          <span className="w-24 shrink-0 truncate text-sm font-medium">
            {r.label}
          </span>
          <span className="h-6 flex-1 overflow-hidden rounded-full bg-line-soft">
            <span
              className="block h-full rounded-full transition-[width] duration-300"
              style={{
                width: `${Math.max(0, Math.min(1, r.value / top)) * 100}%`,
                background: colorOf(r.player),
              }}
            />
          </span>
          <span className="nums w-20 shrink-0 text-right text-sm font-semibold">
            {r.value}
            <span className="ml-1 text-xs font-normal text-muted">{unit}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
