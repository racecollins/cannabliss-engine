import { ArrowUpRight, Flame } from "lucide-react";

import type { BreakoutTrack } from "@/types";
import { cn } from "@/lib/utils";
import { formatDelta } from "@/utils/formatters";

interface BreakoutWatchTableProps {
  data: BreakoutTrack[];
}

export function BreakoutWatchTable({ data }: BreakoutWatchTableProps) {
  return (
    <div className="space-y-2">
      {data.map((track, index) => {
        const intensity = Math.round(track.trendScore * 100);
        const isHot = intensity >= 60;

        return (
          <div
            key={track.id}
            className={cn(
              "flex items-center gap-4 rounded-2xl border px-4 py-3 transition-colors hover:bg-white/[0.04]",
              isHot ? "border-accent/15 bg-accent/[0.03]" : "border-white/8 bg-white/[0.02]",
            )}
          >
            {/* Rank indicator */}
            <div className="flex h-8 w-8 shrink-0 items-center justify-center">
              {isHot ? (
                <Flame className="h-4 w-4 text-accent" />
              ) : (
                <span className="text-xs font-medium text-slate-500">
                  {index + 1}
                </span>
              )}
            </div>

            {/* Track info */}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-white">
                {track.trackTitle}
              </p>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-400">
                <span>{track.artist}</span>
                <span className="text-slate-600">&middot;</span>
                <span>{track.currentZone}</span>
                <span className="text-slate-600">&middot;</span>
                <span>{track.weeksOnPlaylist}w</span>
              </div>
            </div>

            {/* Trend bar */}
            <div className="hidden w-20 items-center gap-2 sm:flex">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent to-sky"
                  style={{ width: `${Math.max(12, intensity)}%` }}
                />
              </div>
            </div>

            {/* Delta badge */}
            <span className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-accent/10 px-2 py-1 text-xs font-semibold text-accent">
              <ArrowUpRight className="h-3 w-3" />
              {formatDelta(track.popularityDelta)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
