import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import place_held_vrm04 as recovery


def test_shortest_positive_rotation_and_vertical_final():
    route = recovery.route_from_home([-528, -61, 338, 180, 0, 90], [-16, -498, 87, -180, 0, -179.25])
    assert 119 < route[1][1].tcp[5] < 121
    assert 149 < route[2][1].tcp[5] < 151
    for _, point in route[4:]:
        assert point.linear
        assert point.tcp[:2] == (-16, -498)
        assert point.tcp[3:] == (-180, 0, -179.25)


@pytest.mark.parametrize('release_fails', [False, True])
def test_release_before_retreat(monkeypatch, release_fails):
    calls = []
    monkeypatch.setattr(recovery, 'move_preflighted', lambda node, w: calls.append(w.label))
    def release(*args):
        calls.append('release')
        if release_fails:
            raise RuntimeError('release failed')
    labels = ['place_final_50mm_vertical', 'post_release_lift_50mm_vertical', 'post_release_lift_100mm_vertical']
    checked = [SimpleNamespace(label=label) for label in labels]
    args = (SimpleNamespace(gripper=release), checked, {'release_position': 26}, {}, lambda r: None)
    if release_fails:
        with pytest.raises(RuntimeError, match='release failed'):
            recovery.run_checked(*args)
        assert calls == [labels[0], 'release']
    else:
        recovery.run_checked(*args)
        assert calls == [labels[0], 'release', *labels[1:]]
