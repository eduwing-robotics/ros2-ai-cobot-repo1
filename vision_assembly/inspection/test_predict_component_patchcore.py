"""CPU-only checks for PatchCore device selection.

These tests never load a checkpoint.  Runtime authority and thresholds are
tested by the hybrid suite; this file only protects the development fallback
from silently accepting an invalid accelerator request.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from types import SimpleNamespace
import predict_component_patchcore as predictor
from predict_component_patchcore import resolve_accelerator, torch


def test_explicit_cpu_is_available_without_cuda():
    assert resolve_accelerator("cpu") == "cpu"


def test_auto_follows_cuda_availability(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_accelerator("auto") == "cpu"
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert resolve_accelerator("auto") == "gpu"


def test_gpu_request_fails_closed_without_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        resolve_accelerator("gpu")


def test_unknown_accelerator_is_rejected():
    with pytest.raises(ValueError, match="accelerator"):
        resolve_accelerator("tpu")


@pytest.mark.parametrize('kind', ['tensor', 'array', 'list'])
def test_anomaly_conversion_exactly_matches_old_float32_values(kind):
    values = np.array([[[.123456789, -2], [float('nan'), float('inf')]]], dtype=np.float64)
    value = torch.tensor(values, requires_grad=True) if kind == 'tensor' else (
        values.tolist() if kind == 'list' else values)
    old = np.asarray(predictor.json_safe(value), dtype=np.float32).squeeze()
    actual = predictor.anomaly_array(value)
    np.testing.assert_array_equal(actual, old)
    assert actual.dtype == np.float32 and actual.shape == (2, 2)


@pytest.fixture
def fake_inference(monkeypatch):
    state = SimpleNamespace(models=[], calls=[], fail=False)
    class Model:
        @staticmethod
        def configure_pre_processor(**kwargs):
            return kwargs
        def __init__(self, **kwargs):
            self.loaded = False
            state.models.append(self)
    class Engine:
        def __init__(self, **kwargs):
            self.output = kwargs['default_root_dir']
        def predict(self, *, model, ckpt_path, data_path, return_predictions):
            state.calls.append((model, ckpt_path, data_path, self.output))
            if state.fail:
                raise RuntimeError('prediction failed')
            if ckpt_path is None:
                assert model.loaded
            else:
                model.loaded = True
            return [SimpleNamespace(image_path=[str(Path(data_path) / 'slot.png')],
                pred_score=torch.tensor([.5]), anomaly_map=torch.ones(1, 2, 2))]
    monkeypatch.setitem(sys.modules, 'anomalib.engine', SimpleNamespace(Engine=Engine))
    monkeypatch.setitem(sys.modules, 'anomalib.models', SimpleNamespace(Patchcore=Model))
    monkeypatch.setattr(predictor, '_MODEL_CACHE', predictor.OrderedDict())
    monkeypatch.setattr(predictor, '_MODEL_CACHE_ENABLED', False)
    return state


def test_cache_disabled_for_one_shot_cli(tmp_path, fake_inference):
    checkpoint = tmp_path / 'model.ckpt'
    checkpoint.write_bytes(b'weights')
    for _ in range(2):
        predictor._predict_outputs('gpu', tmp_path, checkpoint, tmp_path, accelerator='cpu')
    assert len(fake_inference.models) == 2
    assert not predictor._MODEL_CACHE


def test_worker_reuses_only_model_and_reloads_replaced_weights(tmp_path, fake_inference):
    checkpoint = tmp_path / 'model.ckpt'
    checkpoint.write_bytes(b'weights')
    predictor.enable_model_cache()
    for index in range(2):
        predictor._predict_outputs('gpu', tmp_path / f'input{index}', checkpoint,
            tmp_path / f'output{index}', accelerator='cpu')
    assert len(fake_inference.models) == 1
    assert [call[1] for call in fake_inference.calls] == [checkpoint, None]
    assert fake_inference.calls[0][2:] != fake_inference.calls[1][2:]
    replacement = tmp_path / 'replacement.ckpt'
    replacement.write_bytes(b'weights')
    replacement.replace(checkpoint)
    predictor._predict_outputs('gpu', tmp_path, checkpoint, tmp_path, accelerator='cpu')
    assert len(fake_inference.models) == 2
    assert fake_inference.calls[-1][1] == checkpoint
    assert len(predictor._MODEL_CACHE) == 1


def test_prediction_failure_evicts_cached_model(tmp_path, fake_inference):
    checkpoint = tmp_path / 'model.ckpt'
    checkpoint.write_bytes(b'weights')
    predictor.enable_model_cache()
    predictor._predict_outputs('gpu', tmp_path, checkpoint, tmp_path, accelerator='cpu')
    fake_inference.fail = True
    with pytest.raises(RuntimeError, match='prediction failed'):
        predictor._predict_outputs('gpu', tmp_path, checkpoint, tmp_path, accelerator='cpu')
    assert not predictor._MODEL_CACHE
    fake_inference.fail = False
    predictor._predict_outputs('gpu', tmp_path, checkpoint, tmp_path, accelerator='cpu')
    assert len(fake_inference.models) == 2


def test_cache_size_bounded(tmp_path, fake_inference, monkeypatch):
    checkpoint = tmp_path / 'model.ckpt'
    checkpoint.write_bytes(b'weights')
    monkeypatch.setattr(predictor, '_MODEL_CACHE_LIMIT', 1)
    predictor.enable_model_cache()
    for component in ('gpu', 'hbm', 'gpu'):
        predictor._predict_outputs(component, tmp_path, checkpoint, tmp_path, accelerator='cpu')
    assert len(predictor._MODEL_CACHE) == 1 and len(fake_inference.models) == 3
