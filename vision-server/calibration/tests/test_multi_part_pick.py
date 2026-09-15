import sys
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import detect_small_part_dry_run as detector  # noqa: E402
import full_pick_place_same_spot as workflow  # noqa: E402
import pick_part_with_gripper_camera as multi_part  # noqa: E402


def make_depth_mask_detector(depth):
    instance = object.__new__(detector.SmallPartDetector)
    instance.args = SimpleNamespace(
        min_support_depth_pixels=40,
        min_observed_height_mm=0.5,
        part_height_mm=8.0,
        depth_mask_height_fraction=0.35,
        height_tolerance_mm=2.0,
    )
    instance.depth = depth.astype(np.float32)
    return instance


def test_depth_segmentation_recovers_raised_part_on_sloped_plane():
    yy, xx = np.indices((120, 160), dtype=np.float32)
    support = 0.500 + 0.000015 * xx + 0.000010 * yy
    depth = support.copy()
    depth[48:72, 65:95] -= 0.008
    instance = make_depth_mask_detector(depth)

    mask = instance._build_depth_mask(instance.depth)

    assert mask[60, 80] == 255
    assert mask[10, 10] == 0
    assert 500 <= np.count_nonzero(mask) <= 900


def test_depth_segmentation_rejects_flat_sloped_support():
    yy, xx = np.indices((120, 160), dtype=np.float32)
    depth = 0.500 + 0.000015 * xx + 0.000010 * yy
    instance = make_depth_mask_detector(depth)

    mask = instance._build_depth_mask(instance.depth)

    assert np.count_nonzero(mask) == 0


def test_profile_catalog_resolves_all_six_parts_and_aliases():
    catalog = multi_part.load_catalog(multi_part.DEFAULT_PROFILE_CONFIG)

    assert set(catalog['profiles']) == {
        'gpu', 'hbm', 'vrm', 'power_module', 'inductor', 'smd_capacitor'
    }
    assert multi_part.resolve_profile(catalog, 'black-block')[0] == 'vrm'
    assert multi_part.resolve_profile(catalog, 'SMD')[0] == 'smd_capacitor'
    assert multi_part.resolve_profile(catalog, 'long orange')[0] == 'power_module'


def test_profile_dimensions_match_candidate_source():
    catalog = multi_part.load_catalog(multi_part.DEFAULT_PROFILE_CONFIG)
    source_path = (
        multi_part.PROJECT_ROOT
        / catalog['source_dimensions_file']
    )
    source = json.loads(source_path.read_text(encoding='utf-8'))['parts']

    for profile in catalog['profiles'].values():
        candidate = source[profile['source_part_spec_id']]['nominal_size_mm']
        nominal = profile['nominal_size_mm']
        assert [nominal['length'], nominal['width']] == sorted(
            [candidate['x'], candidate['y']], reverse=True
        )
        assert nominal['height'] == candidate['height']


def test_dark_and_orange_appearance_masks_do_not_merge_white_support():
    frame = np.full((100, 100, 3), 235, dtype=np.uint8)
    frame[35:65, 30:70] = (20, 20, 20)
    instance = object.__new__(detector.SmallPartDetector)
    instance.args = SimpleNamespace(
        segmentation_mode='dark', max_gray=180.0, dark_gray_delta=20.0,
        min_gray=55.0, gray_delta=24.0, part_color='any',
    )
    dark_mask = instance._build_mask(frame)
    assert dark_mask[50, 50] == 255
    assert dark_mask[10, 10] == 0

    frame[35:65, 30:70] = (0, 140, 255)
    instance.args.segmentation_mode = 'bright'
    instance.args.part_color = 'orange'
    orange_mask = instance._build_mask(frame)
    assert orange_mask[50, 50] == 255
    assert orange_mask[10, 10] == 0


def test_inductor_uses_depth_and_preserves_orientation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        multi_part, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )

    multi_part.main(['--part-type', 'inductor', '--approach-only'])

    assert len(calls) == 2
    detect = calls[0][1]
    pick = calls[1][1]
    assert detect[detect.index('--part-shape') + 1] == 'circle'
    assert detect[detect.index('--segmentation-mode') + 1] == 'depth'
    assert detect[detect.index('--orientation-mode') + 1] == 'preserve'
    assert pick[pick.index('--orientation-mode') + 1] == 'preserve'
    assert '--approach-only' in pick
    assert '--dry-run' in pick


def test_unvalidated_contact_pick_is_blocked_before_subprocess(monkeypatch):
    calls = []
    monkeypatch.setattr(
        multi_part, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )

    with pytest.raises(SystemExit):
        multi_part.main([
            '--part-type', 'hbm',
            '--grasp-z-offset-mm', '-4',
            '--gripper-close-position', '20',
            '--execute', '--confirm-full-cycle',
        ])

    assert calls == []


def test_unvalidated_live_approach_is_blocked_before_subprocess(monkeypatch):
    calls = []
    monkeypatch.setattr(
        multi_part, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )

    with pytest.raises(SystemExit):
        multi_part.main([
            '--part-type', 'hbm', '--approach-only',
            '--execute', '--confirm-approach-only',
        ])

    assert calls == []


def test_explicitly_unlocked_contact_path_builds_full_cycle(monkeypatch):
    calls = []
    monkeypatch.setattr(
        multi_part, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )

    multi_part.main([
        '--part-type', 'hbm',
        '--grasp-z-offset-mm', '-4',
        '--gripper-close-position', '20',
        '--allow-unvalidated-part-profile',
        '--allow-provisional-calibration',
        '--execute', '--confirm-full-cycle',
    ])

    assert len(calls) == 2
    pick = calls[1][1]
    assert '--execute' in pick
    assert '--confirm-full-cycle' in pick
    assert '--approach-only' not in pick
    assert pick[pick.index('--grasp-z-offset-mm') + 1] == '-4.0'
    assert pick[pick.index('--gripper-close-position') + 1] == '20'
    assert '--allow-provisional-calibration' in pick
    assert '--allow-unvalidated-part-profile' in pick


def test_axis_free_workflow_omits_alignment_and_axis_check(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow, 'validate_target_file', lambda *args: {})
    monkeypatch.setattr(
        workflow, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )
    monkeypatch.setattr(workflow, 'gripper_open', lambda position: None)
    monkeypatch.setattr(sys, 'argv', [
        'full_pick_place_same_spot.py',
        '--skip-detection', '--target-file', 'target.json',
        '--part-profile-id', 'inductor',
        '--part-shape', 'circle',
        '--orientation-mode', 'preserve',
        '--segmentation-mode', 'depth',
        '--grasp-z-offset-mm', '-4',
        '--allow-unvalidated-part-profile',
        '--allow-provisional-calibration',
        '--execute', '--confirm-full-cycle',
    ])

    workflow.main()

    approach_commands = [
        command for _, command in calls
        if 'run_object_approach.sh' in command[0]
    ]
    cycle = next(
        command for _, command in calls
        if 'run_grasp_place_cycle.sh' in command[0]
    )
    assert approach_commands
    assert all('--align-part' not in command for command in approach_commands)
    assert cycle[cycle.index('--orientation-mode') + 1] == 'preserve'


def test_low_level_workflow_cannot_bypass_profile_motion_gate(monkeypatch):
    calls = []
    monkeypatch.setattr(
        workflow, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )
    monkeypatch.setattr(sys, 'argv', [
        'full_pick_place_same_spot.py',
        '--part-profile-id', 'hbm',
        '--part-length-mm', '14.30996',
        '--part-width-mm', '10.24665',
        '--part-height-mm', '9.81511',
        '--part-shape', 'rectangle',
        '--orientation-mode', 'long_axis',
        '--segmentation-mode', 'dark',
        '--part-color', 'any',
        '--approach-only', '--execute', '--confirm-approach-only',
    ])

    with pytest.raises(SystemExit):
        workflow.main()

    assert calls == []
