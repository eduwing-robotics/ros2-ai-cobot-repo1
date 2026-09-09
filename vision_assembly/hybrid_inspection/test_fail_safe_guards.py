"""Synthetic, CPU-only regressions; no checkpoints, captures or subprocesses."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import main
import patchcore_inspector as patchcore
import preprocessor_and_cropper as providers
from opencv_inspectors import check_auxiliary_pose, estimate_common_projection_bias


def passing_stages():
    return {name: dict(status='PASS', authority='AUTHORITATIVE', confidence=0.99)
            for name in main.REQUIRED_SLOT_STAGES}


@pytest.mark.parametrize('missing', [None, *sorted(main.REQUIRED_SLOT_STAGES)])
def test_missing_required_stages_never_pass(missing):
    stages = passing_stages() if missing else {}
    if missing:
        del stages[missing]
    assert main.fuse_required_stages(stages)[0] == 'UNKNOWN'
    assert main.fuse_required_stages(passing_stages(), frozenset({'pins'}))[0] == 'UNKNOWN'


@pytest.mark.parametrize('bad', [None, {}, {'status': 'OK', 'authority': 'AUTHORITATIVE'},
                                {'status': 'PASS', 'authority': 'AUTHORITATIVE', 'confidence': float('nan')},
                                {'status': 'PASS', 'authority': 'AUTHORITATIVE', 'score': float('inf')}])
def test_invalid_stage_cannot_become_pass_or_hide_independent_fail(bad):
    stages = passing_stages()
    stages['pose'] = bad
    assert main.fuse_required_stages(stages)[0] == 'UNKNOWN'
    stages['presence']['status'] = 'FAIL'
    assert main.fuse_required_stages(stages)[0] == 'FAIL'


def test_board_requires_unique_complete_slot_ids():
    quality = dict(blocks_decision=False, flags=[], policy={'validated': True})
    rows = [dict(slot_id=f'slot_{i}', status='PASS') for i in range(25)]
    assert main.fuse_board_result(rows, True, 'OK', quality)[0] == 'PASS'
    assert main.fuse_board_result(rows, True, 'OK', quality, expected_slot_ids={'other'})[0] == 'UNKNOWN'
    rows[-1] = dict(rows[0])
    assert main.fuse_board_result(rows, True, 'OK', quality)[0] == 'UNKNOWN'


def pose_item():
    return dict(confidence=0.9, evidence=dict(present=True, center_px=[55, 50],
                expected_center_px=[50, 50], long_axis_angle_deg_undirected=0.0))


@pytest.mark.parametrize('field,value', [('center_px', [float('nan'), 50]),
    ('center_px', [50]), ('expected_center_px', [[50, 50]]),
    ('long_axis_angle_deg_undirected', float('inf')), ('mask_area_px', float('nan'))])
def test_nonfinite_or_misshaped_pose_is_unknown(field, value):
    item = pose_item()
    item['evidence'][field] = value
    result = check_auxiliary_pose(item, 0, (100, 100, 3), (100, 100))
    assert result.status == 'UNKNOWN' and result.authority == 'INVALID'


def test_missing_axis_cannot_default_to_correct_orientation():
    item = pose_item()
    item['evidence'].pop('long_axis_angle_deg_undirected')
    assert check_auxiliary_pose(item, 0, (100, 100, 3), (100, 100)).status == 'UNKNOWN'
    assert check_auxiliary_pose(item, 0, (100, 100, 3), (100, 100), check_axis_angle=False).status == 'FAIL'


def test_bad_centroid_cannot_poison_shared_bias():
    items = {f'slot_{i}': pose_item() for i in range(6)}
    items['bad'] = pose_item()
    items['bad']['evidence']['center_px'] = [float('nan'), 50]
    items['malformed'] = None
    bias, evidence = estimate_common_projection_bias(items, (1000, 1000, 3), (100, 100))
    assert bias == (0.5, 0.0)
    assert evidence['candidate_count'] == 6


def slot(slot_id='hbm_01', component='HBM', key='hbm', center=(50, 50)):
    return providers.FixedSlot(slot_id, component, key, (*center, 30, 20), 0.0,
                               np.zeros((20, 30, 3), np.uint8), (35, 40), (30, 20))


def test_clipped_heatmap_keeps_slot_relative_pixels():
    item = slot(center=(5, 50))
    full_item = slot(center=(55, 50))
    evidence = patchcore.PatchCoreEvidence(item.slot_id, 'hbm', 'UNKNOWN', 'ADVISORY_ONLY',
        0.5, 'TEST', None, None, 0.2, 0.2,
        np.tile(np.linspace(0.2, 0.35, 44, dtype=np.float32), (29, 1)))
    image = np.zeros((100, 100, 3), np.uint8)
    clipped = main._absolute_patchcore_evidence_map(image, [item], {item.slot_id: evidence})
    full = main._absolute_patchcore_evidence_map(image, [full_item], {item.slot_id: evidence})
    np.testing.assert_array_equal(clipped[40:60, :20], full[40:60, 50:70])


@pytest.mark.parametrize('bad_map', [np.zeros((10, 9)), np.full((10, 10), np.nan), np.zeros((10, 10, 1))])
def test_corrupt_heatmap_is_not_rendered_as_clean(bad_map):
    with pytest.raises(ValueError):
        main._heatmap_images(np.zeros((10, 10, 3), np.uint8), bad_map)


@pytest.mark.parametrize('settings', [dict(pass_max=float('inf'), fail_min=float('inf')),
    dict(pass_max=0.2, fail_min=float('nan')), dict(pass_max=0.2), ['wrong']])
def test_invalid_patchcore_threshold_cannot_authorize_pass(tmp_path, settings):
    provider = patchcore.ComponentPatchCoreInspector(tmp_path)
    provider.thresholds = {'components': {'hbm': settings}}
    result = provider._decision('hbm', 0.1)
    assert result[:2] == ('UNKNOWN', 'INVALID')


def test_patchcore_component_calibration_error_is_isolated(tmp_path, monkeypatch):
    provider = patchcore.ComponentPatchCoreInspector(tmp_path)
    provider.normal = {'components': {'hbm': {'pixel': {'percentiles': {'99.9': float('nan')}}}}}
    monkeypatch.setattr(patchcore, '_checkpoint', lambda *args: 'unused')
    calls = []
    def predict(component, *args):
        calls.append(component)
        return {'ai_gpu': {'score': 0.1, 'anomaly_map': np.zeros((8, 8), np.float32)}}
    monkeypatch.setattr(patchcore, '_predict_outputs', predict)
    result = provider.inspect(np.zeros((100, 100, 3), np.uint8),
                              [slot(), slot('ai_gpu', 'GPU', 'gpu')], tmp_path)
    assert result['hbm_01'].authority == 'UNAVAILABLE'
    assert result['hbm_01'].normal_pixel_p999 is None
    assert result['ai_gpu'].authority == 'ADVISORY_ONLY'
    assert calls == ['gpu']


@pytest.mark.parametrize('kind', ['presence', 'state', 'seating'])
def test_classifier_load_errors_are_isolated(tmp_path, monkeypatch, kind):
    cls = {'presence': providers.SlotPresenceClassifier, 'state': providers.VrmStateClassifier,
           'seating': providers.VrmSeatingClassifier}[kind]
    provider = cls(tmp_path, device='cpu')
    def broken(*args):
        if kind != 'presence':
            provider.metadata = ['invalid metadata shape']
        raise ValueError('corrupt metadata')
    monkeypatch.setattr(provider, '_load', broken)
    kwargs = {'non_empty_confidence': 1.0} if kind == 'seating' else {}
    result = provider.inspect(slot('vrm_01', 'VRM', 'vrm'), np.zeros((100, 100, 3), np.uint8), **kwargs)
    assert result.predicted_state == 'UNKNOWN'
    assert result.authority == 'UNAVAILABLE' and 'PROVIDER_ERROR:ValueError' in result.reason
    if kind != 'presence':
        assert provider.metadata == {}


@pytest.mark.parametrize('shape', [(1, 1), (1, 3), (2, 2), (2,), (1, 2, 1)])
def test_logits_require_exact_single_sample_class_axis(shape):
    import torch
    with pytest.raises(ValueError):
        providers._classifier_probabilities(torch.zeros(shape), 2)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_logits_and_nonempty_confidence_rejected(value):
    import torch
    with pytest.raises(ValueError):
        providers._classifier_probabilities(torch.tensor([[0.0, value]]), 2)
    with pytest.raises(ValueError):
        providers._probability(value)


@pytest.mark.parametrize('payload', ['{broken', '[]', '{"detections": null}',
    '{"detections": [null]}', '{"detections": [{"slot_id":"hbm_01"}, {"slot_id":"hbm_01"}]}'])
def test_yolo_bad_report_is_unavailable_without_subprocess(tmp_path, monkeypatch, payload):
    provider = providers.YoloSegAuxiliary()
    provider.python = provider.weights = Path(__file__)
    monkeypatch.setattr(providers.subprocess, 'run', lambda *args, **kwargs: None)
    (tmp_path / 's22_parts_seg_latest.json').write_text(payload)
    assert provider.inspect(tmp_path / 'unused.png', tmp_path) == {}
    assert provider.last_status == 'UNAVAILABLE'


def test_presence_validation_and_rgb_input_are_preserved(tmp_path):
    import torch
    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.anchor = torch.nn.Parameter(torch.zeros(1))
        def forward(self, tensor):
            self.observed = tensor.detach().clone()
            return torch.tensor([[0.0, 10.0]])
    model = FakeModel()
    metadata = dict(classes=['EMPTY', 'PRESENT'], crop_pipeline=providers.PRESENCE_CROP_PIPELINE,
                    input_size=16, validated=False, authority='AUTHORITATIVE')
    provider = providers.SlotPresenceClassifier(tmp_path, device='cpu')
    provider._models['hbm'] = (model, metadata, tmp_path / 'unused.pt')
    image = np.full((100, 100, 3), (20, 40, 80), np.uint8)
    before = image.copy()
    result = provider.inspect(slot(), image)
    assert result.authority == 'ADVISORY_ONLY' and result.status == 'UNKNOWN'
    mean, std = np.array([.485, .456, .406]), np.array([.229, .224, .225])
    np.testing.assert_allclose(model.observed[0, :, 0, 0].numpy(),
                               (np.array([80, 40, 20]) / 255 - mean) / std, atol=1e-6)
    np.testing.assert_array_equal(image, before)
    metadata['classes'].reverse()
    assert provider.inspect(slot(), image).authority == 'INVALID'
