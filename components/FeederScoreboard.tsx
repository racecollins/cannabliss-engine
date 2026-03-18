"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useState } from "react";

import type { FeederStat } from "@/types";
import { cn } from "@/lib/utils";
import { formatFractional, formatPercent } from "@/utils/formatters";

interface FeederScoreboardProps {
  data: FeederStat[];
}

type SortKey =
  | "feederName"
  | "candidates"
  | "admits"
  | "hitRate"
  | "avgEntryZone"
  | "avgSurvivalWeeks"
  | "topTenPromotions";

export function FeederScoreboard({ data }: FeederScoreboardProps) {
  const [sortKey, setSortKey] = useState<SortKey>("hitRate");
  const [descending, setDescending] = useState(true);

  const sorted = [...data].sort((a, b) => {
    const aValue = a[sortKey];
    const bValue = b[sortKey];

    if (typeof aValue === "string" && typeof bValue === "string") {
      return descending ? bValue.localeCompare(aValue) : aValue.localeCompare(bValue);
    }

    return descending ? Number(bValue) - Number(aValue) : Number(aValue) - Number(bValue);
  });

  function updateSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setDescending((current) => !current);
      return;
    }

    setSortKey(nextKey);
    setDescending(true);
  }

  function SortButton({ label, value }: { label: string; value: SortKey }) {
    const isActive = sortKey === value;
    const Icon = isActive ? (descending ? ArrowDown : ArrowUp) : ChevronsUpDown;

    return (
      <button
        type="button"
        onClick={() => updateSort(value)}
        className={cn(
          "inline-flex items-center gap-1 text-xs uppercase tracking-[0.18em] text-muted transition hover:text-white",
          isActive && "text-white",
        )}
      >
        {label}
        <Icon className="h-3.5 w-3.5" />
      </button>
    );
  }

  return (
    <div className="overflow-hidden rounded-[1.5rem] border border-white/10">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10 text-sm">
          <thead className="bg-white/[0.03]">
            <tr>
              <th className="px-4 py-3 text-left"><SortButton label="Feeder" value="feederName" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Candidates" value="candidates" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Admits" value="admits" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Hit Rate" value="hitRate" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Avg Entry Zone" value="avgEntryZone" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Avg Survival" value="avgSurvivalWeeks" /></th>
              <th className="px-4 py-3 text-right"><SortButton label="Top 10 Promotions" value="topTenPromotions" /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {sorted.map((feeder) => (
              <tr key={feeder.feederName} className="bg-transparent transition hover:bg-white/[0.03]">
                <td className="px-4 py-4">
                  <div className="inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-100">
                    {feeder.feederName}
                  </div>
                </td>
                <td className="px-4 py-4 text-right text-slate-200">{feeder.candidates}</td>
                <td className="px-4 py-4 text-right text-slate-200">{feeder.admits}</td>
                <td className="px-4 py-4 text-right font-medium text-accent">{formatPercent(feeder.hitRate)}</td>
                <td className="px-4 py-4 text-right text-slate-200">{feeder.avgEntryZone}</td>
                <td className="px-4 py-4 text-right text-slate-200">
                  {formatFractional(feeder.avgSurvivalWeeks)} wks
                </td>
                <td className="px-4 py-4 text-right text-slate-200">{feeder.topTenPromotions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
