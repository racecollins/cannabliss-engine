"use client";

import { Activity, Flame, Music2, TrendingUp, Users } from "lucide-react";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import type { DashboardDataset } from "@/types";
import { BreakoutWatchTable } from "@/components/BreakoutWatchTable";
import { FeederScoreboard } from "@/components/FeederScoreboard";
import { MovementLog } from "@/components/MovementLog";
import { NewThisWeek } from "@/components/NewThisWeek";
import { PlaylistStructureBar } from "@/components/PlaylistStructureBar";
import { TopTenSnapshot } from "@/components/TopTenSnapshot";
import {
  formatCompactDate,
  formatDelta,
  formatNumber,
} from "@/utils/formatters";

import { DashboardShell } from "./dashboard-shell";
import { SectionHeader } from "./section-header";
import { StatCard } from "./stat-card";

const FollowerGrowthChart = dynamic(
  () => import("@/charts/FollowerGrowthChart").then((mod) => mod.FollowerGrowthChart),
  {
    ssr: false,
    loading: () => <div className="h-[280px] rounded-2xl border border-white/8 bg-black/20" />,
  },
);

const WeeklyActivityChart = dynamic(
  () => import("@/charts/WeeklyActivityChart").then((mod) => mod.WeeklyActivityChart),
  {
    ssr: false,
    loading: () => <div className="h-[260px] rounded-2xl border border-white/8 bg-black/20" />,
  },
);

const growthRanges = [
  { label: "7D", count: 2 },
  { label: "30D", count: 5 },
  { label: "90D", count: 12 },
] as const;

type GrowthRangeLabel = "7D" | "30D" | "90D" | "1Y";

type DashboardDataStatus = {
  usingLocalRunData: boolean;
  latestRunTimestamp: string | null;
  coverage: {
    followerHistory: string;
    weeklyActivity: string;
    feederStats: string;
    zoneStats: string;
    breakoutTracks: string;
    movementEvents: string;
    topTenTracks: string;
  };
  source: "spotify+local" | "local-fallback";
  sourceDetail?: string;
  playlistName?: string | null;
};

interface DashboardViewProps {
  dashboardData: DashboardDataset;
  dashboardDataStatus: DashboardDataStatus;
}

export function DashboardView({
  dashboardData,
  dashboardDataStatus,
}: DashboardViewProps) {
  const [growthRange, setGrowthRange] = useState<GrowthRangeLabel>("90D");
  const {
    breakoutTracks,
    feederStats,
    followerHistory,
    movementEvents,
    topTenTracks,
    weeklyActivity,
    zoneStats,
  } = dashboardData;

  const resolvedGrowthRanges = [
    ...growthRanges,
    { label: "1Y" as const, count: followerHistory.length },
  ];

  const growthSlice = useMemo(() => {
    const count = resolvedGrowthRanges.find((item) => item.label === growthRange)?.count ?? 12;
    return followerHistory.slice(-count);
  }, [growthRange, followerHistory, resolvedGrowthRanges]);

  const latestFollowers = followerHistory.at(-1)?.followers ?? 0;
  const sevenDayGrowth = followerHistory.at(-1)?.weeklyChange ?? 0;
  const playlistSize = zoneStats.reduce((sum, zone) => sum + zone.trackCount, 0);
  const latestActivity =
    weeklyActivity[0] ?? {
      weekStart: new Date().toISOString(),
      additions: 0,
      removals: 0,
      promotions: 0,
      demotions: 0,
      hallOfFameReturns: 0,
    };
  const netChange = latestActivity.additions - latestActivity.removals;

  const kpis = [
    {
      label: "Followers",
      value: formatNumber(latestFollowers),
      delta: `${formatDelta(sevenDayGrowth)} this week`,
      direction: "up" as const,
      icon: <Users className="h-4 w-4" />,
    },
    {
      label: "Playlist Size",
      value: formatNumber(playlistSize),
      delta: "Target: 100",
      direction: "neutral" as const,
      icon: <Music2 className="h-4 w-4" />,
    },
    {
      label: "Weekly Net",
      value: `${netChange >= 0 ? "+" : ""}${netChange}`,
      delta: `${latestActivity.additions} in / ${latestActivity.removals} out`,
      direction: netChange >= 0 ? ("up" as const) : ("down" as const),
      icon: <Activity className="h-4 w-4" />,
    },
    {
      label: "Promotions",
      value: String(latestActivity.promotions),
      delta: `${latestActivity.demotions} demotions`,
      direction: latestActivity.promotions > 0 ? ("up" as const) : ("neutral" as const),
      icon: <TrendingUp className="h-4 w-4" />,
    },
  ];

  return (
    <DashboardShell
      title="Cannabliss"
      subtitle="Playlist intelligence and curation analytics"
      statusPills={
        <>
          {dashboardDataStatus.source === "spotify+local" ? (
            <span className="rounded-lg border border-accent/20 bg-accent/8 px-2.5 py-1 text-[11px] font-medium text-accent">
              Live
            </span>
          ) : (
            <span className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-400">
              Offline
            </span>
          )}
          {dashboardDataStatus.latestRunTimestamp && (
            <span className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-500">
              Updated {formatCompactDate(dashboardDataStatus.latestRunTimestamp)}
            </span>
          )}
        </>
      }
    >
      {/* ─── KPI Row ─── */}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <StatCard key={kpi.label} {...kpi} />
        ))}
      </section>

      {/* ─── Follower Growth + Weekly Activity ─── */}
      <section className="grid gap-5 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="panel p-5">
          <SectionHeader
            title="Follower Growth"
            action={
              <div className="inline-flex rounded-xl border border-white/8 bg-black/20 p-0.5">
                {resolvedGrowthRanges.map((range) => (
                  <button
                    key={range.label}
                    type="button"
                    onClick={() => setGrowthRange(range.label)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                      growthRange === range.label
                        ? "bg-white/10 text-white"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            }
          />
          <div className="mt-4">
            <FollowerGrowthChart data={growthSlice} />
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="Weekly Activity" />
          <div className="mt-4">
            <WeeklyActivityChart data={[...weeklyActivity].reverse()} />
          </div>
        </div>
      </section>

      {/* ─── New This Week ─── */}
      <section className="panel px-5 py-4">
        <NewThisWeek events={movementEvents} />
      </section>

      {/* ─── Playlist Structure (with zone metrics) ─── */}
      <section className="panel p-5">
        <SectionHeader
          title="Playlist Structure"
          description="Tier distribution, tenure, and flow rates"
        />
        <div className="mt-4">
          <PlaylistStructureBar data={zoneStats} />
        </div>
      </section>

      {/* ─── Top 10 + Breakout Watch ─── */}
      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="panel p-5">
          <SectionHeader
            title="Top 10"
            description="Premium tier with movement indicators"
            action={
              <span className="rounded-lg border border-accent/20 bg-accent/8 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent">
                Premium
              </span>
            }
          />
          <div className="mt-4">
            <TopTenSnapshot data={topTenTracks} />
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader
            title="Breakout Watch"
            description="Strongest upward momentum right now"
            action={
              <div className="flex items-center gap-1.5 text-xs text-accent">
                <Flame className="h-3.5 w-3.5" />
                Hot
              </div>
            }
          />
          <div className="mt-4">
            <BreakoutWatchTable data={breakoutTracks} />
          </div>
        </div>
      </section>

      {/* ─── Movement Feed + Feeder Scoreboard ─── */}
      <section className="grid gap-5 xl:grid-cols-[0.6fr_1.4fr]">
        <div className="panel p-5">
          <SectionHeader
            title="Movement Feed"
            description="Recent editorial actions"
            action={
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                Live
              </div>
            }
          />
          <div className="mt-4">
            <MovementLog data={movementEvents} />
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader
            title="Feeder Scoreboard"
            description="Source playlist performance and conversion rates"
          />
          <div className="mt-4">
            <FeederScoreboard data={feederStats} />
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="pb-4 text-center text-[11px] text-slate-600">
        {dashboardDataStatus.sourceDetail ?? "Cannabliss Control Center"}
      </footer>
    </DashboardShell>
  );
}
