"""Apply an explicitly reviewed edition; never manufacture a verified baseline.

Default is preview-only. Applying requires --apply and a durable checkpoint.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.cannabliss import (CannablissTrack, CannablissBuildResult, _song_key,
    _parse_datetime, parse_source_items, save_cannabliss_state, append_cannabliss_run)
from src.curator_queue import build_with_queue


def prepare_edition(proposal, raw, now):
    if proposal.get('status') != 'editorial_proposal_not_applied':
        raise ValueError('Expected a reviewed editorial proposal')
    before = [r['uri'] for r in proposal['before']]
    live = parse_source_items(raw, source_tag='current', current_order=True)
    live_uris = [t.uri for t in live]
    if len(live) != len(raw) or len(set(live_uris)) != len(live_uris):
        raise ValueError('Unsupported or duplicate current items; reconcile before migration')
    if [u for u in live_uris if u in set(before)] != before:
        raise ValueError('Existing songs were removed or reordered since approval; reconcile first')
    rows = proposal['tracks']
    if len(rows) != 100 or len({r['uri'] for r in rows}) != 100:
        raise ValueError('Approved edition must contain 100 unique songs')
    stamp = now.isoformat()
    tracks = [CannablissTrack(r['uri'], r['name'], ', '.join(r['artists']), stamp,
                             {'approved_edition'}, i+1) for i,r in enumerate(rows)]
    if len({_song_key(t) for t in tracks}) != 100:
        raise ValueError('Edition has duplicate song variants')
    history = {t.uri: dict(name=t.name, artists=t.artists, song_key=_song_key(t),
                          entered_at=stamp) for t in live + tracks}
    selected = {t.uri for t in tracks}
    monday = (now-timedelta(days=now.weekday())).date().isoformat()
    # This reviewed migration is an initial baseline, separate from normal
    # weekly intake. The next Friday can perform the first regular refresh.
    rotation = dict(version=2, tracks=history, verified_order=[t.uri for t in tracks],
                    curator_queue=[], dismissed_uris=[], dismissed_song_keys=[],
                    weekly_budget={'week':now.strftime('%G-W%V'),'used':0},
                    featured_weeks={t.uri:{'week':monday,'streak':1} for t in tracks[:10]})
    for i,(t,r) in enumerate(zip(tracks,rows)):
        added = _parse_datetime(r.get('added_at') or '')
        if i < 10 or t.uri not in before or (added and now-added < timedelta(days=14)):
            history[t.uri]['protected_until']=(now+timedelta(days=14)).isoformat()
        if i < 10:
            history[t.uri]['last_featured_at']=stamp
    # Preserve additions made after the preview as next-week nominations.
    for t in live:
        if t.uri in before or t.uri in selected:
            continue
        added=min(_parse_datetime(t.added_at) or now,now)
        rotation['curator_queue'].append(dict(song_key=_song_key(t),nominated_at=added.isoformat(),
            observed_at=stamp,eligible_week=(added+timedelta(days=7-added.weekday())).date().isoformat(),
            track=dict(uri=t.uri,name=t.name,artists=t.artists,added_at=t.added_at,
                       source_tags=['current'],current_position=t.current_position,
                       popularity=None,release_date=t.release_date)))
    retired = [u for u in before if u not in selected]
    for uri in retired:
        history[uri]['retired_at']=stamp
    return CannablissBuildResult(tracks, {'fresh_front':tracks[:10],'body':tracks[10:]},
        {'activation':['Explicitly reviewed initial 100-song edition'],
         'queued_for_future':[e['track']['name'] for e in rotation['curator_queue']]},
        len(selected-set(before)), 'major', retired, rotation,
        [u for u,h in history.items() if 'protected_until' in h],
        {t.uri:'Reviewed first-edition selection' for t in tracks}, False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proposal')
    parser.add_argument('--state',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from src.config import load_config
    from src.spotify_client import SpotifyClient
    from src.state_store import checkpoint, remote_head
    from src.preview import write_preview
    cfg=load_config()
    proposal=json.loads(Path(args.proposal).read_text())
    if proposal['target_playlist_id'] != cfg.cannabliss_target_playlist_id:
        raise ValueError('Proposal targets a different playlist')
    if Path(args.state).exists() or Path(args.state+'.pending.json').exists():
        raise ValueError('Activation state already exists; do not repeat migration')
    client=SpotifyClient(cfg.spotify_client_id,cfg.spotify_client_secret,cfg.spotify_refresh_token)
    client.authenticate()
    raw=client.get_all_playlist_items(cfg.cannabliss_target_playlist_id)
    now=datetime.now(timezone.utc)
    result=prepare_edition(proposal,raw,now)
    write_preview(result,parse_source_items(raw,source_tag='current',current_order=True),
                  str(Path(args.state).parent/'activation-preview.md'))
    print(f'Prepared {len(result.ordered_tracks)} songs and {len(result.rotation_state["curator_queue"])} queued nominations.')
    if not args.apply:
        print('Preview only: no Spotify or verified-history changes.'); return
    if remote_head() is not None:
        raise RuntimeError('Durable history already exists; do not overwrite it with a new baseline')
    if client.get_all_playlist_items(cfg.cannabliss_target_playlist_id) != raw:
        raise RuntimeError('Playlist changed during activation; rebuild the preview')
    before=[t.uri for t in parse_source_items(raw,source_tag='current')]
    after=[t.uri for t in result.ordered_tracks]
    pending=dict(timestamp=now.isoformat(),target_playlist_id=cfg.cannabliss_target_playlist_id,
                 before=before,after=after,proposed_rotation=result.rotation_state)
    # The initial state has no successful runs. Only a matched readback below
    # establishes a schema-2 baseline that the scheduler can restore.
    save_cannabliss_state({'runs':[]},args.state)
    save_cannabliss_state(pending,args.state+'.pending.json')
    checkpoint(args.state,pending=pending)
    client.replace_playlist_tracks(cfg.cannabliss_target_playlist_id,after)
    actual=parse_source_items(client.get_all_playlist_items(cfg.cannabliss_target_playlist_id),source_tag='current')
    if [t.uri for t in actual] != after:
        raise RuntimeError('Readback mismatch; pending checkpoint retained for recovery')
    append_cannabliss_run(result,path=args.state,now=now,cooldown_days=42,
                         target_playlist_id=cfg.cannabliss_target_playlist_id)
    checkpoint(args.state)
    Path(args.state+'.pending.json').unlink()
    print('Activated and verified the approved edition; durable history saved.')


if __name__=='__main__':
    main()
