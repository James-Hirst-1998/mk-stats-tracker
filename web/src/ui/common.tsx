// The small shared pieces: player colours, faces, and number formatting.

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
  size = 44,
}: {
  character: string | null;
  color: string;
  label: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const initials = label
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  if (!character || failed)
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded-lg font-semibold text-white"
        style={{ width: size, height: size, background: color, fontSize: size * 0.36 }}
        title={label}
      >
        {initials}
      </div>
    );
  return (
    <img
      src={`/assets/characters/${slug(character)}.png`}
      alt={label}
      title={label}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className="shrink-0 rounded-lg bg-line-soft object-contain"
      style={{ width: size, height: size, boxShadow: `inset 0 0 0 2px ${color}33` }}
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
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-line bg-card shadow-[0_1px_2px_rgba(0,0,0,0.03)] ${className}`}
    >
      {(title || right) && (
        <header className="flex items-baseline justify-between gap-3 border-b border-line-soft px-4 py-3">
          {title && (
            <h2 className="text-[13px] font-semibold tracking-wide text-ink-soft uppercase">
              {title}
            </h2>
          )}
          {right}
        </header>
      )}
      {children}
    </section>
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
