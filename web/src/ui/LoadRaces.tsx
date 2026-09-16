// Loading a session from files: drop the folder tools/track.py wrote, or
// pick it. The only way races reach a hosted copy of the dashboard.

import { useEffect, useRef, useState } from "react";
import { go } from "../App";
import { useHasApi } from "../lib/data";
import {
  forget,
  loadExample,
  loadFiles,
  useLocalSessions,
  type Picked,
} from "../lib/local";
import { Card } from "./common";

/** Everything under a dropped entry. A browser hands a dropped folder over as
 *  an entry to walk, not as a list of files. */
async function walk(entry: FileSystemEntry, into: string, out: Picked[]) {
  if (entry.isFile) {
    const file = await new Promise<File>((ok, fail) =>
      (entry as FileSystemFileEntry).file(ok, fail),
    );
    out.push({ path: into + entry.name, file });
    return;
  }
  if (!entry.isDirectory) return;
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  // readEntries gives a directory over in batches, and an empty one is the end.
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((ok, fail) =>
      reader.readEntries(ok, fail),
    );
    if (!batch.length) break;
    for (const child of batch) await walk(child, `${into}${entry.name}/`, out);
  }
}

/** Loads the example night and opens it. */
export function ExampleButton({
  className,
  children,
}: {
  className: string;
  children: React.ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const open = async () => {
    setBusy(true);
    setFailed(null);
    try {
      go(`/s/${await loadExample()}`);
    } catch (err) {
      setFailed(`Could not load the example: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button onClick={open} disabled={busy} className={className}>
        {busy ? "Loading…" : children}
      </button>
      {failed && <span className="text-xs text-muted">{failed}</span>}
    </>
  );
}

export function LoadRaces({ onClose }: { onClose?: () => void }) {
  const loaded = useLocalSessions();
  // The example is for visitors. Running locally, there are real races.
  const hosted = useHasApi() === false;
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const folderInput = useRef<HTMLInputElement>(null);
  const filesInput = useRef<HTMLInputElement>(null);

  // Not in React's attribute types, so set on the element itself.
  useEffect(() => {
    folderInput.current?.setAttribute("webkitdirectory", "");
  }, []);

  const read = async (picked: Picked[]) => {
    setBusy(true);
    setNotes([]);
    try {
      const { loaded: dirs, skipped } = await loadFiles(picked);
      setNotes(skipped);
      if (dirs.length) {
        onClose?.();
        go(`/s/${dirs[0]}`);
      }
    } catch (err) {
      setNotes([`Could not read those files: ${err instanceof Error ? err.message : err}`]);
    } finally {
      setBusy(false);
    }
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setOver(false);
    // Entries have to be taken before the first await; the drop's item list
    // is emptied once the handler yields.
    const entries = [...e.dataTransfer.items]
      .map((item) => item.webkitGetAsEntry())
      .filter((entry): entry is FileSystemEntry => entry != null);
    const picked: Picked[] = [];
    if (entries.length) for (const entry of entries) await walk(entry, "", picked);
    else for (const file of e.dataTransfer.files) picked.push({ path: file.name, file });
    read(picked);
  };

  const fromInput = (input: HTMLInputElement | null) => {
    const picked = [...(input?.files ?? [])].map((file) => ({
      path: file.webkitRelativePath || file.name,
      file,
    }));
    if (input) input.value = "";
    if (picked.length) read(picked);
  };

  return (
    <Card
      title="Load races"
      className="mt-5"
      right={
        onClose && (
          <button
            onClick={onClose}
            className="rounded-full border border-line px-3 py-0.5 text-xs hover:bg-line-soft"
          >
            Close
          </button>
        )
      }
    >
      <div className="px-5 pb-5">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-9 text-center transition-colors ${
            over ? "border-brand bg-brand-soft" : "border-line bg-white/60"
          }`}
        >
          <p className="text-base font-semibold text-ink">
            {busy ? "Reading…" : "Drop a session folder here"}
          </p>
          <p className="max-w-md text-sm text-ink-soft">
            The folder <code className="font-mono text-[13px]">tools/track.py</code> writes
            into <code className="font-mono text-[13px]">races/</code>, or just its{" "}
            <code className="font-mono text-[13px]">.jsonl</code> files. They are read in
            this browser and never uploaded.
          </p>
          <div className="mt-1 flex flex-wrap justify-center gap-2">
            <button
              onClick={() => folderInput.current?.click()}
              disabled={busy}
              className="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50"
            >
              Choose a folder
            </button>
            <button
              onClick={() => filesInput.current?.click()}
              disabled={busy}
              className="rounded-full border border-line bg-white px-4 py-1.5 text-sm hover:bg-line-soft disabled:opacity-50"
            >
              Choose files
            </button>
          </div>
          <input
            ref={folderInput}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => fromInput(e.currentTarget)}
          />
          <input
            ref={filesInput}
            type="file"
            multiple
            accept=".jsonl,.json"
            className="hidden"
            onChange={(e) => fromInput(e.currentTarget)}
          />
        </div>

        {hosted && (
          <div className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm text-ink-soft">
            <span>No races of your own?</span>
            <ExampleButton className="font-semibold text-brand hover:underline disabled:opacity-50">
              See an example night →
            </ExampleButton>
            <span className="text-muted">four players, Maple Treeway and Koopa Cape</span>
          </div>
        )}

        {notes.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-ink-soft">
            {notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}

        {loaded.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
              Loaded in this browser
            </p>
            <ul className="divide-y divide-line-soft rounded-xl border border-line bg-white">
              {loaded.map((s) => (
                <li key={s.dir} className="flex items-center gap-3 px-3 py-2 text-sm">
                  <a href={`#/s/${s.dir}`} className="mr-auto truncate text-brand hover:underline">
                    {s.meta.name}
                  </a>
                  <span className="nums text-muted">
                    {s.meta.started?.slice(0, 10)} · {s.meta.races.length} race
                    {s.meta.races.length === 1 ? "" : "s"}
                  </span>
                  <button
                    onClick={() => {
                      forget(s.dir);
                      if (window.location.hash.includes(s.dir)) go("/stats");
                    }}
                    className="rounded-full border border-line px-3 py-0.5 text-xs hover:bg-line-soft"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
