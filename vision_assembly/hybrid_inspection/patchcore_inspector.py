#!/usr/bin/env python3
"""Anomalib 2.6 component PatchCore wrapper with fail-safe thresholds."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[2]
INSPECTION_DIR = PROJECT_DIR / "vision_assembly/inspection"
if str(INSPECTION_DIR) not in sys.path:
    sys.path.insert(0, str(INSPECTION_DIR))

from build_component_patchcore_dataset import OUTPUT_SIZE, _crop_slot  # noqa: E402
from predict_component_patchcore import _checkpoint, _predict_outputs  # noqa: E402


@dataclass
class PatchCoreEvidence:
    slot_id: str
    component_key: str
    status: str
    authority: str
    score: float | None
    reason: str
    pass_max: float | None
    fail_min: float | None
    normal_p99: float | None
    normal_pixel_p999: float | None
    anomaly_map: np.ndarray | None

    def report_dict(self) -> dict[str, Any]:
        spatial = None
        if self.anomaly_map is not None and self.normal_pixel_p999 is not None:
            array = np.asarray(self.anomaly_map, np.float32).squeeze()
            if array.ndim == 2 and np.isfinite(array).all():
                h, w = array.shape
                # Training crop adds .22 of slot size on every side.
                # Restrict diagnostics to the physical fixed slot, not padding.
                iy, ix = int(round(h*.22/1.44)), int(round(w*.22/1.44))
                inside = array[iy:h-iy, ix:w-ix]
                if inside.size:
                    spatial = {'slot_peak': float(inside.max()),
                               'crop_peak': float(array.max()),
                               'slot_above_normal_fraction': float(np.mean(inside > self.normal_pixel_p999))}
        return {
            "slot_id": self.slot_id,
            "component_key": self.component_key,
            "status": self.status,
            "authority": self.authority,
            "score": self.score,
            "reason": self.reason,
            "pass_max": self.pass_max,
            "fail_min": self.fail_min,
            "normal_p99": self.normal_p99,
            "normal_pixel_p999": self.normal_pixel_p999,
            "spatial_evidence": spatial,
        }


def valid_prediction(prediction: dict[str, Any]) -> bool:
    """An absent/corrupt anomaly map is not a zero-anomaly result."""
    try:
        score = float(prediction['score'])
        anomaly_map = np.asarray(prediction['anomaly_map'], dtype=np.float32)
        return bool(np.isfinite(score) and anomaly_map.ndim == 2
                    and anomaly_map.size > 0 and np.isfinite(anomaly_map).all())
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


class ComponentPatchCoreInspector:
    """Run one PatchCore memory bank per component type.

    The RGB/BGR colour crop is saved without CLAHE.  The existing training
    crop orientation and output size are reused exactly.  A normal-only p99 is
    evidence, not a defect threshold; authoritative decisions require a
    separate controlled-defect ``decision_thresholds.json`` file.
    """

    def __init__(
        self,
        model_root: Path,
        normal_calibration: Path | None = None,
        decision_thresholds: Path | None = None,
        component_model_roots: dict[str, Path] | None = None,
    ):
        self.model_root = model_root.expanduser().resolve()
        self.normal_calibration_path = (
            normal_calibration.expanduser().resolve()
            if normal_calibration
            else self.model_root / "normal_calibration.json"
        )
        self.threshold_path = (
            decision_thresholds.expanduser().resolve()
            if decision_thresholds
            else self.model_root / "decision_thresholds.json"
        )
        self.normal = self._load_optional(self.normal_calibration_path)
        self.thresholds = self._load_optional(self.threshold_path)
        self.component_model_roots = {
            key: value.expanduser().resolve()
            for key, value in (component_model_roots or {}).items()
        }
        self.component_normal = {
            key: self._load_optional(root / "normal_calibration.json")
            for key, root in self.component_model_roots.items()
        }
        self.component_thresholds = {
            key: self._load_optional(root / "decision_thresholds.json")
            for key, root in self.component_model_roots.items()
        }

    @staticmethod
    def _load_optional(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Calibration must be a JSON object")
            return payload
        except (OSError, ValueError) as error:
            return {"_load_error": type(error).__name__}

    def _decision(self, component: str, score: float) -> tuple[str, str, float | None, float | None, str]:
        thresholds = self.component_thresholds.get(component, self.thresholds)
        try:
            if "_load_error" in thresholds:
                raise ValueError("Threshold file is invalid")
            settings = thresholds.get("components", {}).get(component)
            if not np.isfinite(score):
                raise ValueError("Score is not finite")
            if settings:
                pass_max = float(settings["pass_max"])
                fail_min = float(settings["fail_min"])
                if not np.isfinite([pass_max, fail_min]).all():
                    raise ValueError("Thresholds are not finite")
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            return "UNKNOWN", "INVALID", None, None, "INVALID_THRESHOLD_OR_SCORE"
        if not settings:
            return "UNKNOWN", "ADVISORY_ONLY", None, None, "CONTROLLED_DEFECT_THRESHOLD_MISSING"
        if pass_max >= fail_min:
            return "UNKNOWN", "INVALID", pass_max, fail_min, "INVALID_THRESHOLD_ORDER"
        authority = str(settings.get("authority", "ADVISORY_ONLY"))
        if score <= pass_max:
            observed, reason = "PASS", "ANOMALY_SCORE_BELOW_PASS_MAX"
        elif score >= fail_min:
            observed, reason = "FAIL", "ANOMALY_SCORE_ABOVE_FAIL_MIN"
        else:
            observed, reason = "UNKNOWN", "ANOMALY_SCORE_IN_GRAY_ZONE"
        return observed if authority == "AUTHORITATIVE" else "UNKNOWN", authority, pass_max, fail_min, reason

    def inspect(self, aligned_bgr: np.ndarray, slots: list[Any], run_dir: Path) -> dict[str, PatchCoreEvidence]:
        # All inference assets are local checkpoints; production inspection
        # must not wait for an external model registry.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        crop_root = run_dir / "patchcore_crops"
        prediction_root = run_dir / "patchcore_runtime"
        grouped: dict[str, list[Any]] = {}
        results: dict[str, PatchCoreEvidence] = {}
        for slot in slots:
            component = slot.component_key
            try:
                output_size = OUTPUT_SIZE[slot.component_type]
                crop, _, _ = _crop_slot(
                    aligned_bgr, slot.geometry, 0.22, output_size,
                )
                destination = crop_root / component / f"{slot.slot_id}.png"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
                    raise RuntimeError(f"Cannot save PatchCore input crop: {destination}")
            except Exception as error:
                results[slot.slot_id] = PatchCoreEvidence(
                    slot.slot_id, component, "UNKNOWN", "UNAVAILABLE", None,
                    f"PATCHCORE_CROP_ERROR:{type(error).__name__}",
                    None, None, None, None, None,
                )
                continue
            grouped.setdefault(component, []).append(slot)

        for component, component_slots in grouped.items():
            component_root = self.component_model_roots.get(component, self.model_root)
            normal_payload = self.component_normal.get(component, self.normal)
            normal_p99 = normal_pixel_p999 = None
            try:
                if "_load_error" in normal_payload:
                    raise ValueError("Normal calibration file is invalid")
                normal_settings = normal_payload.get("components", {}).get(component, {})
                values = [normal_settings.get(kind, {}).get("percentiles", {}).get(percentile)
                          for kind, percentile in (("score", "99.0"), ("pixel", "99.9"))]
                values = [float(value) if value is not None else None for value in values]
                if any(value is not None and not np.isfinite(value) for value in values):
                    raise ValueError("Normal calibration contains nonfinite values")
                normal_p99, normal_pixel_p999 = values
                checkpoint = _checkpoint(component_root, component)
                predictions = _predict_outputs(
                    component,
                    crop_root / component,
                    checkpoint,
                    prediction_root / component,
                )
                if not isinstance(predictions, dict):
                    raise ValueError("PatchCore predictions must be keyed by slot ID")
            except Exception as error:  # provider failure becomes UNKNOWN, never PASS
                for slot in component_slots:
                    results[slot.slot_id] = PatchCoreEvidence(
                        slot.slot_id,
                        component,
                        "UNKNOWN",
                        "UNAVAILABLE",
                        None,
                        f"PATCHCORE_PROVIDER_ERROR:{type(error).__name__}",
                        None,
                        None,
                        normal_p99,
                        normal_pixel_p999,
                        None,
                    )
                continue

            for slot in component_slots:
                prediction = predictions.get(slot.slot_id)
                if prediction is None or not valid_prediction(prediction):
                    results[slot.slot_id] = PatchCoreEvidence(
                        slot.slot_id,
                        component,
                        "UNKNOWN",
                        "UNAVAILABLE",
                        None,
                        "PATCHCORE_OUTPUT_MISSING" if prediction is None else "PATCHCORE_OUTPUT_INVALID",
                        None,
                        None,
                        normal_p99,
                        normal_pixel_p999,
                        None,
                    )
                    continue
                score = float(prediction["score"])
                status, authority, pass_max, fail_min, reason = self._decision(component, score)
                results[slot.slot_id] = PatchCoreEvidence(
                    slot.slot_id,
                    component,
                    status,
                    authority,
                    score,
                    reason,
                    pass_max,
                    fail_min,
                    normal_p99,
                    normal_pixel_p999,
                    prediction.get("anomaly_map"),
                )
        return results
