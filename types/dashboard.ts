export interface FollowerHistoryPoint {
  date: string; // ISO date string, will map to actual Spotify follower timestamps
  followers: number; // total follower count on that date
  weeklyChange: number; // follower delta vs prior week (used for velocity indicators)
  velocity: number; // normalized growth velocity for chart annotations
}

export interface WeeklyActivityEntry {
  weekStart: string; // ISO date for the week start (Sunday/Monday) from Cannabliss run logs
  additions: number; // tracks added to the playlist that week
  removals: number; // tracks removed (aged out or demoted)
  promotions: number; // tracks promoted deeper into premium zones
  demotions: number; // tracks demoted or returned to feeders
  hallOfFameReturns: number; // re-entries from the Hall of Fame archive
}

export interface FeederStat {
  feederName: string;
  candidates: number;
  admits: number; // tracks admitted to the playlist from this feeder
  hitRate: number; // portion of candidates that survived the first week
  avgEntryZone: string; // example: "11-25"
  avgSurvivalWeeks: number;
  topTenPromotions: number;
}

export interface ZoneStat {
  zoneId: string; // internal identifier for wiring UI palettes
  name: string; // human label for the zone
  range: string; // textual range (1-10, 11-25, etc.)
  trackCount: number; // how many tracks currently reside in the zone
  avgWeeks: number; // average tenure inside this zone
  promotionRate: number; // percent of tracks moving upward from this zone
  dropOffRate: number; // percent of tracks exiting downward or aging out
}

export interface BreakoutTrack {
  id: string;
  trackTitle: string;
  artist: string;
  currentZone: string;
  sourceFeeder: string;
  popularityDelta: number; // delta score vs prior snapshot
  weeksOnPlaylist: number;
  trendScore: number; // normalized indicator that drives visual badges
}

export type MovementType =
  | 'promotion'
  | 'demotion'
  | 'entry'
  | 'removal'
  | 'return';

export interface MovementEvent {
  timestamp: string; // ISO timestamp for ordering the editorial feed
  description: string; // short editorial summary
  type: MovementType;
  trackTitle: string;
  artist: string;
  zoneBefore?: string;
  zoneAfter?: string;
  feederBadge?: string;
}

export interface TopTenTrack {
  rank: number;
  trackTitle: string;
  artist: string;
  feeder: string;
  weeksOnPlaylist: number;
  changeDelta: number; // delta in rank (negative = rising)
  changeDirection: 'up' | 'down' | 'steady';
}

export interface DashboardDataset {
  followerHistory: FollowerHistoryPoint[];
  weeklyActivity: WeeklyActivityEntry[];
  feederStats: FeederStat[];
  zoneStats: ZoneStat[];
  breakoutTracks: BreakoutTrack[];
  movementEvents: MovementEvent[];
  topTenTracks: TopTenTrack[];
}
