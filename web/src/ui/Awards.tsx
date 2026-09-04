// Whole-session awards. The rules are in stats.ts and are fixed, so these are
// the same every time the same session is loaded, and a tie stays a tie.

import type { Awards as AwardSet, Player } from "../lib/stats";
import { colorOf } from "./common";

export function AwardList({
  awards,
  players,
  label,
}: {
  awards: AwardSet;
  players: Player[];
  label: (p: Player) => string;
}) {
  const named = (ids: number[]) =>
    ids.map((i) => label(players[i])).join(" and ") || "nobody";

  const items: { key: string; title: string; who: React.ReactNode; note: string }[] =
    [];

  if (awards.blueMagnet)
    items.push({
      key: "magnet",
      title: "Blue shell magnet",
      who: <Who ids={awards.blueMagnet.players} named={named} />,
      note: `${awards.blueMagnet.count} taken`,
    });

  if (awards.sniper)
    items.push({
      key: "sniper",
      title: "Sniper",
      who: <Who ids={awards.sniper.players} named={named} />,
      // Landed can exceed thrown: a triple is one throw in the log and can
      // land three times (docs/RACE_LOG.md, "Throws inside a triple").
      note: `${awards.sniper.landed} hit${awards.sniper.landed === 1 ? "" : "s"} from ${awards.sniper.thrown} throw${awards.sniper.thrown === 1 ? "" : "s"} · a triple is one throw`,
    });

  if (awards.firstBlood)
    items.push({
      key: "blood",
      title: "First blood",
      who:
        awards.firstBlood.player != null ? (
          <Who ids={[awards.firstBlood.player]} named={named} />
        ) : (
          <span className="font-semibold">{awards.firstBlood.name}</span>
        ),
      note: `opened ${awards.firstBlood.count} race${
        awards.firstBlood.count === 1 ? "" : "s"
      }`,
    });

  if (awards.collapse)
    items.push({
      key: "collapse",
      title: "The collapse",
      who: <Who ids={[awards.collapse.player]} named={named} />,
      note: `led ${awards.collapse.led}s, finished P${awards.collapse.position} · ${awards.collapse.courseName}`,
    });

  if (items.length === 0)
    return <p className="px-4 py-6 text-sm text-muted">Nothing has been earned yet.</p>;
  return (
    <ul className="divide-y divide-line-soft">
      {items.map((a) => (
        <li key={a.key} className="px-4 py-2.5">
          <div className="text-xs tracking-wide text-muted uppercase">{a.title}</div>
          <div className="mt-0.5 text-sm">{a.who}</div>
          <div className="text-xs text-muted">{a.note}</div>
        </li>
      ))}
    </ul>
  );
}

function Who({ ids, named }: { ids: number[]; named: (ids: number[]) => string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="flex -space-x-1">
        {ids.map((i) => (
          <span
            key={i}
            className="h-2.5 w-2.5 rounded-full ring-2 ring-white"
            style={{ background: colorOf(i) }}
          />
        ))}
      </span>
      <span className="font-semibold">{named(ids)}</span>
      {ids.length > 1 && <span className="text-xs text-muted">(tied)</span>}
    </span>
  );
}
