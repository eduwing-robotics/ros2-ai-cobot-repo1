"""CPU-only checks for PatchCore device selection.

These tests never load a checkpoint.  Runtime authority and thresholds are
tested by the hybrid suite; this file only protects the development fallback
from silently accepting an invalid accelerator request.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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
