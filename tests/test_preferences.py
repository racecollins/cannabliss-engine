from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from src.preferences import observe_order, preference_scores, feature_top_ten
from src.cannabliss import ListeningSignals
from tests.test_curator_rotation import NOW, build, current_list, spotify_rewrite, track


def test_inserts_and_removals_are_not_reorder_preferences():
    state = {"verified_order": ["a", "b", "c", "d"]}
    assert observe_order(state, ["new", "a", "c", "d"], NOW) == []
    assert "order_preferences" not in state


def test_reorder_learns_relative_preferences_not_false_drag_claims():
    state = {"verified_order": [str(i) for i in range(30)]}
    edited = ["9"] + [str(i) for i in range(30) if i != 9]
    events = observe_order(state, edited, NOW)
    assert len(events) == 9
    assert all(e["preferred"] == "9" for e in events)
    assert preference_scores(state, NOW)["9"] == 1
    # Relative preference for a song can fade without erasing the audit evidence.
    assert preference_scores(state, NOW + timedelta(days=126))["9"] < 0.3


def test_body_only_edit_does_not_train_top_ten():
    state = {"verified_order": [str(i) for i in range(30)]}
    edited = state["verified_order"][:]
    edited[20], edited[21] = edited[21], edited[20]
    assert observe_order(state, edited, NOW) == []


def test_preview_is_pure_and_verified_engine_order_is_not_learned():
    first = build(current_list(), learn_top_ten=True)
    original = deepcopy(first.rotation_state)
    live = spotify_rewrite(first, NOW)
    next_run = build(live, state=original, learn_top_ten=True)
    assert original == first.rotation_state
    assert not next_run.rotation_state.get("order_preferences")
    moved = [live[9]] + live[:9] + live[10:]
    moved = [replace(t, current_position=i+1) for i,t in enumerate(moved)]
    edited = build(moved, state=original, learn_top_ten=True)
    assert original == first.rotation_state
    assert edited.rotation_state["order_preferences"]
    assert [t.uri for t in edited.ordered_tracks] == [t.uri for t in moved]
    reread = build(spotify_rewrite(edited, NOW), state=edited.rotation_state, learn_top_ten=True)
    assert reread.rotation_state["order_preferences"] == edited.rotation_state["order_preferences"]


def test_favorite_rests_after_two_weeks_even_with_preference_boost():
    tracks = current_list()
    signals = ListeningSignals(top_track_ranks={"0": 1})
    state = {"order_preferences": [{"preferred": tracks[0].uri, "over": tracks[1].uri, "at": NOW.isoformat()}]}
    orders=[]
    for n in range(4):
        orders.append(feature_top_ten(tracks, [t.uri for t in tracks], state, signals,
                                      NOW+timedelta(days=n*7), rotate=True))
    assert orders[0][0].uri == tracks[0].uri
    assert orders[1][0].uri == tracks[0].uri
    assert tracks[0].uri not in {t.uri for t in orders[2][:10]}
    assert orders[3][0].uri == tracks[0].uri
    assert all(len(o)==100 and len({t.uri for t in o})==100 for o in orders)


def test_listening_ranks_win_over_small_freshness_bonus():
    old = track('old')
    new = replace(track('new'), release_date=NOW.date().isoformat())
    result = feature_top_ten([new,old], [], {}, ListeningSignals(top_track_ranks={'old':1}), NOW, rotate=True)
    assert result[0].uri == old.uri


def test_missing_verified_baseline_does_not_infer_edits():
    state={}
    assert observe_order(state, ['a','b'], NOW)==[]
    assert state=={}


def test_duplicate_lead_artists_are_not_featured_together():
    tracks=[track(i,artist='Same' if i<4 else f'Artist {i}') for i in range(25)]
    result=feature_top_ten(tracks,[],{},ListeningSignals(top_track_ids=frozenset(map(str,range(4)))),NOW,rotate=True)
    assert len({t.artists for t in result[:10]})==10


def test_fifteen_arrivals_and_one_hundred_total_with_learning_enabled():
    current=current_list()
    pool=[track(f'new{i}') for i in range(40)]
    result=build(current,pool,learn_top_ten=True,discovery_per_refresh=15)
    assert result.new_track_count==15
    assert len(result.ordered_tracks)==100
    assert len(result.removed_uris)==15


def test_relative_preference_changes_next_weeks_ranking():
    tracks=current_list()
    state={'verified_order':[t.uri for t in tracks]}
    edited=[tracks[9].uri]+[t.uri for t in tracks if t.uri!=tracks[9].uri]
    observe_order(state,edited,NOW)
    ranked=feature_top_ten(tracks,edited,state,ListeningSignals(),NOW,rotate=True)
    assert ranked[0].uri==tracks[9].uri
