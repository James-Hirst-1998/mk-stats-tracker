// Dated notes, newest first. One file each in web/content/updates.

import { UPDATES, longDate } from "./content";
import { SiteFooter } from "./Footer";
import { Markdown } from "./Markdown";

export function Updates() {
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-5 sm:py-10">
        <h1 className="text-3xl font-bold tracking-tight text-brand-deep">Updates</h1>
        <p className="mt-1 text-sm text-ink-soft">What changed, and when.</p>
        <ol className="mt-6 space-y-4">
          {UPDATES.map((u) => (
            <li key={u.slug} className="card px-5 py-5 sm:px-7">
              <p className="nums text-xs font-semibold tracking-wide text-muted uppercase">
                {longDate(u.date)}
              </p>
              <h2 className="mt-1 text-lg font-bold tracking-tight text-ink">{u.title}</h2>
              <Markdown text={u.body} className="prose-compact mt-2" />
            </li>
          ))}
        </ol>
      </main>
      <SiteFooter />
    </>
  );
}
