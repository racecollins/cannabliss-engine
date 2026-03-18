import { Sparkles } from "lucide-react";

import type { MovementEvent } from "@/types";

interface NewThisWeekProps {
  events: MovementEvent[];
}

export function NewThisWeek({ events }: NewThisWeekProps) {
  const newEntries = events.filter((e) => e.type === "entry");

  if (newEntries.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-sky">
        <Sparkles className="h-3.5 w-3.5" />
        New this week
      </div>
      {newEntries.map((entry) => (
        <div
          key={entry.trackTitle}
          className="flex items-center gap-2 rounded-xl border border-sky/15 bg-sky/5 px-3 py-1.5"
        >
          <span className="text-xs font-medium text-white">
            {entry.trackTitle}
          </span>
          <span className="text-[11px] text-slate-500">
            {entry.artist}
          </span>
          {entry.zoneAfter && (
            <span className="rounded-md bg-sky/10 px-1.5 py-0.5 text-[10px] font-medium text-sky">
              {entry.zoneAfter}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
