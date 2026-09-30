import copy
import json
from dataclasses import replace
from datetime import timedelta

from src.cannabliss import build_cannabliss_playlist
from tests.test_curator_rotation import NOW, current_list, track, spotify_rewrite


def run(live, prior, state, *, now=NOW, master=(), mode='major', allowance=20):
    return build_cannabliss_playlist(
        current_tracks=live, master_tracks=list(master), feeder_tracks=[], hall_tracks=[],
        previous_track_uris={t.uri for t in prior}, rotation_state=state,
        target_size=100, weekly_insertions=allowance, discovery_per_refresh=15,
        queue_curator_additions=True, learn_top_ten=True, update_mode=mode, now=now)


def picks(n=30, added=NOW):
    return [track(f'pick{i:02}', pos=101+i, date=added.isoformat()) for i in range(n)]


def test_thirty_nominations_are_saved_and_spread_over_three_weeks():
    live=current_list(); nominations=picks()
    state={'tracks':{},'verified_order':[t.uri for t in live]}
    original=copy.deepcopy(state)
    result=run(live+nominations,live,state)
    assert state==original
    assert len(result.ordered_tracks)==100
    assert len(result.rotation_state['curator_queue'])==30
    assert result.rotation_state['weekly_budget']['used']==0
    admitted=set()
    for n in range(1,4):
        # JSON roundtrip emulates restarting with durable history. Nominations
        # are no longer on Spotify, and never existed in Master.
        state=json.loads(json.dumps(result.rotation_state))
        live=spotify_rewrite(result,NOW+timedelta(days=n*7))
        result=run(live,result.ordered_tracks,state,now=NOW+timedelta(days=n*7))
        selected={t.uri for t in result.ordered_tracks} & {t.uri for t in nominations}
        assert len(selected-admitted)==10
        admitted|=selected
        assert len(result.rotation_state['curator_queue'])==30-10*n
        assert len(result.ordered_tracks)==100
        assert result.rotation_state['weekly_budget']['used']==10
    assert admitted=={t.uri for t in nominations}


def test_queue_cannot_sneak_in_via_master_or_an_alternate_release():
    live=current_list(); pick=picks(1)[0]
    variant=replace(pick,uri='spotify:track:alternate',current_position=None)
    result=run(live+[pick],live,{'tracks':{}},master=[pick,variant])
    assert pick.uri not in {t.uri for t in result.ordered_tracks}
    assert variant.uri not in {t.uri for t in result.ordered_tracks}
    assert len(result.rotation_state['curator_queue'])==1


def test_repeat_and_micro_do_not_drain_or_duplicate_queue():
    live=current_list(); nom=picks()
    first=run(live+nom,live,{'tracks':{}})
    again=run(live+nom,live,{'tracks':{}})
    assert first.rotation_state==again.rotation_state
    second=run(spotify_rewrite(first,NOW),first.ordered_tracks,first.rotation_state)
    assert len(second.rotation_state['curator_queue'])==30
    micro=run(spotify_rewrite(second,NOW),second.ordered_tracks,second.rotation_state,
              now=NOW+timedelta(days=7),mode='micro')
    assert len(micro.rotation_state['curator_queue'])==30
    major=run(spotify_rewrite(micro,NOW),micro.ordered_tracks,micro.rotation_state,
              now=NOW+timedelta(days=7))
    assert len(major.rotation_state['curator_queue'])==20
    repeat=run(spotify_rewrite(major,NOW),major.ordered_tracks,major.rotation_state,
               now=NOW+timedelta(days=7,hours=1))
    assert len(repeat.rotation_state['curator_queue'])==20


def test_last_week_addition_is_eligible_when_first_observed_this_week():
    live=current_list(); nom=picks(1,added=NOW-timedelta(days=7))
    result=run(live+nom,live,{'tracks':{}})
    assert not result.rotation_state['curator_queue']
    assert nom[0].uri in result.protected_uris
    assert result.rotation_state['tracks'][nom[0].uri]['protected_until']==(NOW+timedelta(days=14)).isoformat()


def test_backlog_leaves_room_for_five_other_discoveries():
    live=current_list(); nom=picks(30,added=NOW-timedelta(days=7))
    result=run(live+nom,live,{'tracks':{}},master=[track(f'new{i}') for i in range(30)])
    assert len(result.summary['queue_promoted'])==10
    assert result.new_track_count==5
    assert result.rotation_state['weekly_budget']['used']==15
    assert len(result.ordered_tracks)==100


def test_shared_weekly_budget_and_artist_limit_hold():
    live=current_list(); nom=picks(30,added=NOW-timedelta(days=7))
    state={'tracks':{},'weekly_budget':{'week':NOW.strftime('%G-W%V'),'used':18}}
    result=run(live+nom,live,state,master=[track('discovery')])
    assert len(result.summary['queue_promoted'])==2
    assert result.rotation_state['weekly_budget']['used']==20
    assert result.new_track_count==0
    duplicates=[replace(t,artists='One artist') for t in nom]
    result=run(live+duplicates,live,{'tracks':{}})
    assert len(result.summary['queue_promoted'])==2
    assert len(result.rotation_state['curator_queue'])==28


def test_unknown_baseline_does_not_misclassify_entire_playlist_as_queue():
    live=current_list()
    result=run(live,[],None)
    assert result.bootstrap
    assert not result.rotation_state.get('curator_queue')
    assert len(result.ordered_tracks)==100


def test_protected_full_edition_preserves_queue_until_space_exists():
    live=current_list(); nom=picks(1,added=NOW-timedelta(days=7))
    state={'tracks':{t.uri:{'protected_until':(NOW+timedelta(days=3)).isoformat()} for t in live}}
    result=run(live+nom,live,state)
    assert len(result.rotation_state['curator_queue'])==1
    assert len(result.ordered_tracks)==100
