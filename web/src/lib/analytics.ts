// Visitor analytics for the hosted site, through PostHog's EU cloud.
//
// Only a production build reports, so a night of racing on `npm run dev`
// sends nothing. The key is a project's public one: it can send events but not
// read them. EU was checked on 2026-09-16 by posting the key to both clouds'
// /flags: EU answered 200, US 401.

const KEY = "phc_oCFiE3UppfAJDvzFawzKu9YfwzyfZVN4Dn6qEc5VxsGb";

export function startAnalytics() {
  if (!import.meta.env.PROD) return;
  // Loaded after the page, so the library is not in the first bundle.
  import("posthog-js").then(({ default: posthog }) =>
    posthog.init(KEY, {
      api_host: "https://eu.i.posthog.com",
      defaults: "2026-08-30",
      // Every route is in the hash (#/stats, #/race/...). These defaults drop
      // the hash from captured URLs and only count a path change as a new
      // page, so without both lines every page would be one pageview of /.
      capture_pageview: { path: true, hash: true },
      disable_capture_url_hashes: false,
    }),
  );
}
