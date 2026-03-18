import {
  BreakoutTrack,
  DashboardDataset,
  FeederStat,
  FollowerHistoryPoint,
  MovementEvent,
  TopTenTrack,
  WeeklyActivityEntry,
  ZoneStat,
} from '../../types/dashboard';

// Mock slices mirror the shape of the real Cannabliss analytics payloads so we can swap in API data later.

export const followerHistory: FollowerHistoryPoint[] = [
  { date: '2025-12-01', followers: 72000, weeklyChange: 520, velocity: 0.75 },
  { date: '2025-12-08', followers: 72520, weeklyChange: 520, velocity: 0.78 },
  { date: '2025-12-15', followers: 73040, weeklyChange: 520, velocity: 0.81 },
  { date: '2025-12-22', followers: 73760, weeklyChange: 720, velocity: 0.95 },
  { date: '2025-12-29', followers: 74160, weeklyChange: 400, velocity: 0.60 },
  { date: '2026-01-05', followers: 74840, weeklyChange: 680, velocity: 0.83 },
  { date: '2026-01-12', followers: 75440, weeklyChange: 600, velocity: 0.78 },
  { date: '2026-01-19', followers: 76040, weeklyChange: 600, velocity: 0.78 },
  { date: '2026-01-26', followers: 76780, weeklyChange: 740, velocity: 0.96 },
  { date: '2026-02-02', followers: 77320, weeklyChange: 540, velocity: 0.70 },
  { date: '2026-02-09', followers: 77840, weeklyChange: 520, velocity: 0.67 },
  { date: '2026-02-16', followers: 78480, weeklyChange: 640, velocity: 0.88 },
];

export const weeklyActivity: WeeklyActivityEntry[] = [
  { weekStart: '2026-02-17', additions: 42, removals: 41, promotions: 12, demotions: 6, hallOfFameReturns: 3 },
  { weekStart: '2026-02-10', additions: 38, removals: 40, promotions: 9, demotions: 7, hallOfFameReturns: 2 },
  { weekStart: '2026-02-03', additions: 39, removals: 38, promotions: 11, demotions: 5, hallOfFameReturns: 4 },
  { weekStart: '2026-01-27', additions: 41, removals: 39, promotions: 8, demotions: 8, hallOfFameReturns: 1 },
  { weekStart: '2026-01-20', additions: 36, removals: 36, promotions: 10, demotions: 6, hallOfFameReturns: 2 },
  { weekStart: '2026-01-13', additions: 43, removals: 42, promotions: 14, demotions: 4, hallOfFameReturns: 3 },
  { weekStart: '2026-01-06', additions: 37, removals: 35, promotions: 7, demotions: 5, hallOfFameReturns: 1 },
  { weekStart: '2025-12-30', additions: 40, removals: 38, promotions: 6, demotions: 7, hallOfFameReturns: 2 },
];

export const feederStats: FeederStat[] = [
  { feederName: 'Cannabliss Master', candidates: 48, admits: 24, hitRate: 0.50, avgEntryZone: '1-10', avgSurvivalWeeks: 10.2, topTenPromotions: 9 },
  { feederName: 'Discover Weekly', candidates: 22, admits: 11, hitRate: 0.50, avgEntryZone: '26-40', avgSurvivalWeeks: 5.8, topTenPromotions: 1 },
  { feederName: 'Release Radar', candidates: 18, admits: 10, hitRate: 0.55, avgEntryZone: '11-25', avgSurvivalWeeks: 8.0, topTenPromotions: 3 },
  { feederName: 'Lorem Mirror', candidates: 14, admits: 6, hitRate: 0.43, avgEntryZone: '26-40', avgSurvivalWeeks: 4.3, topTenPromotions: 0 },
  { feederName: 'Anti-Pop Mirror', candidates: 16, admits: 8, hitRate: 0.50, avgEntryZone: '11-25', avgSurvivalWeeks: 7.1, topTenPromotions: 2 },
  { feederName: 'Manual Inbox', candidates: 20, admits: 12, hitRate: 0.60, avgEntryZone: '1-10', avgSurvivalWeeks: 11.4, topTenPromotions: 4 },
  { feederName: 'Last.fm Feed', candidates: 12, admits: 4, hitRate: 0.33, avgEntryZone: '41-50', avgSurvivalWeeks: 3.2, topTenPromotions: 0 },
];

export const zoneStats: ZoneStat[] = [
  { zoneId: 'premium', name: 'Premium Current', range: '1-10', trackCount: 10, avgWeeks: 6.4, promotionRate: 0.28, dropOffRate: 0.12 },
  { zoneId: 'high', name: 'High Conviction', range: '11-25', trackCount: 15, avgWeeks: 8.1, promotionRate: 0.19, dropOffRate: 0.08 },
  { zoneId: 'discovery', name: 'Discovery', range: '26-40', trackCount: 15, avgWeeks: 5.3, promotionRate: 0.26, dropOffRate: 0.15 },
  { zoneId: 'stability', name: 'Stability', range: '41-50', trackCount: 10, avgWeeks: 9.0, promotionRate: 0.11, dropOffRate: 0.18 },
  { zoneId: 'library', name: 'Library', range: '51-160', trackCount: 110, avgWeeks: 12.8, promotionRate: 0.07, dropOffRate: 0.22 },
];

export const breakoutTracks: BreakoutTrack[] = [
  { id: 'bk-001', trackTitle: 'Soothing Static', artist: 'Velvet Fields', currentZone: 'High Conviction', sourceFeeder: 'Release Radar', popularityDelta: 12, weeksOnPlaylist: 5, trendScore: 0.82 },
  { id: 'bk-002', trackTitle: 'Glass Tides', artist: 'Sunset Vault', currentZone: 'Discovery', sourceFeeder: 'Discover Weekly', popularityDelta: 9, weeksOnPlaylist: 3, trendScore: 0.67 },
  { id: 'bk-003', trackTitle: 'Celadon Bloom', artist: 'Anti-Pop Mirror', currentZone: 'Discovery', sourceFeeder: 'Anti-Pop Mirror', popularityDelta: 14, weeksOnPlaylist: 4, trendScore: 0.91 },
  { id: 'bk-004', trackTitle: 'Motorcade', artist: 'Manual Inbox', currentZone: 'High Conviction', sourceFeeder: 'Manual Inbox', popularityDelta: 11, weeksOnPlaylist: 6, trendScore: 0.75 },
  { id: 'bk-005', trackTitle: 'Northern Frame', artist: 'Last.fm Feed', currentZone: 'Discovery', sourceFeeder: 'Last.fm Feed', popularityDelta: 6, weeksOnPlaylist: 2, trendScore: 0.58 },
  { id: 'bk-006', trackTitle: 'Vault Language', artist: 'Lore Echo', currentZone: 'High Conviction', sourceFeeder: 'Cannabliss Master', popularityDelta: 8, weeksOnPlaylist: 7, trendScore: 0.61 },
];

export const movementEvents: MovementEvent[] = [
  { timestamp: '2026-03-15T10:32:00Z', description: 'Promoted into Premium Current after a 38% rise in saves.', type: 'promotion', trackTitle: 'Walled Gardens', artist: 'Jade Static', zoneBefore: 'High Conviction', zoneAfter: 'Premium Current', feederBadge: 'Manual Inbox' },
  { timestamp: '2026-03-14T14:05:00Z', description: 'Returned from Hall of Fame a week earlier than planned.', type: 'return', trackTitle: 'Midnight Walkers', artist: 'Strata Loom', zoneAfter: 'Discovery', feederBadge: 'Hall of Fame' },
  { timestamp: '2026-03-13T09:20:00Z', description: 'Entered via Release Radar with strong first-week engagement.', type: 'entry', trackTitle: 'Silver Drifts', artist: 'Noble Cloud', zoneAfter: 'Discovery', feederBadge: 'Release Radar' },
  { timestamp: '2026-03-12T17:40:00Z', description: 'Dropped from Stability after 12 weeks and aging out.', type: 'removal', trackTitle: 'Plain Signals', artist: 'Boreal Dawn', zoneBefore: 'Stability' },
  { timestamp: '2026-03-11T12:11:00Z', description: 'Demoted to Discovery after momentum cooled.', type: 'demotion', trackTitle: 'Courtlight', artist: 'Echo Marathon', zoneBefore: 'High Conviction', zoneAfter: 'Discovery' },
];

export const topTenTracks: TopTenTrack[] = [
  { rank: 1, trackTitle: 'Lucid Bloom', artist: 'Ether Run', feeder: 'Cannabliss Master', weeksOnPlaylist: 12, changeDelta: -1, changeDirection: 'up' },
  { rank: 2, trackTitle: 'Neon Orchard', artist: 'Condor Signal', feeder: 'Manual Inbox', weeksOnPlaylist: 9, changeDelta: 0, changeDirection: 'steady' },
  { rank: 3, trackTitle: 'City of Light', artist: 'Velvet Fields', feeder: 'Release Radar', weeksOnPlaylist: 8, changeDelta: 1, changeDirection: 'down' },
  { rank: 4, trackTitle: 'Static Bloom', artist: 'Lore Echo', feeder: 'Cannabliss Master', weeksOnPlaylist: 10, changeDelta: -2, changeDirection: 'up' },
  { rank: 5, trackTitle: 'Moonlit Plex', artist: 'Sunset Vault', feeder: 'Manual Inbox', weeksOnPlaylist: 7, changeDelta: 0, changeDirection: 'steady' },
  { rank: 6, trackTitle: 'Ghost Relay', artist: 'Haze Harbor', feeder: 'Release Radar', weeksOnPlaylist: 5, changeDelta: 2, changeDirection: 'down' },
  { rank: 7, trackTitle: 'North Signal', artist: 'Chroma Glide', feeder: 'Cannabliss Master', weeksOnPlaylist: 11, changeDelta: 1, changeDirection: 'down' },
  { rank: 8, trackTitle: 'Field Theory', artist: 'Anti-Pop Mirror', feeder: 'Anti-Pop Mirror', weeksOnPlaylist: 4, changeDelta: -1, changeDirection: 'up' },
  { rank: 9, trackTitle: 'Orbit Lamps', artist: 'Last.fm Feed', feeder: 'Last.fm Feed', weeksOnPlaylist: 3, changeDelta: 0, changeDirection: 'steady' },
  { rank: 10, trackTitle: 'Outer Bloom', artist: 'Manual Inbox', feeder: 'Manual Inbox', weeksOnPlaylist: 6, changeDelta: 1, changeDirection: 'down' },
];

export const dashboardMockData: DashboardDataset = {
  followerHistory,
  weeklyActivity,
  feederStats,
  zoneStats,
  breakoutTracks,
  movementEvents,
  topTenTracks,
};
