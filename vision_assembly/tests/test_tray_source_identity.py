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


def test_observation_fallback_is_unique_shared_and_does_not_claim_tracking():
    from tray_source_identity import assign_observation_sources
    ids=TraySourceIdentity();ids.assign([part(1,0),part(2,20)])
    detections=ids.assign([part(1,10),part(2,80)])
    assert detections[0]['id'] is None
    assign_observation_sources(detections,'reg','obs')
    assert len({p['id'] for p in detections})==2
    assert detections[0]['source_identity_scope']=='observation_cell'
    import hashlib,json
    expected='observation:'+hashlib.sha256(json.dumps(['reg','obs','hbm',1],separators=(',', ':')).encode()).hexdigest()
    assert detections[0]['id']==expected
    assert detections[0]['calibration_instance_index']==1
    other=assign_observation_sources([part(1,10)],'reg','next-obs')
    assert other[0]['id']!=expected


def test_duplicate_observation_indices_cannot_get_execution_identity():
    from tray_source_identity import assign_observation_sources
    detections=assign_observation_sources([part(1,0),part(1,40)],'reg','obs')
    assert all(d['id'] is None for d in detections)


def test_duplicate_observed_cell_is_not_resolved_by_numbering_it_twice():
    from tray_source_identity import assign_observation_sources
    detections=assign_observation_sources([part(1,0),part(2,1)],'reg','obs')
    assert all(d['id'] is None for d in detections)
