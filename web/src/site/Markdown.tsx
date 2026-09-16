// Markdown from web/content, drawn with the typography styles in styles.css.
// The text is ours and bundled at build time, so it goes in as HTML.

import { marked } from "marked";
import { useMemo } from "react";

marked.use({
  renderer: {
    // Links off the site open in a new tab; hash links stay in this one.
    link({ href, title, tokens }) {
      const text = this.parser.parseInline(tokens);
      const away = /^https?:/.test(href) ? ' target="_blank" rel="noreferrer"' : "";
      const titled = title ? ` title="${title}"` : "";
      return `<a href="${href}"${titled}${away}>${text}</a>`;
    },
  },
});

export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  const html = useMemo(() => marked.parse(text, { async: false }), [text]);
  return (
    <div className={`prose prose-site max-w-none ${className}`} dangerouslySetInnerHTML={{ __html: html }} />
  );
}
