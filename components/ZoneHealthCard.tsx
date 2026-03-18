import type { ZoneStat } from "@/types";
import { cn } from "@/lib/utils";
import { formatFractional, formatPercent } from "@/utils/formatters";

interface ZoneHealthCardProps {
  data: ZoneStat[];
}

const zoneTone: Record<string, { bar: string; text: string; accent: string }> = {
  premium: { bar: "bg-accent", text: "text-accent", accent: "border-accent/20" },
  high: { bar: "bg-sky", text: "text-sky", accent: "border-sky/20" },
  discovery: { bar: "bg-gold", text: "text-gold", accent: "border-gold/20" },
  stability: { bar: "bg-violet-400", text: "text-violet-300", accent: "border-violet-400/20" },
  library: { bar: "bg-slate-500", text: "text-slate-400", accent: "border-white/10" },
};

export function ZoneHealthCard({ data }: ZoneHealthCardProps) {
  const maxTrackCount = Math.max(...data.map((z) => z.trackCount), 1);

  return (
    <div className="space-y-3">
      {data.map((zone) => {
        const tone = zoneTone[zone.zoneId] ?? zoneTone.library;
        const barWidth = Math.max(8, (zone.trackCount / maxTrackCount) * 100);

        return (
          <div
            key={zone.zoneId}
            className={cn(
              "rounded-2xl border bg-white/[0.02] p-4 transition-colors hover:bg-white/[0.04]",
              tone.accent,
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn("h-2 w-2 rounded-full", tone.bar)} />
                <p className="text-sm font-semibold text-white">
                  {zone.name}
                </p>
                <span className="text-xs text-slate-500">{zone.range}</span>
              </div>
              <span className={cn("text-sm font-bold", tone.text)}>
                {zone.trackCount}
              </span>
            </div>

            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
              <div
                className={cn("h-full rounded-full opacity-70", tone.bar)}
                style={{ width: `${barWidth}%` }}
              />
            </div>

            <div className="mt-3 flex gap-4 text-xs">
              <div>
                <span className="text-slate-500">Avg tenure </span>
                <span className="font-medium text-slate-300">{formatFractional(zone.avgWeeks)}w</span>
              </div>
              <div>
                <span className="text-slate-500">Promo </span>
                <span className="font-medium text-slate-300">{formatPercent(zone.promotionRate)}</span>
              </div>
              <div>
                <span className="text-slate-500">Drop </span>
                <span className="font-medium text-slate-300">{formatPercent(zone.dropOffRate)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
