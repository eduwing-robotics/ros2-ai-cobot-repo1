import cv2
import numpy as np
from hbm_pin_bands import check_hbm_pin_bands
from hbm_pin_bands import inspect_hbm_pins
import json
import hashlib


def sample():
    a = np.full((240, 170, 3), 35, np.uint8)
    for x in (25, 130):
        for y in range(30, 186, 12):
            cv2.rectangle(a, (x, y), (x + 5, y + 6), (220, 220, 220), -1)
    return a


def test_reference_required():
    assert check_hbm_pin_bands(sample(), "PRESENT").status == "UNKNOWN"


def test_identical_is_not_certified_pass():
    r = check_hbm_pin_bands(sample(), "PRESENT", sample())
    assert r.status == "UNKNOWN"
    assert r.authority == "ADVISORY_ONLY"


def test_long_gap_right():
    ref = sample()
    a = ref.copy()
    a[28:145, 118:149] = 35
    r = check_hbm_pin_bands(a, "PRESENT", ref)
    assert r.status == "FAIL"
    assert r.measured["candidate_sides"] == ["right"]
    assert r.authority == "ADVISORY_ONLY"


def test_empty_abstains():
    assert check_hbm_pin_bands(sample(), "EMPTY", sample()).status == "UNKNOWN"


def test_dark_and_wrong_shape_abstain():
    ref = sample()
    assert check_hbm_pin_bands(ref * 0, "PRESENT", ref).status == "UNKNOWN"
    assert check_hbm_pin_bands(ref, "PRESENT", ref[:40]).status == "UNKNOWN"


def test_runtime_missing_reference_and_bad_alignment(tmp_path):
    for alignment in (False, True):
        r = inspect_hbm_pins("hbm_08", sample(), "PRESENT", alignment, root=tmp_path)
        assert r.status == "UNKNOWN" and r.authority == "UNAVAILABLE"


def test_runtime_hash_and_authority(tmp_path):
    p = tmp_path / "ref.png"
    cv2.imwrite(str(p), sample())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"reference_id": "test", "authority": "VALIDATED",
        "slots": {"hbm_08": {"path": "ref.png", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}}}))
    a = sample()
    a[28:145, 118:149] = 35
    r = inspect_hbm_pins("hbm_08", a, "PRESENT", True, tmp_path, manifest)
    assert r.status == "FAIL" and r.authority == "ADVISORY_ONLY"
    p.write_bytes(b"changed")
    r = inspect_hbm_pins("hbm_08", a, "PRESENT", True, tmp_path, manifest)
    assert r.reason == "HBM_PIN_REFERENCE_HASH_MISMATCH"


def test_dark_runtime_explains_abstention(tmp_path):
    p = tmp_path / "ref.png"
    cv2.imwrite(str(p), sample())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"reference_id": "test", "slots": {
        "hbm_08": {"path": "ref.png", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}}}))
    r = inspect_hbm_pins("hbm_08", sample() * 0, "PRESENT", True, tmp_path, manifest)
    assert r.status == "UNKNOWN"
    assert r.reason == "HBM_PIN_OBSERVATION_INSUFFICIENT_RECAPTURE"
    assert r.measured["observation_quality"]["recapture_recommended"] is True
    assert set(r.measured["observation_quality"]["uncertain_sides"]) == {"left", "right"}
    assert all(s["reason"] == "INSUFFICIENT_VISIBLE_PIN_ANCHORS"
               for s in r.measured["individual_pins"])


def test_uncertain_other_side_does_not_erase_candidate(tmp_path):
    p = tmp_path / "ref.png"
    cv2.imwrite(str(p), sample())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"reference_id": "test", "slots": {
        "hbm_08": {"path": "ref.png", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}}}))
    image = sample()
    image[:, :45] = 0
    image[28:145, 118:149] = 35
    r = inspect_hbm_pins("hbm_08", image, "PRESENT", True, tmp_path, manifest)
    assert r.status == "FAIL" and r.authority == "ADVISORY_ONLY"
    assert r.measured["observation_quality"]["recapture_recommended"] is True
    assert "left" in r.measured["observation_quality"]["uncertain_sides"]


def test_reference_deficiency_is_not_sample_recapture(tmp_path):
    p = tmp_path / "ref.png"
    reference = sample()
    reference[:, :45] = 0
    cv2.imwrite(str(p), reference)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"reference_id": "test", "slots": {
        "hbm_08": {"path": "ref.png", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}}}))
    r = inspect_hbm_pins("hbm_08", sample(), "PRESENT", True, tmp_path, manifest)
    assert r.status == "UNKNOWN"
    assert r.reason == "HBM_PIN_REFERENCE_INSUFFICIENT"
    q = r.measured["observation_quality"]
    assert q["reference_review_required"] is True
    assert q["reference_insufficient_sides"] == ["left"]
    assert q["recapture_recommended"] is False
    dark = sample()
    dark[:, 110:] = 0
    r = inspect_hbm_pins("hbm_08", dark, "PRESENT", True, tmp_path, manifest)
    q = r.measured["observation_quality"]
    assert q["reference_review_required"] is True
    assert q["recapture_recommended"] is True
    assert q["sample_uncertain_sides"] == ["right"]
