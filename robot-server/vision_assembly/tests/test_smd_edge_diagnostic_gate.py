"""Pure numeric gate tests without loading ROS/GPU runtime dependencies."""
import ast
from pathlib import Path
import numpy as np

source = Path(__file__).resolve().parents[1]/'scripts/capture_smd_edge_diagnostic.py'
tree = ast.parse(source.read_text())
scope = {'np': np, 'unwrap': lambda a: np.rad2deg(np.unwrap(np.deg2rad(a), period=np.pi))}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'summarize'], type_ignores=[]), str(source), 'exec'), scope)
summarize = scope['summarize']
gate = {'max_center_span_canonical_px': 3.5, 'temporal_median_gate': {'median_absolute_deviation_max_deg': 1.5, 'max_batch_span_deg': 3.0}}


def rows():
    return [dict(center=[10.,20.], angle=89., pose=[0.,0.,0.,180.,0.,0.], base=[1.,2.,3.], base_angle=1.) for _ in range(30)]


def test_stable():
    assert summarize(rows(), gate)['stability_passed']


def test_incomplete():
    assert not summarize(rows()[:29], gate)['stability_passed']


def test_center_rejected():
    r=rows(); r[-1]['center'][0]+=3.501
    assert not summarize(r, gate)['stability_passed']


def test_batch_angle_rejected():
    r=rows()
    for item in r[-10:]: item['angle']+=3.01
    assert not summarize(r, gate)['stability_passed']


def test_robot_motion_rejected():
    r=rows(); r[-1]['pose'][0]=.501
    assert not summarize(r, gate)['stability_passed']


def test_robot_rotation_wrap():
    r=rows(); r[-1]['pose'][3]=-180.
    assert summarize(r, gate)['stability_passed']


def test_nonfinite_rejected():
    r=rows(); r[-1]['center'][0]=float('nan')
    assert not summarize(r, gate)['stability_passed']
