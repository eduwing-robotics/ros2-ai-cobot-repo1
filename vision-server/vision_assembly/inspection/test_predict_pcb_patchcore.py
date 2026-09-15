import pytest

from predict_pcb_patchcore import triage


def test_provisional_triage_boundaries():
    assert triage(0.40, 0.40, 0.55) == "NORMAL_CANDIDATE"
    assert triage(0.41, 0.40, 0.55) == "RECHECK"
    assert triage(0.55, 0.40, 0.55) == "ANOMALY_CANDIDATE"


def test_triage_rejects_invalid_threshold_order():
    with pytest.raises(ValueError):
        triage(0.5, 0.6, 0.5)
