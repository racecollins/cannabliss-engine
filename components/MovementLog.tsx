import { ArrowDownLeft, ArrowUpRight, RotateCcw, Sparkles, Trash2 } from "lucide-react";

import type { MovementEvent, MovementType } from "@/types";
import { cn } from "@/lib/utils";
import { formatCompactDate } from "@/utils/formatters";

interface MovementLogProps {
  data: MovementEvent[];
}

const movementMeta: Record<
  MovementType,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  promotion: { icon: ArrowUpRight, color: "text-accent bg-accent/10 border-accent/20", label: "Promoted" },
  demotion: { icon: ArrowDownLeft, color: "text-amber-300 bg-amber-400/10 border-amber-400/20", label: "Demoted" },
  entry: { icon: Sparkles, color: "text-sky bg-sky/10 border-sky/20", label: "New" },
  removal: { icon: Trash2, color: "text-rose bg-rose/10 border-rose/20", label: "Removed" },
  return: { icon: RotateCcw, color: "text-gold bg-gold/10 border-gold/20", label: "Returned" },
};

export function MovementLog({ data }: MovementLogProps) {
  return (
    <div className="relative space-y-0">
      <div className="absolute bottom-0 left-5 top-0 w-px bg-white/8" />

      {data.map((event, index) => {
        const meta = movementMeta[event.type];
        const Icon = meta.icon;
        const isLast = index === data.length - 1;

        return (
          <div
            key={`${event.timestamp}-${event.trackTitle}`}
            className={cn("relative flex gap-4 py-3", !isLast && "border-b border-white/5")}
          >
            <div
              className={cn(
                "relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border",
                meta.color,
              )}
            >
              <Icon className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-semibold text-white">
                  {event.trackTitle}
                </p>
                <span
                  className={cn(
                    "shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                    meta.color,
                  )}
                >
                  {meta.label}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                <span>{event.artist}</span>
                {event.zoneAfter && (
                  <span className="text-slate-400">
                    {event.zoneBefore ? `${event.zoneBefore} → ` : "→ "}
                    {event.zoneAfter}
                  </span>
                )}
                <span>{formatCompactDate(event.timestamp)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
