// The two long pages. Each is one Markdown file in web/content.

import { journey, setup } from "./content";
import { SiteFooter } from "./Footer";
import { Markdown } from "./Markdown";

function Article({ text }: { text: string }) {
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-5 sm:py-10">
        <article className="card px-5 py-7 sm:px-10 sm:py-10">
          <Markdown text={text} />
        </article>
      </main>
      <SiteFooter />
    </>
  );
}

export const Setup = () => <Article text={setup} />;
export const Journey = () => <Article text={journey} />;
