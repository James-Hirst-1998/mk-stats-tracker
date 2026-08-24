// The small shared pieces: player colours, faces, cards, and number
// formatting.

import { useState } from "react";
import { CHARACTERS } from "../data/names";
import type { Player } from "../lib/stats";

/** Assigned by player index, never by rank - see the note in styles.css. */
export const PLAYER_COLORS = [
  "#2a78d6",
  "#eb6834",
  "#1baf7a",
  "#eda100",
  "#9c36b5",
  "#0c8599",
  "#e64980",
  "#5c7cfa",
];

export const colorOf = (i: number) => PLAYER_COLORS[i % PLAYER_COLORS.length];

/** The same slug tools/fetch_assets.py names the files with. */
export function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "x"
  );
}

export const faceUrl = (character: string) =>
  `/assets/characters/${slug(character)}.png`;

export type NameMode = "characters" | "names";

/** What to call a player: their name, or the character they are driving.
 *
 *  In Characters mode a race-specific character wins, because somebody who
 *  switched character for one race should read as who they actually drove. */
export function nameOf(
  player: Player,
  mode: NameMode,
  raceCharacter?: string | null,
): string {
  if (mode === "names") return player.name;
  return raceCharacter ?? player.characterName ?? player.name;
}

export function characterOf(player: Player, raceCharacter?: number | null) {
  const id = raceCharacter ?? player.character;
  return id == null ? null : (CHARACTERS[id] ?? null);
}

export function Face({
  character,
  color,
  label,
  size = 56,
  ring = true,
}: {
  character: string | null;
  color: string;
  label: string;
  size?: number;
  ring?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const initials = label
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  const frame = {
    width: size,
    height: size,
    boxShadow: ring ? `0 0 0 2px ${color}` : undefined,
  };
  if (!character || failed)
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded-xl font-semibold text-white"
        style={{ ...frame, background: color, fontSize: size * 0.34 }}
        title={label}
      >
        {initials}
      </div>
    );
  return (
    <img
      src={faceUrl(character)}
      alt={label}
      title={label}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className="shrink-0 rounded-xl bg-white object-contain"
      style={frame}
    />
  );
}

export function mmss(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  const whole = Math.floor(seconds);
  const ms = Math.round((seconds - whole) * 1000);
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

/** Seconds, for durations that are not lap times. */
export const secs = (x: number | null | undefined) =>
  x == null ? "-" : `${x.toFixed(1)}s`;

export const ordinal = (n: number | null | undefined) => (n == null ? "-" : `P${n}`);

export function Card({
  title,
  note,
  right,
  children,
  className = "",
}: {
  title?: string;
  note?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`card min-w-0 ${className}`}>
      {(title || right) && (
        <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-5 pt-4 pb-3">
          {title && (
            <h2 className="text-[15px] font-bold tracking-tight">
              {title}
              {note && (
                <span className="ml-2 text-xs font-normal text-muted">{note}</span>
              )}
            </h2>
          )}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

/** A row of buttons where exactly one is on. */
export function Tabs<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="flex gap-1 border-b border-line px-5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition ${
            value === o.value
              ? "border-brand text-brand"
              : "border-transparent text-muted hover:text-ink-soft"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Small pill switch, for Characters/Names and playback speed. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className = "",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <div
      className={`inline-flex overflow-hidden rounded-full border border-line bg-white/80 p-0.5 text-sm ${className}`}
    >
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-full px-3 py-1 transition ${
            value === o.value
              ? "bg-brand font-medium text-white"
              : "text-ink-soft hover:bg-line-soft"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const rankColor = (position: number | null | undefined) =>
  position === 1
    ? "text-gold"
    : position === 2
      ? "text-silver"
      : position === 3
        ? "text-bronze"
        : "text-ink-soft";

/** 1st, 2nd, 3rd get their metal; everybody else is just a number. */
export function Rank({ n, size = 30 }: { n: number; size?: number }) {
  const metal =
    n === 1
      ? { bg: "#fdf6dd", ink: "#8a6d1a", line: "#e6cf7a" }
      : n === 2
        ? { bg: "#f1f3f5", ink: "#5f6570", line: "#ced4da" }
        : n === 3
          ? { bg: "#fbeee2", ink: "#8a4f1c", line: "#e2bf9b" }
          : { bg: "#eef4fb", ink: "#5c7a99", line: "#d3e2f2" };
  return (
    <span
      className="nums inline-flex shrink-0 items-center justify-center rounded-full font-bold"
      style={{
        width: size,
        height: size,
        background: metal.bg,
        color: metal.ink,
        border: `1px solid ${metal.line}`,
        fontSize: size * 0.45,
      }}
    >
      {n}
    </span>
  );
}

export const suffix = (n: number) =>
  n === 1 ? "st" : n === 2 ? "nd" : n === 3 ? "rd" : "th";
