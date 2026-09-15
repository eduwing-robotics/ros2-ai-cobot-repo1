import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from assembly_test_profiles import GROUPS,workflow,build
from assembly_api_client import make_request


@pytest.mark.parametrize('profile',GROUPS)
def test_group_workflow_keeps_preflight_fresh_capture_and_grasp_checks(tmp_path,profile):
    steps=dict(workflow(tmp_path,profile));names=list(steps)
    phase='smd' if profile=='SMD' else 'non-smd'
    assert names.index('capture_board')<names.index('capture_tray')<names.index('plan_'+phase)<names.index('preflight_'+phase)<names.index('assemble_'+phase)
    assert '--part-group' in steps['capture_tray']
    assert '--execute' not in steps['preflight_'+phase]
    assert '--dry-run' in steps['preflight_'+phase]
    if profile!='SMD':assert '--verify-tray-pick' in steps['assemble_'+phase]
    else:assert names.index('measure_smd')<names.index('plan_smd')
    assert ('refine_vrm' in steps)==(profile=='VRM')
    assert names[-1]=='after_photo'


def test_client_cannot_fall_back_to_direct_execution_or_unknown_profile():
    status={'profiles':['full','HBM'],'recipe_revision':'reviewed'}
    request=make_request(status,execute=True,profile='HBM')
    assert request['action']=='assembly.start' and request['profile']=='HBM' and request['confirm_scene_ready'] is True
    assert make_request(status)['action']=='assembly.check'
    with pytest.raises(RuntimeError):make_request({},execute=True)
    with pytest.raises(ValueError):make_request(status,profile='HBM')
