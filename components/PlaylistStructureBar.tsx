"use client";

import { cn } from "@/lib/utils";
import type { ZoneStat } from "@/types";
import { formatFractional, formatPercent } from "@/utils/formatters";

interface PlaylistStructureBarProps {
  data: ZoneStat[];
}

const zoneStyles: Record<string, { bg: string; text: string; glow: string }> = {
  premium: {
    bg: "bg-accent/80",
    text: "text-accent",
    glow: "shadow-[0_0_12px_rgba(126,240,178,0.3)]",
  },
  high: {
    bg: "bg-sky/70",
    text: "text-sky",
    glow: "shadow-[0_0_12px_rgba(123,214,255,0.25)]",
  },
  discovery: {
    bg: "bg-gold/60",
    text: "text-gold",
    glow: "shadow-[0_0_12px_rgba(242,198,109,0.2)]",
  },
  stability: {
    bg: "bg-violet-400/50",
    text: "text-violet-300",
    glow: "",
  },
  library: {
    bg: "bg-white/20",
    text: "text-slate-400",
    glow: "",
  },
};

export function PlaylistStructureBar({ data }: PlaylistStructureBarProps) {
  const total = data.reduce((sum, zone) => sum + zone.trackCount, 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-300">
          {total} tracks across {data.length} tiers
        </p>
        <p className="text-xs text-muted">Target: 100</p>
      </div>

      {/* Segmented bar */}
      <div className="flex h-10 w-full gap-1 overflow-hidden rounded-2xl">
        {data.map((zone) => {
          const style = zoneStyles[zone.zoneId] ?? zoneStyles.library;
          const widthPercent = total > 0 ? (zone.trackCount / total) * 100 : 20;

          return (
            <div
              key={zone.zoneId}
              className={cn(
                "group relative flex items-center justify-center transition-all duration-300 hover:brightness-125",
                style.bg,
                style.glow,
              )}
              style={{ width: `${Math.max(widthPercent, 4)}%` }}
            >
              {widthPercent > 8 && (
                <span className="text-xs font-semibold text-white/90 drop-shadow-sm">
                  {zone.trackCount}
                </span>
              )}

              {/* Tooltip on hover */}
              <div className="pointer-events-none absolute -top-16 left-1/2 z-10 -translate-x-1/2 scale-0 rounded-xl border border-white/10 bg-panel/95 px-3 py-2 shadow-lg backdrop-blur-xl transition-transform group-hover:scale-100">
                <p className="whitespace-nowrap text-xs font-semibold text-white">
                  {zone.name}
                </p>
                <p className="whitespace-nowrap text-[11px] text-slate-400">
                  {zone.range} &middot; {zone.trackCount} tracks
                </p>
                <p className="mt-1 whitespace-nowrap text-[10px] text-slate-500">
                  {formatFractional(zone.avgWeeks)}w avg &middot;{" "}
                  {formatPercent(zone.promotionRate)} promo &middot;{" "}
                  {formatPercent(zone.dropOffRate)} drop
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Zone detail grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {data.map((zone) => {
          const style = zoneStyles[zone.zoneId] ?? zoneStyles.library;
          return (
            <div
              key={zone.zoneId}
              className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5"
            >
              <div className="flex items-center gap-2">
                <div className={cn("h-2 w-2 rounded-full", style.bg)} />
                <span className={cn("text-xs font-semibold", style.text)}>
                  {zone.range}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                {zone.name}
              </p>
              <div className="mt-2 flex gap-3 text-[10px]">
                <span className="text-slate-400">
                  <span className="font-medium text-slate-300">{formatFractional(zone.avgWeeks)}</span>w
                </span>
                <span className="text-slate-400">
                  <span className="font-medium text-slate-300">{formatPercent(zone.promotionRate)}</span> up
                </span>
                <span className="text-slate-400">
                  <span className="font-medium text-slate-300">{formatPercent(zone.dropOffRate)}</span> out
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
