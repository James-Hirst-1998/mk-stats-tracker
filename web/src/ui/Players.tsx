// Who the people at the controls are.
//
// A race log knows characters, not people: without this the tracked players
// are named after whoever they were driving, and the Characters/Names toggle
// has nothing to switch to. Saving writes races/<session>/players.json, which
// is the same file tools/report.py reads, so naming somebody here names them
// everywhere rather than only in this browser. A session loaded from files
// has no directory to write to, so its names are kept with the loaded copy.

import { useEffect, useState } from "react";
import { isLocal, saveLocalPlayers } from "../lib/local";
import type { PlayersFile, Player } from "../lib/stats";
import { Card, Face, colorOf } from "./common";

export function Players({
  dir,
  players,
  characterOf,
  onSaved,
  onClose,
}: {
  dir: string;
  players: Player[];
  characterOf: (p: Player) => string | null;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [names, setNames] = useState<string[]>(() => players.map((p) => p.name));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setNames(players.map((p) => p.name)), [players]);

  const save = async () => {
    setSaving(true);
    setError(null);
    const file: PlayersFile = {
      players: players.map((p, i) => ({
        name: names[i]?.trim() || p.name,
        // Kept from what the session already matched on, so renaming
        // somebody never changes which racer they are.
        ...(p.character != null ? { character: p.character } : {}),
        ...(p.human ? { human: true } : {}),
      })),
    };
    try {
      if (isLocal(dir)) {
        await saveLocalPlayers(dir, file);
      } else {
        const res = await fetch(`/api/session/${dir}/players`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(file),
        });
        if (!res.ok) {
          const said = await res.json().catch(() => null);
          throw new Error(said?.error || `${res.status}`);
        }
      }
      onSaved();
    } catch (err) {
      const said = String(err instanceof Error ? err.message : err);
      // The usual one: the session was recorded under sudo, so its directory
      // belongs to root and nothing running as a person can write into it.
      setError(
        /permission denied|EACCES|EPERM/i.test(said)
          ? `That session's files belong to root — run: sudo chown -R "$USER" races/${dir}`
          : `Could not save: ${said}`,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Who is who" className="mt-5">
      <p className="px-5 pb-3 text-sm text-ink-soft">
        Each row is a racer the logs found at a controller. Put a person's name
        against them and the Characters/Names toggle switches between the two.
      </p>
      <div className="grid gap-3 px-5 pb-4 sm:grid-cols-2">
        {players.map((p, i) => (
          <label
            key={p.index}
            className="flex items-center gap-3 rounded-xl border border-line bg-white px-3 py-2"
          >
            <Face
              character={characterOf(p)}
              color={colorOf(p.index)}
              label={p.name}
              size={40}
            />
            <span className="w-24 shrink-0 truncate text-sm text-muted">
              {characterOf(p) ?? `racer ${p.index + 1}`}
            </span>
            <input
              value={names[i] ?? ""}
              onChange={(e) =>
                setNames((was) => was.map((n, j) => (j === i ? e.target.value : n)))
              }
              placeholder="name"
              maxLength={40}
              className="min-w-0 flex-1 rounded-lg border border-line px-3 py-1.5 text-sm focus:border-brand focus:outline-none"
            />
          </label>
        ))}
      </div>
      <div className="flex items-center gap-3 border-t border-line-soft px-5 py-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save names"}
        </button>
        <button
          onClick={onClose}
          className="rounded-full border border-line px-4 py-1.5 text-sm hover:bg-line-soft"
        >
          Close
        </button>
        <span className="text-xs text-muted">
          {error ??
            (isLocal(dir)
              ? "Kept in this browser with the loaded files."
              : `Written to races/${dir}/players.json.`)}
        </span>
      </div>
    </Card>
  );
}
