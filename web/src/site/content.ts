// The written pages, as Markdown bundled into the site. Editing a file under
// web/content/ is the whole of updating one; see web/content/README.md.

import journey from "../../content/journey.md?raw";
import setup from "../../content/setup.md?raw";

export { journey, setup };

export interface Update {
  slug: string;
  /** From the file name, YYYY-MM-DD, so the order never depends on the text. */
  date: string;
  title: string;
  body: string;
}

const files = import.meta.glob("../../content/updates/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export const UPDATES: Update[] = Object.entries(files)
  .map(([path, text]) => {
    const slug = path.split("/").pop()!.replace(/\.md$/, "");
    const heading = text.match(/^#\s+(.+)$/m);
    return {
      slug,
      date: slug.slice(0, 10),
      title: heading?.[1].trim() ?? slug.slice(11),
      body: heading ? text.replace(heading[0], "").trim() : text.trim(),
    };
  })
  .sort((a, b) => b.slug.localeCompare(a.slug));

export const longDate = (date: string) =>
  new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
