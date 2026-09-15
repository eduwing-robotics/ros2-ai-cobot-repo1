"""Advisory long pin-band gaps; no individual-pin count or PASS authority."""
import cv2
import numpy as np
import hashlib
import json
from pathlib import Path
from opencv_inspectors import CheckEvidence, clahe_gray


def inspect_hbm_pins(slot_id, crop_bgr, presence_state, alignment_valid,
                     root=None, manifest_path=None):
    """Pinned reference, fail-closed IO, and advisory-only runtime adapter."""
    def unavailable(reason):
        return CheckEvidence("hbm_pin_bands", "UNKNOWN", "UNAVAILABLE", 0.0,
                             reason, {}, {})
    if not alignment_valid:
        return unavailable("HBM_PIN_ALIGNMENT_INVALID")
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    manifest_path = manifest_path or root / "vision_assembly/config/hbm_pin_reference.json"
    try:
        manifest = json.loads(Path(manifest_path).read_text())
        entry = manifest["slots"][slot_id]
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            return unavailable("HBM_PIN_REFERENCE_PATH_INVALID")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            return unavailable("HBM_PIN_REFERENCE_HASH_MISMATCH")
        reference = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if reference is None:
            return unavailable("HBM_PIN_REFERENCE_DECODE_FAILED")
        evidence = check_hbm_pin_bands(crop_bgr, presence_state, reference)
        if presence_state == "PRESENT" and crop_bgr is not None and crop_bgr.shape == reference.shape:
            from hbm_individual_pins import compare
            individual = compare(reference, crop_bgr)
            evidence.measured["individual_pins"] = [
                {k: side[k] for k in ("side", "status", "reason", "reference_peaks",
                    "missing_indices", "uncertain_indices", "evidence_ratio", "defect_points_px")}
                for side in individual]
            uncertain_sides = [side["side"] for side in individual
                               if side["status"] not in ("PASS", "FAIL")]
            reference_sides = [side["side"] for side in individual
                               if side["reason"] == "REFERENCE_PIN_ANCHORS_INSUFFICIENT"]
            sample_sides = [side for side in uncertain_sides if side not in reference_sides]
            evidence.measured["observation_quality"] = {
                "status": "INSUFFICIENT" if uncertain_sides else "NO_EXISTING_ABSTENTION",
                "uncertain_sides": uncertain_sides,
                "recapture_recommended": bool(sample_sides),
                "reference_review_required": bool(reference_sides),
                "reference_insufficient_sides": reference_sides,
                "sample_uncertain_sides": sample_sides,
                "basis": "EXISTING_PER_PIN_ABSTENTION_NOT_NEW_BRIGHTNESS_THRESHOLD",
                "certifies_visibility_or_normality": False,
            }
            points = [p for side in individual for p in side["defect_points_px"]]
            evidence.measured["defect_points_crop_px"] = points
            if points:
                evidence.status = "FAIL"
                evidence.reason = "HBM_INDIVIDUAL_PIN_ABSENCE_CANDIDATE"
            elif uncertain_sides and evidence.status == "UNKNOWN":
                evidence.reason = ("HBM_PIN_REFERENCE_INSUFFICIENT" if reference_sides
                                   else "HBM_PIN_OBSERVATION_INSUFFICIENT_RECAPTURE")
        evidence.measured["reference_id"] = manifest["reference_id"]
        evidence.measured["reference_sha256"] = entry["sha256"]
        evidence.measured["position_or_occlusion_confound_not_excluded"] = True
        return evidence
    except (OSError, ValueError, KeyError, TypeError, cv2.error):
        return unavailable("HBM_PIN_REFERENCE_UNAVAILABLE")


def check_hbm_pin_bands(crop_bgr, presence_state="UNKNOWN", reference_bgr=None):
    limits = {"long_gap_fraction": 0.40, "minimum_white_pixels": 8,
              "scope": "long contiguous pin-band absence, not single irregular pins"}
    def result(reason, measured=None, status="UNKNOWN"):
        return CheckEvidence("hbm_pin_bands", status, "ADVISORY_ONLY", 0.0,
                             reason, measured or {}, limits)
    if presence_state != "PRESENT":
        return result("HBM_PIN_PRESENCE_UNCERTAIN")
    if crop_bgr is None or min(crop_bgr.shape[:2]) < 32:
        return result("HBM_PIN_IMAGE_INVALID")
    h, w = crop_bgr.shape[:2]
    raw = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    enhanced = clahe_gray(crop_bgr)
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    white = (raw >= 130) & (enhanced >= 150) & (hsv[..., 1] <= 100)
    # Fixed bands preserve slot-relative position. Exclude logo, dot and adjacent slots.
    y0, y1 = int(h * .12), int(h * .78)
    measured = {"bands": {}, "candidate_sides": []}
    for side, xa, xb in (("left", .06, .25), ("right", .69, .88)):
        x0, x1 = int(w * xa), int(w * xb)
        band = white[y0:y1, x0:x1]
        rows = np.count_nonzero(band, axis=1) >= 2
        # Bridge small inter-pin spaces, but retain extended missing runs.
        rows = cv2.morphologyEx(rows.astype(np.uint8)[:, None], cv2.MORPH_CLOSE,
                               np.ones((max(3, int(h * .04)), 1), np.uint8))[:, 0]
        longest = current = 0
        for present in rows:
            current = 0 if present else current + 1
            longest = max(longest, current)
        gap = longest / max(1, len(rows))
        # A remaining bright pin anchors visibility; fully dark bands abstain.
        visible = int(band.sum()) >= limits["minimum_white_pixels"]
        measured["bands"][side] = {"bbox_px": [x0, y0, x1, y1],
            "white_pixels": int(band.sum()), "longest_gap_fraction": gap,
            "visibility_anchor": visible}
        if visible and gap >= limits["long_gap_fraction"]:
            measured["candidate_sides"].append(side)
    # Absolute darkness is not defect evidence: normal pins may be occluded.
    measured["absolute_gap_sides"] = measured["candidate_sides"][:]
    measured["candidate_sides"] = []
    if reference_bgr is None or reference_bgr.shape != crop_bgr.shape:
        return result("HBM_PIN_REFERENCE_REQUIRED", measured)
    reference = check_hbm_pin_bands(reference_bgr, "PRESENT")
    baseline = reference.measured.get("bands", {})
    for side in measured["absolute_gap_sides"]:
        before = baseline.get(side, {})
        after = measured["bands"][side]
        delta = after["longest_gap_fraction"] - before.get("longest_gap_fraction", 1.0)
        after["gap_increase_from_reference"] = delta
        if before.get("visibility_anchor") and delta >= .35:
            measured["candidate_sides"].append(side)
    limits["minimum_gap_increase"] = .35
    return result("HBM_LONG_PIN_GAP_CANDIDATE" if measured["candidate_sides"]
                  else "HBM_PIN_BANDS_NOT_CONFIRMED", measured,
                  "FAIL" if measured["candidate_sides"] else "UNKNOWN")
