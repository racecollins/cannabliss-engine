from copy import deepcopy
from datetime import datetime, timezone
import pytest
from src.activate_edition import prepare_edition

NOW=datetime(2026,9,30,tzinfo=timezone.utc)


def fixture():
    rows=[dict(uri=f'spotify:track:{i}',name=f'Song {i}',artists=[f'Artist {i}'],
               added_at='2026-01-01T00:00:00Z') for i in range(105)]
    proposal=dict(status='editorial_proposal_not_applied',before=rows,tracks=rows[:100])
    raw=[dict(added_at=r['added_at'],track=dict(uri=r['uri'],name=r['name'],
         artists=[{'name':a} for a in r['artists']],type='track')) for r in rows]
    return proposal,raw


def test_reviewed_migration_preserves_post_preview_nomination_without_advancing_history():
    p,raw=fixture(); original=deepcopy(p)
    raw.append(dict(added_at=NOW.isoformat(),track=dict(uri='spotify:track:new',
        name='New nomination',artists=[{'name':'New artist'}],type='track')))
    result=prepare_edition(p,raw,NOW)
    assert len(result.ordered_tracks)==100
    assert len(result.removed_uris)==5
    assert result.rotation_state['curator_queue'][0]['eligible_week']=='2026-10-05'
    assert result.rotation_state['curator_queue'][0]['track']['uri']=='spotify:track:new'
    assert 'spotify:track:new' not in result.removed_uris
    assert p==original


@pytest.mark.parametrize('change',['remove','reorder','duplicate'])
def test_migration_refuses_stale_or_ambiguous_approval(change):
    p,raw=fixture()
    if change=='remove':raw.pop(0)
    elif change=='reorder':raw[0],raw[1]=raw[1],raw[0]
    else:raw.append(raw[0])
    with pytest.raises(ValueError):prepare_edition(p,raw,NOW)


def test_invalid_edition_size_is_rejected():
    p,raw=fixture();p['tracks']=p['tracks'][:99]
    with pytest.raises(ValueError,match='100'):prepare_edition(p,raw,NOW)
