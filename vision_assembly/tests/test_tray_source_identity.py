from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tray_source_identity import TraySourceIdentity


def part(index,x):return dict(part_type='hbm',instance_index=index,reference_center_pixel=[x,10.])


def test_removing_first_cell_does_not_rename_remaining_sources():
    ids=TraySourceIdentity();first=ids.assign([part(1,0),part(2,40),part(3,80)])
    remaining=ids.assign([part(1,40),part(2,80)])
    assert [p['id'] for p in remaining]==[p['id'] for p in first[1:]]
    assert [p['instance_index'] for p in remaining]==[1,2]  # motion indexing unchanged


def test_reappearance_keeps_identity_and_other_session_does_not_reuse_it():
    ids=TraySourceIdentity();source=ids.assign([part(1,0)])[0]['id']
    ids.assign([])
    assert ids.assign([part(1,1)])[0]['id']==source
    assert TraySourceIdentity().assign([part(1,0)])[0]['id']!=source


def test_ambiguous_matches_are_not_guessed():
    ids=TraySourceIdentity();ids.assign([part(1,0),part(2,20)])
    assert ids.assign([part(1,10)])[0]['id'] is None
    duplicate=ids.assign([part(1,0),part(2,1)])
    assert all(p['id'] is None for p in duplicate)


def test_fixed_anchor_prevents_gradual_walk_into_another_cell():
    ids=TraySourceIdentity();original=ids.assign([part(1,0)])[0]['id']
    assert ids.assign([part(1,10)])[0]['id']==original
    assert ids.assign([part(1,20)])[0]['id']!=original
