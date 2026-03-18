import cannablissStateJson from "@/data/cannabliss_state.json";

import type {
  BreakoutTrack,
  DashboardDataset,
  MovementEvent,
  TopTenTrack,
  WeeklyActivityEntry,
  ZoneStat,
} from "@/types";

import {
  dashboardMockData,
  feederStats as mockFeederStats,
  followerHistory as mockFollowerHistory,
} from "./mockData";

type LocalCannablissRun = {
  timestamp: string;
  track_ids?: string[];
  new_track_count?: number;
  summary?: {
    added?: string[];
    promoted?: string[];
    held?: string[];
    shifted_down?: string[];
    removed?: string[];
  };
  zones?: Record<string, string[]>;
};

const localState = cannablissStateJson as { runs?: LocalCannablissRun[] };
const localRuns = [...(localState.runs ?? [])].sort((a, b) =>
  a.timestamp.localeCompare(b.timestamp),
);

const latestRun = localRuns.at(-1);
const previousRun = localRuns.at(-2);

const zoneConfig = [
  { key: "premium_current", zoneId: "premium", name: "Premium Current", range: "1-10" },
  { key: "high_conviction", zoneId: "high", name: "High Conviction", range: "11-25" },
  { key: "discovery", zoneId: "discovery", name: "Discovery", range: "26-40" },
  { key: "stabilizers", zoneId: "stability", name: "Stability", range: "41-50" },
  { key: "library", zoneId: "library", name: "Library", range: "51-160" },
] as const;

function placeholderTrackTitle(trackId: string) {
  return `Track ${trackId.slice(0, 8)}`;
}

function placeholderArtist() {
  return "Spotify metadata pending";
}

function inferZoneLabel(position: number) {
  if (position <= 10) return "Premium Current";
  if (position <= 25) return "High Conviction";
  if (position <= 40) return "Discovery";
  if (position <= 50) return "Stability";
  return "Library";
}

function inferZoneKey(position: number) {
  if (position <= 10) return "premium_current";
  if (position <= 25) return "high_conviction";
  if (position <= 40) return "discovery";
  if (position <= 50) return "stabilizers";
  return "library";
}

function countTrackOccurrences(runs: LocalCannablissRun[]) {
  const counts = new Map<string, number>();

  for (const run of runs) {
    for (const trackId of run.track_ids ?? []) {
      counts.set(trackId, (counts.get(trackId) ?? 0) + 1);
    }
  }

  return counts;
}

function buildWeeklyActivity(runs: LocalCannablissRun[]): WeeklyActivityEntry[] {
  if (runs.length < 2) {
    return dashboardMockData.weeklyActivity;
  }

  return runs
    .slice(-8)
    .map((run) => ({
      weekStart: run.timestamp,
      additions: run.summary?.added?.length ?? run.new_track_count ?? 0,
      removals: run.summary?.removed?.length ?? 0,
      promotions: run.summary?.promoted?.length ?? 0,
      demotions: run.summary?.shifted_down?.length ?? 0,
      hallOfFameReturns: 0,
    }))
    .reverse();
}

function buildZoneStats(runs: LocalCannablissRun[]): ZoneStat[] {
  if (!latestRun?.zones) {
    return dashboardMockData.zoneStats;
  }

  const appearances = countTrackOccurrences(runs);

  return zoneConfig.map((zone, index) => {
    const trackIds = latestRun.zones?.[zone.key] ?? [];
    const fallback = dashboardMockData.zoneStats[index];
    const averageRunsPresent =
      trackIds.length > 0
        ? trackIds.reduce((sum, trackId) => sum + (appearances.get(trackId) ?? 1), 0) / trackIds.length
        : 0;
    const promotionPool =
      (latestRun.summary?.promoted ?? []).filter((trackId) => trackIds.includes(trackId)).length /
      Math.max(trackIds.length, 1);
    const removalPool =
      (latestRun.summary?.removed ?? []).filter((trackId) => trackIds.includes(trackId)).length /
      Math.max(trackIds.length, 1);

    return {
      zoneId: zone.zoneId,
      name: zone.name,
      range: zone.range,
      trackCount: trackIds.length,
      // Real weeks require dated historical snapshots. Until we have that, approximate using run presence.
      avgWeeks: Number((averageRunsPresent * 1.2).toFixed(1)) || fallback.avgWeeks,
      promotionRate: promotionPool || fallback.promotionRate,
      dropOffRate: removalPool || fallback.dropOffRate,
    };
  });
}

function buildTopTenTracks(runs: LocalCannablissRun[]): TopTenTrack[] {
  if (!latestRun?.track_ids?.length) {
    return dashboardMockData.topTenTracks;
  }

  const previousPositions = new Map<string, number>();
  const occurrences = countTrackOccurrences(runs);

  (previousRun?.track_ids ?? []).forEach((trackId, index) => {
    previousPositions.set(trackId, index + 1);
  });

  return latestRun.track_ids.slice(0, 10).map((trackId, index) => {
    const currentRank = index + 1;
    const previousRank = previousPositions.get(trackId);
    const changeDelta = previousRank ? currentRank - previousRank : -1;
    const changeDirection =
      previousRank == null ? "up" : changeDelta < 0 ? "up" : changeDelta > 0 ? "down" : "steady";

    return {
      rank: currentRank,
      trackTitle: placeholderTrackTitle(trackId),
      artist: placeholderArtist(),
      feeder: "Local state",
      weeksOnPlaylist: occurrences.get(trackId) ?? 1,
      changeDelta,
      changeDirection,
    };
  });
}

function buildBreakoutTracks(runs: LocalCannablissRun[]): BreakoutTrack[] {
  if (!latestRun?.track_ids?.length || !previousRun?.track_ids?.length) {
    return dashboardMockData.breakoutTracks;
  }

  const previousPositions = new Map<string, number>();
  previousRun.track_ids.forEach((trackId, index) => {
    previousPositions.set(trackId, index + 1);
  });

  const occurrences = countTrackOccurrences(runs);
  const breakout = latestRun.track_ids
    .map((trackId, index) => {
      const currentPosition = index + 1;
      const previousPosition = previousPositions.get(trackId) ?? currentPosition + 12;
      const movement = previousPosition - currentPosition;

      return {
        id: trackId,
        trackTitle: placeholderTrackTitle(trackId),
        artist: placeholderArtist(),
        currentZone: inferZoneLabel(currentPosition),
        sourceFeeder: "Local state",
        popularityDelta: movement,
        weeksOnPlaylist: occurrences.get(trackId) ?? 1,
        trendScore: Math.max(0.2, Math.min(1, movement / 20)),
      };
    })
    .filter((track) => track.popularityDelta > 0)
    .sort((a, b) => b.popularityDelta - a.popularityDelta)
    .slice(0, 6);

  return breakout.length > 0 ? breakout : dashboardMockData.breakoutTracks;
}

function buildMovementEvents(runs: LocalCannablissRun[]): MovementEvent[] {
  if (!latestRun) {
    return dashboardMockData.movementEvents;
  }

  const events: MovementEvent[] = [];
  const ts = latestRun.timestamp;

  for (const trackId of latestRun.summary?.promoted?.slice(0, 2) ?? []) {
    const position = latestRun.track_ids?.indexOf(trackId) ?? -1;
    events.push({
      timestamp: ts,
      description: "Moved upward in the latest Cannabliss run based on the stored local state.",
      type: "promotion",
      trackTitle: placeholderTrackTitle(trackId),
      artist: placeholderArtist(),
      zoneAfter: inferZoneLabel(position + 1),
      feederBadge: "Local state",
    });
  }

  for (const trackId of latestRun.summary?.added?.slice(0, 3) ?? []) {
    const position = latestRun.track_ids?.indexOf(trackId) ?? -1;
    events.push({
      timestamp: ts,
      description: "Entered the playlist in the latest saved run from the local Cannabliss state.",
      type: "entry",
      trackTitle: placeholderTrackTitle(trackId),
      artist: placeholderArtist(),
      zoneAfter: inferZoneLabel(position + 1),
      feederBadge: "Local state",
    });
  }

  for (const trackId of latestRun.summary?.removed?.slice(0, 2) ?? []) {
    events.push({
      timestamp: ts,
      description: "Removed in the latest saved run according to the local Cannabliss summary.",
      type: "removal",
      trackTitle: placeholderTrackTitle(trackId),
      artist: placeholderArtist(),
      zoneBefore: "Library",
    });
  }

  return events.length > 0 ? events : dashboardMockData.movementEvents;
}

const followerHistory = mockFollowerHistory;
const weeklyActivity = buildWeeklyActivity(localRuns);
const zoneStats = buildZoneStats(localRuns);
const topTenTracks = buildTopTenTracks(localRuns);
const breakoutTracks = buildBreakoutTracks(localRuns);
const movementEvents = buildMovementEvents(localRuns);

export const dashboardDataStatus = {
  usingLocalRunData: localRuns.length > 0,
  latestRunTimestamp: latestRun?.timestamp ?? null,
  coverage: {
    followerHistory: "mock",
    weeklyActivity: localRuns.length > 1 ? "local" : "mock",
    feederStats: "mock",
    zoneStats: latestRun?.zones ? "local+derived" : "mock",
    breakoutTracks: latestRun && previousRun ? "local+derived" : "mock",
    movementEvents: latestRun ? "local+derived" : "mock",
    topTenTracks: latestRun?.track_ids?.length ? "local+derived" : "mock",
  },
} as const;

export const dashboardData: DashboardDataset = {
  followerHistory,
  weeklyActivity,
  feederStats: mockFeederStats,
  zoneStats,
  breakoutTracks,
  movementEvents,
  topTenTracks,
};

