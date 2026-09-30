"""Durable nominations captured from additions to the public playlist."""
from collections import Counter
from dataclasses import asdict
from datetime import timedelta
import copy


def build_with_queue(options):
    from src.cannabliss import (CannablissTrack, build_cannabliss_playlist,
                                _parse_datetime, _primary_artist, _song_key)
    options = dict(options)
    options['queue_curator_additions'] = False  # Run the existing selection once.
    limit = options.pop('curator_queue_per_refresh')
    if limit < 1:
        raise ValueError('Curator queue admission limit must be positive')
    now = options['now']
    state = copy.deepcopy(options['rotation_state'] or {})
    # Without a verified baseline we cannot tell nominations from incumbents.
    if options['rotation_state'] is None and not options['previous_track_uris']:
        return build_cannabliss_playlist(**options)
    previous = set(options['previous_track_uris'])
    live = sorted(options['current_tracks'], key=lambda t: t.current_position or 10**9)
    additions = [t for t in live if t.uri not in previous]
    queue = state.setdefault('curator_queue', [])
    keys = {entry['song_key'] for entry in queue}
    captured = []
    for track in additions:
        key = _song_key(track)
        if key in keys:
            continue
        added = min(_parse_datetime(track.added_at) or now, now)
        next_monday = (added + timedelta(days=7-added.weekday())).date().isoformat()
        data = asdict(track)
        data['source_tags'] = sorted(track.source_tags)
        queue.append(dict(track=data, song_key=key, nominated_at=added.isoformat(),
                          observed_at=now.isoformat(), eligible_week=next_monday))
        keys.add(key)
        captured.append(track)
    queue.sort(key=lambda e: (e['nominated_at'], e['observed_at'], e['track']['uri']))

    # Extra nominations are parked, not treated as current protected picks.
    incumbents = [t for t in live if t.uri in previous]
    counts = Counter(_primary_artist(t.artists) for t in incumbents)
    monday = (now - timedelta(days=now.weekday())).date().isoformat()
    week = now.strftime('%G-W%V')
    budget = state.get('weekly_budget', {})
    used = budget.get('used', 0) if budget.get('week') == week else 0
    remaining = max(0, options['weekly_insertions'] - used)
    history = state.get('tracks', {})
    protected = sum((_parse_datetime(history.get(t.uri, {}).get('protected_until', '')) or now) > now
                    for t in incumbents)
    slots = min(limit, remaining, max(0, options['target_size']-protected))
    major = options['update_mode'] == 'major' and state.get('last_major_week') != week
    promoted = []
    selected_keys = set()
    if major:
        for entry in queue:
            if len(promoted) >= slots:
                break
            if entry['eligible_week'] > monday:
                continue
            data = dict(entry['track'])
            data['source_tags'] = set(data['source_tags']) | {'curator_queue'}
            track = CannablissTrack(**data)
            artist = _primary_artist(track.artists)
            if counts[artist] >= options['max_tracks_per_artist']:
                continue
            promoted.append(track)
            selected_keys.add(entry['song_key'])
            counts[artist] += 1
    # Block every queued recording (including alternate releases) from being
    # admitted through Master or a feeder before its own queue turn.
    for source in ('master_tracks', 'feeder_tracks', 'hall_tracks'):
        options[source] = [t for t in options[source] if _song_key(t) not in keys]
    options['current_tracks'] = incumbents + promoted
    options['rotation_state'] = state
    options['discovery_per_refresh'] = max(0, options['discovery_per_refresh']-len(promoted))
    result = build_cannabliss_playlist(**options)
    if not {t.uri for t in promoted}.issubset({t.uri for t in result.ordered_tracks}):
        raise RuntimeError('Queued nominations were not retained; refusing to discard queue entries')
    result.rotation_state['curator_queue'] = [e for e in queue if e['song_key'] not in selected_keys]
    result.summary['queued_for_future'] = [f"{e['track']['name']} — eligible {e['eligible_week']}"
                                           for e in result.rotation_state['curator_queue']]
    result.summary['queue_promoted'] = [t.name for t in promoted]
    result.summary['queue_captured'] = [t.name for t in captured]
    for track in promoted:
        result.reasons[track.uri] = 'Your queued nomination: admitted this week, protected for 14 days'
    return result
