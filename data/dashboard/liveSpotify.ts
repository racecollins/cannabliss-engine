import "server-only";

import cannablissStateJson from "@/data/cannabliss_state.json";
import type {
  BreakoutTrack,
  DashboardDataset,
  FeederStat,
  FollowerHistoryPoint,
  MovementEvent,
  TopTenTrack,
  WeeklyActivityEntry,
  ZoneStat,
} from "@/types";

import { dashboardMockData } from "./mockData";
import { dashboardData as fallbackDashboardData, dashboardDataStatus as fallbackDashboardDataStatus } from "./realData";

type SpotifyArtist = {
  name?: string;
};

type SpotifyTrack = {
  id?: string;
  name?: string;
  artists?: SpotifyArtist[];
  popularity?: number;
};

type SpotifyPlaylistItem = {
  added_at?: string;
  track?: SpotifyTrack | null;
  item?: SpotifyTrack | null;
};

type SpotifyPlaylist = {
  id?: string;
  name?: string;
  followers?: {
    total?: number;
  };
  tracks?: {
    total?: number;
  };
};

type SpotifyTracksResponse = {
  tracks?: (SpotifyTrack | null)[];
};

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

type TrackMeta = {
  id: string;
  trackTitle: string;
  artist: string;
  popularity: number;
  addedAt?: string;
};

const API_BASE = "https://api.spotify.com/v1";
const TOKEN_URL = "https://accounts.spotify.com/api/token";
const localState = cannablissStateJson as { runs?: LocalCannablissRun[] };
const localRuns = [...(localState.runs ?? [])].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
const latestRun = localRuns.at(-1);
const previousRun = localRuns.at(-2);

const zoneConfig = [
  { key: "premium_current", zoneId: "premium", name: "Premium Current", range: "1-10" },
  { key: "high_conviction", zoneId: "high", name: "High Conviction", range: "11-25" },
  { key: "discovery", zoneId: "discovery", name: "Discovery", range: "26-40" },
  { key: "stabilizers", zoneId: "stability", name: "Stability", range: "41-50" },
  { key: "library", zoneId: "library", name: "Library", range: "51-160" },
] as const;

function requireEnv(name: string) {
  return process.env[name]?.trim() ?? "";
}

function getTrackArtist(track: SpotifyTrack | null | undefined) {
  const artists = track?.artists?.map((artist) => artist.name).filter(Boolean) ?? [];
  return artists.join(", ") || "Unknown Artist";
}

function buildTrackMeta(item: SpotifyPlaylistItem): TrackMeta | null {
  const track = item.track ?? item.item;
  if (!track?.id || !track.name) {
    return null;
  }

  return {
    id: track.id,
    trackTitle: track.name,
    artist: getTrackArtist(track),
    popularity: track.popularity ?? 0,
    addedAt: item.added_at,
  };
}

function buildTrackMetaFromTrack(track: SpotifyTrack | null | undefined): TrackMeta | null {
  if (!track?.id || !track.name) {
    return null;
  }

  return {
    id: track.id,
    trackTitle: track.name,
    artist: getTrackArtist(track),
    popularity: track.popularity ?? 0,
  };
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

function inferZoneLabel(position: number) {
  if (position <= 10) return "Premium Current";
  if (position <= 25) return "High Conviction";
  if (position <= 40) return "Discovery";
  if (position <= 50) return "Stability";
  return "Library";
}

function buildDerivedFollowerHistory(currentFollowers: number): FollowerHistoryPoint[] {
  if (currentFollowers <= 0) {
    return dashboardMockData.followerHistory;
  }

  const base = dashboardMockData.followerHistory;
  return base.map((point) => ({
    date: point.date,
    followers: currentFollowers,
    weeklyChange: 0,
    velocity: 0,
  }));
}

function buildWeeklyActivity(runs: LocalCannablissRun[]): WeeklyActivityEntry[] {
  if (runs.length < 2) {
    return fallbackDashboardData.weeklyActivity;
  }

  return runs
    .slice(-8)
    .map((run, index, list) => {
      if (index === 0) {
        return {
          weekStart: run.timestamp,
          additions: run.summary?.added?.length ?? run.new_track_count ?? 0,
          removals: run.summary?.removed?.length ?? 0,
          promotions: run.summary?.promoted?.length ?? 0,
          demotions: run.summary?.shifted_down?.length ?? 0,
          hallOfFameReturns: 0,
        };
      }

      const previous = list[index - 1];
      const currentSet = new Set(run.track_ids ?? []);
      const previousSet = new Set(previous.track_ids ?? []);
      const additions = [...currentSet].filter((trackId) => !previousSet.has(trackId)).length;
      const removals = [...previousSet].filter((trackId) => !currentSet.has(trackId)).length;

      return {
        weekStart: run.timestamp,
        additions,
        removals,
        promotions: run.summary?.promoted?.length ?? 0,
        demotions: run.summary?.shifted_down?.length ?? 0,
        hallOfFameReturns: 0,
      };
    })
    .reverse();
}

function buildZoneStats(runs: LocalCannablissRun[]): ZoneStat[] {
  if (!latestRun?.zones) {
    return fallbackDashboardData.zoneStats;
  }

  const appearances = countTrackOccurrences(runs);

  return zoneConfig.map((zone, index) => {
    const trackIds = latestRun.zones?.[zone.key] ?? [];
    const fallback = fallbackDashboardData.zoneStats[index];
    const averageRunsPresent =
      trackIds.length > 0
        ? trackIds.reduce((sum, trackId) => sum + (appearances.get(trackId) ?? 1), 0) / trackIds.length
        : 0;

    return {
      zoneId: zone.zoneId,
      name: zone.name,
      range: zone.range,
      trackCount: trackIds.length,
      avgWeeks: Number((averageRunsPresent * 1.2).toFixed(1)) || fallback.avgWeeks,
      promotionRate:
        trackIds.length > 0
          ? (latestRun.summary?.promoted ?? []).filter((trackId) => trackIds.includes(trackId)).length / trackIds.length
          : fallback.promotionRate,
      dropOffRate:
        trackIds.length > 0
          ? (latestRun.summary?.removed ?? []).filter((trackId) => trackIds.includes(trackId)).length / trackIds.length
          : fallback.dropOffRate,
    };
  });
}

function findSourceFeeder(trackId: string, feederMembership: Map<string, string>) {
  return feederMembership.get(trackId) ?? "Cannabliss";
}

function buildTopTenTracks(
  liveTargetTracks: TrackMeta[],
  feederMembership: Map<string, string>,
  occurrences: Map<string, number>,
): TopTenTrack[] {
  if (liveTargetTracks.length === 0) {
    return fallbackDashboardData.topTenTracks;
  }

  const previousPositions = new Map<string, number>();
  (previousRun?.track_ids ?? []).forEach((trackId, index) => {
    previousPositions.set(trackId, index + 1);
  });

  return liveTargetTracks.slice(0, 10).map((track, index) => {
    const currentRank = index + 1;
    const previousRank = previousPositions.get(track.id);
    const changeDelta = previousRank == null ? -1 : currentRank - previousRank;
    const changeDirection =
      previousRank == null ? "up" : changeDelta < 0 ? "up" : changeDelta > 0 ? "down" : "steady";

    return {
      rank: currentRank,
      trackTitle: track.trackTitle,
      artist: track.artist,
      feeder: findSourceFeeder(track.id, feederMembership),
      weeksOnPlaylist: occurrences.get(track.id) ?? 1,
      changeDelta,
      changeDirection,
    };
  });
}

function buildBreakoutTracks(
  liveTargetTracks: TrackMeta[],
  feederMembership: Map<string, string>,
  occurrences: Map<string, number>,
): BreakoutTrack[] {
  if (liveTargetTracks.length === 0) {
    return fallbackDashboardData.breakoutTracks;
  }

  const previousPositions = new Map<string, number>();
  (previousRun?.track_ids ?? []).forEach((trackId, index) => {
    previousPositions.set(trackId, index + 1);
  });

  const breakout = liveTargetTracks
    .map((track, index) => {
      const currentPosition = index + 1;
      const previousPosition = previousPositions.get(track.id) ?? currentPosition + 10;
      const upwardMovement = previousPosition - currentPosition;

      return {
        id: track.id,
        trackTitle: track.trackTitle,
        artist: track.artist,
        currentZone: inferZoneLabel(currentPosition),
        sourceFeeder: findSourceFeeder(track.id, feederMembership),
        popularityDelta: upwardMovement > 0 ? upwardMovement : Math.max(1, Math.round(track.popularity / 18)),
        weeksOnPlaylist: occurrences.get(track.id) ?? 1,
        trendScore: Math.max(0.25, Math.min(1, (upwardMovement > 0 ? upwardMovement : track.popularity / 10) / 12)),
      };
    })
    .sort((a, b) => b.popularityDelta - a.popularityDelta)
    .slice(0, 6);

  return breakout.length > 0 ? breakout : fallbackDashboardData.breakoutTracks;
}

function buildMovementEvents(
  liveTargetTrackMap: Map<string, TrackMeta>,
  feederMembership: Map<string, string>,
): MovementEvent[] {
  if (!latestRun) {
    return fallbackDashboardData.movementEvents;
  }

  const events: MovementEvent[] = [];
  const timestamp = latestRun.timestamp;

  for (const trackId of latestRun.summary?.promoted?.slice(0, 2) ?? []) {
    const track = liveTargetTrackMap.get(trackId);
    if (!track) continue;
    const position = latestRun.track_ids?.indexOf(trackId) ?? -1;
    events.push({
      timestamp,
      description: "Promoted in the latest Cannabliss run and currently holding a stronger position.",
      type: "promotion",
      trackTitle: track.trackTitle,
      artist: track.artist,
      zoneAfter: inferZoneLabel(position + 1),
      feederBadge: findSourceFeeder(trackId, feederMembership),
    });
  }

  for (const trackId of latestRun.summary?.added?.slice(0, 3) ?? []) {
    const track = liveTargetTrackMap.get(trackId);
    if (!track) continue;
    const position = latestRun.track_ids?.indexOf(trackId) ?? -1;
    events.push({
      timestamp,
      description: "Entered the live Cannabliss playlist in the latest saved run.",
      type: "entry",
      trackTitle: track.trackTitle,
      artist: track.artist,
      zoneAfter: inferZoneLabel(position + 1),
      feederBadge: findSourceFeeder(trackId, feederMembership),
    });
  }

  return events.length > 0 ? events : fallbackDashboardData.movementEvents;
}

function buildFeederStats(
  liveTargetTracks: TrackMeta[],
  feederPlaylistMap: Map<string, { playlistName: string; trackIds: Set<string> }>,
  occurrences: Map<string, number>,
): FeederStat[] {
  if (feederPlaylistMap.size === 0) {
    return fallbackDashboardData.feederStats;
  }

  const positionMap = new Map<string, number>();
  liveTargetTracks.forEach((track, index) => {
    positionMap.set(track.id, index + 1);
  });

  const stats = [...feederPlaylistMap.values()].map((feeder) => {
    const admittedTrackIds = [...feeder.trackIds].filter((trackId) => positionMap.has(trackId));
    const admittedPositions = admittedTrackIds.map((trackId) => positionMap.get(trackId) ?? 160);
    const averagePosition =
      admittedPositions.length > 0
        ? admittedPositions.reduce((sum, position) => sum + position, 0) / admittedPositions.length
        : 160;
    const topTenPromotions = admittedPositions.filter((position) => position <= 10).length;
    const averageRunsPresent =
      admittedTrackIds.length > 0
        ? admittedTrackIds.reduce((sum, trackId) => sum + (occurrences.get(trackId) ?? 1), 0) / admittedTrackIds.length
        : 1;

    return {
      feederName: feeder.playlistName,
      candidates: feeder.trackIds.size,
      admits: admittedTrackIds.length,
      hitRate: feeder.trackIds.size > 0 ? admittedTrackIds.length / feeder.trackIds.size : 0,
      avgEntryZone: inferZoneLabel(Math.round(averagePosition)).replace("Premium Current", "1-10").replace("High Conviction", "11-25").replace("Discovery", "26-40").replace("Stability", "41-50").replace("Library", "51-160"),
      avgSurvivalWeeks: Number((averageRunsPresent * 1.2).toFixed(1)),
      topTenPromotions,
    };
  });

  return stats.sort((a, b) => b.hitRate - a.hitRate);
}

async function getAccessToken() {
  const clientId = requireEnv("SPOTIFY_CLIENT_ID");
  const clientSecret = requireEnv("SPOTIFY_CLIENT_SECRET");
  const refreshToken = requireEnv("SPOTIFY_REFRESH_TOKEN");

  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error("Missing Spotify credentials for live dashboard fetch.");
  }

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  });

  const auth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");
  const response = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Spotify auth failed with ${response.status}`);
  }

  const payload = (await response.json()) as { access_token?: string };
  if (!payload.access_token) {
    throw new Error("Spotify auth response did not include an access token.");
  }

  return payload.access_token;
}

async function spotifyGet<T>(accessToken: string, path: string, params?: Record<string, string>) {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
  }

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Spotify GET ${path} failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

async function getAllPlaylistItems(accessToken: string, playlistId: string) {
  const items: SpotifyPlaylistItem[] = [];
  let offset = 0;

  while (true) {
    const data = await spotifyGet<{ items?: SpotifyPlaylistItem[] }>(
      accessToken,
      `/playlists/${playlistId}/items`,
      {
        limit: "100",
        offset: String(offset),
      },
    );

    const batch = data.items ?? [];
    items.push(...batch);
    if (batch.length < 100) {
      break;
    }
    offset += 100;
  }

  return items;
}

async function getPlaylist(accessToken: string, playlistId: string) {
  return spotifyGet<SpotifyPlaylist>(accessToken, `/playlists/${playlistId}`, {
    fields: "id,name,followers(total),tracks(total)",
  });
}

async function getTracksByIds(accessToken: string, trackIds: string[]) {
  const uniqueTrackIds = [...new Set(trackIds.filter(Boolean))];
  const trackMap = new Map<string, TrackMeta>();

  for (let index = 0; index < uniqueTrackIds.length; index += 50) {
    const batch = uniqueTrackIds.slice(index, index + 50);
    if (batch.length === 0) {
      continue;
    }

    let data: SpotifyTracksResponse;
    try {
      data = await spotifyGet<SpotifyTracksResponse>(accessToken, "/tracks", {
        ids: batch.join(","),
      });
    } catch (error) {
      console.error("Dashboard supplemental track fetch failed for batch", batch, error);
      continue;
    }

    for (const track of data.tracks ?? []) {
      const meta = buildTrackMetaFromTrack(track);
      if (meta) {
        trackMap.set(meta.id, meta);
      }
    }
  }

  return trackMap;
}

export async function getDashboardData(): Promise<{
  data: DashboardDataset;
  status: DashboardDataStatus;
}> {
  try {
    const targetPlaylistId = requireEnv("CANNABLISS_TARGET_PLAYLIST_ID");
    if (!targetPlaylistId) {
      throw new Error("Missing CANNABLISS_TARGET_PLAYLIST_ID.");
    }

    const feederPlaylistIds = requireEnv("CANNABLISS_FEEDER_PLAYLIST_IDS")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    const accessToken = await getAccessToken();
    const [playlist, targetItems] = await Promise.all([
      getPlaylist(accessToken, targetPlaylistId),
      getAllPlaylistItems(accessToken, targetPlaylistId),
    ]);

    const liveTargetTracks = targetItems.map(buildTrackMeta).filter((value): value is TrackMeta => value !== null);
    const liveTargetTrackMap = new Map(liveTargetTracks.map((track) => [track.id, track]));
    const occurrences = countTrackOccurrences(localRuns);
    const currentFollowers = playlist.followers?.total ?? 0;

    const stateTrackIds = localRuns.flatMap((run) => [
      ...(run.track_ids ?? []),
      ...(run.summary?.added ?? []),
      ...(run.summary?.promoted ?? []),
      ...(run.summary?.held ?? []),
      ...(run.summary?.shifted_down ?? []),
      ...(run.summary?.removed ?? []),
      ...Object.values(run.zones ?? {}).flat(),
    ]);

    const unresolvedStateTrackIds = [...new Set(stateTrackIds)].filter(
      (trackId) => !liveTargetTrackMap.has(trackId),
    );
    const supplementalTrackMap = await getTracksByIds(accessToken, unresolvedStateTrackIds);
    const mergedTrackMap = new Map([...supplementalTrackMap, ...liveTargetTrackMap]);

    const feederPlaylistResults = await Promise.allSettled(
      feederPlaylistIds.map(async (playlistId) => {
        const [details, items] = await Promise.all([
          getPlaylist(accessToken, playlistId),
          getAllPlaylistItems(accessToken, playlistId),
        ]);

        const trackIds = new Set(
          items
            .map((item) => item.track?.id ?? item.item?.id)
            .filter((trackId): trackId is string => Boolean(trackId)),
        );

        return {
          playlistId,
          playlistName: details.name || `Feeder ${playlistId.slice(0, 6)}`,
          trackIds,
        };
      }),
    );
    const feederPlaylists = feederPlaylistResults
      .filter(
        (
          result,
        ): result is PromiseFulfilledResult<{
          playlistId: string;
          playlistName: string;
          trackIds: Set<string>;
        }> => result.status === "fulfilled",
      )
      .map((result) => result.value);
    const feederFailures = feederPlaylistResults.filter(
      (result): result is PromiseRejectedResult => result.status === "rejected",
    );

    const feederMembership = new Map<string, string>();
    const feederPlaylistMap = new Map<string, { playlistName: string; trackIds: Set<string> }>();

    for (const feeder of feederPlaylists) {
      feederPlaylistMap.set(feeder.playlistId, {
        playlistName: feeder.playlistName,
        trackIds: feeder.trackIds,
      });

      for (const trackId of feeder.trackIds) {
        if (!feederMembership.has(trackId)) {
          feederMembership.set(trackId, feeder.playlistName);
        }
      }
    }

    const data: DashboardDataset = {
      followerHistory: buildDerivedFollowerHistory(currentFollowers),
      weeklyActivity: buildWeeklyActivity(localRuns),
      feederStats: buildFeederStats(liveTargetTracks, feederPlaylistMap, occurrences),
      zoneStats: buildZoneStats(localRuns),
      breakoutTracks: buildBreakoutTracks(
        latestRun?.track_ids?.map((trackId) => mergedTrackMap.get(trackId)).filter((value): value is TrackMeta => Boolean(value)) ??
          liveTargetTracks,
        feederMembership,
        occurrences,
      ),
      movementEvents: buildMovementEvents(mergedTrackMap, feederMembership),
      topTenTracks: buildTopTenTracks(
        latestRun?.track_ids?.map((trackId) => mergedTrackMap.get(trackId)).filter((value): value is TrackMeta => Boolean(value)) ??
          liveTargetTracks,
        feederMembership,
        occurrences,
      ),
    };

    return {
      data,
      status: {
        usingLocalRunData: localRuns.length > 0,
        latestRunTimestamp: latestRun?.timestamp ?? null,
        coverage: {
          followerHistory: currentFollowers > 0 ? "spotify-live+derived-history" : "mock",
          weeklyActivity: localRuns.length > 1 ? "local-derived" : "mock",
          feederStats: feederPlaylistMap.size > 0 ? "spotify-live+derived" : "mock",
          zoneStats: latestRun?.zones ? "local-derived" : "mock",
          breakoutTracks: mergedTrackMap.size > 0 ? "spotify-live+local-derived" : "mock",
          movementEvents: mergedTrackMap.size > 0 ? "spotify-live+local-derived" : "mock",
          topTenTracks: mergedTrackMap.size > 0 ? "spotify-live+local-derived" : "mock",
        },
        source: "spotify+local",
        sourceDetail:
          currentFollowers > 0
            ? feederFailures.length > 0
              ? `Live Spotify playlist loaded. ${feederFailures.length} feeder playlist fetch${feederFailures.length === 1 ? "" : "es"} failed, so feeder coverage is partial.`
              : "Live Spotify playlist and track metadata loaded."
            : "Spotify connected with partial coverage.",
        playlistName: playlist.name ?? null,
      },
    };
  } catch (error) {
    console.error("Dashboard live Spotify fetch failed; falling back to local data.", error);
    return {
      data: fallbackDashboardData,
      status: {
        ...fallbackDashboardDataStatus,
        source: "local-fallback",
        sourceDetail:
          error instanceof Error
            ? `Using local fallback because Spotify fetch failed: ${error.message}`
            : "Using local fallback because Spotify fetch failed.",
        playlistName: null,
      },
    };
  }
}
