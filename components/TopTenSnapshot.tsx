import { ArrowDownRight, ArrowUpRight, Minus, Sparkles } from "lucide-react";

import type { TopTenTrack } from "@/types";
import { cn } from "@/lib/utils";

interface TopTenSnapshotProps {
  data: TopTenTrack[];
}

const rankColors: Record<number, string> = {
  1: "from-accent/30 to-accent/5 border-accent/30",
  2: "from-sky/20 to-sky/5 border-sky/20",
  3: "from-gold/20 to-gold/5 border-gold/20",
};

export function TopTenSnapshot({ data }: TopTenSnapshotProps) {
  return (
    <div className="space-y-2">
      {data.map((track) => {
        const isTop3 = track.rank <= 3;
        const isNew = track.changeDirection === "up" && track.weeksOnPlaylist <= 1;

        return (
          <div
            key={track.rank}
            className={cn(
              "group flex items-center gap-3 rounded-2xl border px-4 py-3 transition-colors",
              isTop3
                ? `bg-gradient-to-r ${rankColors[track.rank]}`
                : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]",
            )}
          >
            <div
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold",
                isTop3 ? "bg-white/10 text-white" : "bg-white/5 text-slate-400",
              )}
            >
              {track.rank}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-semibold text-white">
                  {track.trackTitle}
                </p>
                {isNew && (
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-gold" />
                )}
              </div>
              <p className="mt-0.5 truncate text-xs text-slate-400">
                {track.artist}
                <span className="text-slate-500">
                  {" "}&middot; {track.weeksOnPlaylist}w
                </span>
              </p>
            </div>
            <div className="shrink-0">
              {track.changeDirection === "up" && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-accent/10 px-2 py-1 text-xs font-semibold text-accent">
                  <ArrowUpRight className="h-3 w-3" />
                  {Math.abs(track.changeDelta)}
                </span>
              )}
              {track.changeDirection === "down" && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-rose/10 px-2 py-1 text-xs font-semibold text-rose">
                  <ArrowDownRight className="h-3 w-3" />
                  {Math.abs(track.changeDelta)}
                </span>
              )}
              {track.changeDirection === "steady" && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-xs text-slate-500">
                  <Minus className="h-3 w-3" />
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
