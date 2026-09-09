import numpy as np

from predict_component_patchcore import (
    _fixed_excess_map, _heatmap_images, _normalize_component_maps, _paste_max,
    _restore_slot_map, _trim_map_to_slot,
)


def test_fixed_excess_map_does_not_stretch_normal_frame():
    first = _fixed_excess_map(np.asarray([[0.19, 0.20, 0.24]], np.float32), 0.20)
    second = _fixed_excess_map(np.asarray([[0.19, 0.20, 0.80]], np.float32), 0.20)
    assert first[0, 0] == 0.0
    assert first[0, 1] == 0.0
    assert 0.0 < first[0, 2] < 1.0
    assert second[0, 2] == 1.0


def test_restore_rotated_slot_map_returns_original_crop_shape():
    model_map = np.arange(24, dtype=np.float32).reshape(4, 6)
    restored = _restore_slot_map(model_map, (8, 12), True)
    assert restored.shape == (12, 8)


def test_trim_removes_context_margin():
    trimmed = _trim_map_to_slot(np.zeros((14, 20), dtype=np.float32), (10, 6))
    assert trimmed.shape == (6, 10)


def test_component_normalization_and_overlay_preserve_uncovered_source():
    destination = np.zeros((20, 30), dtype=np.float32)
    coverage = np.zeros((20, 30), dtype=np.uint8)
    normalized = _normalize_component_maps([
        ("a", np.arange(48, dtype=np.float32).reshape(6, 8))
    ])[0][1]
    _paste_max(destination, coverage, normalized, (15, 10))
    source = np.full((20, 30, 3), 120, dtype=np.uint8)
    heatmap, overlay = _heatmap_images(source, destination, coverage)
    assert np.count_nonzero(coverage) == 48
    assert tuple(overlay[0, 0]) == (120, 120, 120)
    assert tuple(heatmap[10, 15]) != tuple(heatmap[0, 0])
