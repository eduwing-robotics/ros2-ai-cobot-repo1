import numpy as np

from train_pcb_patchcore import fixed_anomaly_u8


def test_fixed_heatmap_does_not_stretch_each_frame():
    first = fixed_anomaly_u8(np.asarray([[0.0, 0.2]], dtype=np.float32))
    second = fixed_anomaly_u8(np.asarray([[0.0, 0.8]], dtype=np.float32))
    assert first[0, 1] == 51
    assert second[0, 1] == 204


def test_fixed_heatmap_clips_invalid_and_out_of_range_values():
    result = fixed_anomaly_u8(
        np.asarray([[-1.0, np.nan, 0.5, 2.0]], dtype=np.float32)
    )
    assert result.tolist() == [[0, 0, 127, 255]]


def test_visible_min_suppresses_normal_heat_and_keeps_fixed_scale():
    result = fixed_anomaly_u8(
        np.asarray([[0.2, 0.35, 0.675, 1.0]], dtype=np.float32),
        visible_min=0.35,
    )
    assert result.tolist() == [[0, 0, 127, 255]]
