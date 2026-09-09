#!/usr/bin/env python3
"""S22 board registration, fixed-slot crops, and optional YOLO evidence.

Raw colour pixels are preserved for learned providers.  CLAHE deliberately
does not appear in this module; it belongs only to local OpenCV checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[2]
INSPECTION_DIR = PROJECT_DIR / "vision_assembly/inspection"
CAMERA_DIR = PROJECT_DIR / "camera2_scrcpy"
SLOT_CLASSIFIER_DIR = PROJECT_DIR / "vision_assembly/slot_classifier"
for directory in (INSPECTION_DIR, CAMERA_DIR, SLOT_CLASSIFIER_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from extract_inspection_roi import detect_board, operator_source_corners  # noqa: E402
from full_board_inspector import (  # noqa: E402
    _load_image,
    _load_json,
    _project_path,
    align_board,
    board_alignment_mask,
    slot_geometry,
)
from layout_overrides import apply_component_slot_overrides  # noqa: E402
from vrm_state_common import (  # noqa: E402
    VRM_STATE_CROP_PIPELINE,
    crop_vrm_state_slot,
)
from vrm_seating_common import (  # noqa: E402
    VRM_SEATING_CROP_PIPELINE,
    crop_vrm_seating_slot,
)
from component_presence_common import (  # noqa: E402
    PRESENCE_CROP_PIPELINE,
    crop_component_presence_slot,
)


TYPE_DIRS = {
    "GPU": "gpu",
    "HBM": "hbm",
    "Power Module": "power_module",
    "VRM": "vrm",
    "Inductor": "inductor",
    "SMD Capacitor": "smd_capacitor",
}
CANONICAL_SIZE = (1600, 1266)


def _probability(value: Any) -> float:
    value = float(value)
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("Probability must be finite and within [0, 1]")
    return value


def _classifier_probabilities(logits: Any, class_count: int) -> np.ndarray:
    import torch

    # A different batch/class axis cannot be treated as the expected model.
    if (not isinstance(logits, torch.Tensor) or tuple(logits.shape) != (1, class_count)
            or not bool(torch.isfinite(logits).all())):
        raise ValueError("Classifier logits have invalid shape or nonfinite data")
    probabilities = torch.softmax(logits, dim=1)[0].cpu().numpy()
    if not np.isfinite(probabilities).all():
        raise ValueError("Classifier returned nonfinite probabilities")
    return probabilities


@dataclass
class RegisteredBoard:
    image_bgr: np.ndarray
    source_homography: np.ndarray
    alignment_warp: np.ndarray
    alignment_score: float
    alignment_reason: str
    input_was_canonical: bool


@dataclass
class FixedSlot:
    slot_id: str
    component_type: str
    component_key: str
    geometry: tuple[float, float, float, float]
    expected_axis_angle_deg: float
    crop_bgr: np.ndarray
    crop_origin_px: tuple[int, int]
    crop_size_px: tuple[int, int]


@dataclass
class PresenceEvidence:
    slot_id: str
    predicted_state: str
    status: str
    confidence: float
    authority: str
    reason: str
    model_path: str | None


@dataclass
class VrmStateEvidence:
    slot_id: str
    predicted_state: str
    confidence: float
    authority: str
    reason: str
    model_path: str | None
    minimum_confidence: float
    raw_predicted_state: str = "UNKNOWN"
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass
class VrmSeatingEvidence:
    slot_id: str
    predicted_state: str
    status: str
    confidence: float
    authority: str
    reason: str
    model_path: str | None
    flat_max_seating_probability: float
    seating_min_probability: float
    raw_predicted_state: str = "UNKNOWN"
    probabilities: dict[str, float] = field(default_factory=dict)


def _bounded_crop(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    margin_ratio: float,
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    center_x, center_y, size_x, size_y = geometry
    width = max(16, int(round(size_x * (1.0 + 2.0 * margin_ratio))))
    height = max(16, int(round(size_y * (1.0 + 2.0 * margin_ratio))))
    x0 = max(0, int(round(center_x - width * 0.5)))
    y0 = max(0, int(round(center_y - height * 0.5)))
    x1 = min(image.shape[1], x0 + width)
    y1 = min(image.shape[0], y0 + height)
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise RuntimeError(f"Fixed slot crop is outside the board: {geometry}")
    return image[y0:y1, x0:x1].copy(), (x0, y0), (x1 - x0, y1 - y0)


class FixedSlotCropper:
    """Rectify one board and force extraction of every configured slot."""

    def __init__(self, config_path: Path):
        self.config_path = config_path.expanduser().resolve()
        self.config = _load_json(self.config_path)
        self.reference = _load_image(_project_path(self.config["reference_image"]))
        self.layout = _load_json(_project_path(self.config["board_layout"]))
        physical = _load_json(_project_path(self.config["physical_board"]))
        self.layout, self.override_slots = apply_component_slot_overrides(
            self.layout, physical
        )
        board = self.layout["board"]["size_mm"]
        self.board_size_mm = (float(board["x"]), float(board["y"]))
        self.socket_clearance = _load_json(
            PROJECT_DIR / "vision_assembly/config/unity_socket_clearance.json"
        )

    def static_board_mask(self) -> np.ndarray:
        return board_alignment_mask(
            self.layout, self.reference.shape, self.board_size_mm,
            self.config['coordinate_mapping'],
            float(self.config['global_alignment'].get('component_exclusion_margin_mm', 2.5)),
        )

    def register(self, image_bgr: np.ndarray) -> RegisteredBoard:
        if image_bgr is None or image_bgr.size == 0:
            raise ValueError("Input image is empty")
        output_width, output_height = CANONICAL_SIZE
        input_was_canonical = image_bgr.shape[:2] == (output_height, output_width)
        if input_was_canonical:
            rectified = image_bgr.copy()
            source_h = np.eye(3, dtype=np.float32)
        else:
            expected_aspect = max(self.board_size_mm) / min(self.board_size_mm)
            _, _, detection = detect_board(image_bgr, expected_aspect)
            source = operator_source_corners(detection.points)
            destination = np.asarray(
                (
                    (0.0, 0.0),
                    (output_width - 1.0, 0.0),
                    (output_width - 1.0, output_height - 1.0),
                    (0.0, output_height - 1.0),
                ),
                np.float32,
            )
            source_h = cv2.getPerspectiveTransform(source, destination)
            rectified = cv2.warpPerspective(
                image_bgr,
                source_h,
                CANONICAL_SIZE,
                flags=cv2.INTER_LANCZOS4,
                borderMode=cv2.BORDER_REPLICATE,
            )

        mask = self.static_board_mask()
        aligned, score, warp, reason = align_board(
            self.reference,
            rectified,
            self.config["global_alignment"],
            mask,
        )
        return RegisteredBoard(
            image_bgr=aligned,
            source_homography=source_h,
            alignment_warp=warp,
            alignment_score=float(score),
            alignment_reason=str(reason),
            input_was_canonical=input_was_canonical,
        )

    def fixed_slots(
        self, aligned_bgr: np.ndarray, margin_ratio: float = 0.22
    ) -> list[FixedSlot]:
        slots: list[FixedSlot] = []
        for placement in self.layout["placements"]:
            component_type = str(placement["component_type"])
            if component_type not in TYPE_DIRS:
                raise RuntimeError(f"Unsupported component type: {component_type}")
            geometry = slot_geometry(
                placement,
                aligned_bgr.shape,
                self.board_size_mm,
                self.config["coordinate_mapping"],
            )
            crop, origin, crop_size = _bounded_crop(
                aligned_bgr, geometry, margin_ratio
            )
            slots.append(
                FixedSlot(
                    slot_id=str(placement["slot_id"]),
                    component_type=component_type,
                    component_key=TYPE_DIRS[component_type],
                    geometry=geometry,
                    expected_axis_angle_deg=float(
                        placement.get("long_axis_deg_in_board", 0.0)
                    )
                    % 180.0,
                    crop_bgr=crop,
                    crop_origin_px=origin,
                    crop_size_px=crop_size,
                )
            )
        if len(slots) != 25:
            raise RuntimeError(f"Inspection contract requires 25 slots, got {len(slots)}")
        if len({slot.slot_id for slot in slots}) != 25:
            raise RuntimeError("Inspection contract requires 25 unique slot IDs")
        return slots


class SlotPresenceClassifier:
    """Load one optional TorchScript PRESENT/EMPTY model per component type.

    A missing model or missing validation metadata is fail-safe UNKNOWN.  Model
    output class order must be [EMPTY, PRESENT].
    """

    def __init__(self, model_root: Path, device: str = "cuda"):
        self.model_root = model_root.expanduser().resolve()
        self.device_name = device
        self._models: dict[str, Any] = {}

    def _load(self, component_key: str):
        if component_key in self._models:
            return self._models[component_key]
        candidate_root = self.model_root / "component_presence_candidate"
        model_path = candidate_root / f"{component_key}_presence.torchscript.pt"
        metadata_path = candidate_root / f"{component_key}_presence.json"
        if not model_path.is_file() or not metadata_path.is_file():
            self._models[component_key] = (None, None, model_path)
            return self._models[component_key]
        import torch

        device = self.device_name if torch.cuda.is_available() else "cpu"
        model = torch.jit.load(str(model_path), map_location=device).eval()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self._models[component_key] = (model, metadata, model_path)
        return self._models[component_key]

    def inspect(self, slot: FixedSlot, registered_board_bgr: np.ndarray) -> PresenceEvidence:
        try:
            return self._inspect(slot, registered_board_bgr)
        except Exception as error:
            return PresenceEvidence(
                slot.slot_id, "UNKNOWN", "UNKNOWN", 0.0, "UNAVAILABLE",
                f"PRESENCE_PROVIDER_ERROR:{type(error).__name__}",
                str(self.model_root / "component_presence_candidate" / f"{slot.component_key}_presence.torchscript.pt"),
            )

    def _inspect(self, slot: FixedSlot, registered_board_bgr: np.ndarray) -> PresenceEvidence:
        model, metadata, model_path = self._load(slot.component_key)
        if model is None or metadata is None:
            return PresenceEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "UNAVAILABLE",
                "PRESENCE_MODEL_OR_VALIDATION_METADATA_MISSING",
                str(model_path),
            )
        import torch

        if metadata.get("crop_pipeline") != PRESENCE_CROP_PIPELINE:
            return PresenceEvidence(
                slot.slot_id, "UNKNOWN", "UNKNOWN", 0.0, "UNAVAILABLE",
                "PRESENCE_CROP_PIPELINE_MISMATCH", str(model_path),
            )
        if tuple(metadata.get("classes", ())) != ("EMPTY", "PRESENT"):
            return PresenceEvidence(
                slot.slot_id, "UNKNOWN", "UNKNOWN", 0.0, "INVALID",
                "PRESENCE_CLASS_ORDER_INVALID", str(model_path),
            )
        minimum = _probability(metadata.get("minimum_confidence", 0.80))

        device = next(model.parameters()).device
        presence_crop = crop_component_presence_slot(
            registered_board_bgr, slot.geometry, slot.component_key
        )
        rgb = cv2.cvtColor(presence_crop, cv2.COLOR_BGR2RGB)
        size = int(metadata.get("input_size", 224))
        rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
        mean = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
        std = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
        tensor = ((tensor - mean) / std).unsqueeze(0).to(device)
        with torch.inference_mode():
            probabilities = _classifier_probabilities(model(tensor), 2)
        index = int(np.argmax(probabilities))
        predicted = ("EMPTY", "PRESENT")[index]
        confidence = float(probabilities[index])
        authority = (
            "AUTHORITATIVE" if metadata.get("validated") is True
            and metadata.get("authority") == "AUTHORITATIVE" else "ADVISORY_ONLY"
        )
        status = "UNKNOWN"
        reason = "LOW_CONFIDENCE"
        if confidence >= minimum:
            if authority == "AUTHORITATIVE":
                status = "PASS" if predicted == "PRESENT" else "FAIL"
                reason = f"CALIBRATED_{predicted}"
            else:
                reason = f"UNVERIFIED_{predicted}_CANDIDATE"
        return PresenceEvidence(
            slot.slot_id,
            predicted,
            status,
            confidence,
            authority,
            reason,
            str(model_path),
        )


class VrmStateClassifier:
    """Optional S22 EMPTY/CORRECT/ROTATED fixed-slot classifier."""

    def __init__(self, model_root: Path, device: str = "cuda"):
        self.model_root = model_root.expanduser().resolve()
        self.device_name = device
        self.model = None
        self.metadata = None
        self.model_path = self.model_root / "vrm_state.torchscript.pt"

    def _load(self) -> None:
        if self.metadata is not None:
            return
        metadata_path = self.model_root / "vrm_state.json"
        if not self.model_path.is_file() or not metadata_path.is_file():
            self.metadata = {}
            return
        import torch

        device = self.device_name if torch.cuda.is_available() else "cpu"
        self.model = torch.jit.load(str(self.model_path), map_location=device).eval()
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    def inspect(
        self, slot: FixedSlot, registered_board_bgr: np.ndarray | None = None
    ) -> VrmStateEvidence:
        try:
            return self._inspect(slot, registered_board_bgr)
        except Exception as error:
            if not isinstance(self.metadata, dict):
                self.metadata = {}
            return VrmStateEvidence(
                slot.slot_id, "UNKNOWN", 0.0, "UNAVAILABLE",
                f"VRM_STATE_PROVIDER_ERROR:{type(error).__name__}", str(self.model_path), 1.0,
            )

    def _inspect(
        self, slot: FixedSlot, registered_board_bgr: np.ndarray | None = None
    ) -> VrmStateEvidence:
        self._load()
        if self.model is None or not self.metadata:
            return VrmStateEvidence(
                slot.slot_id,
                "UNKNOWN",
                0.0,
                "UNAVAILABLE",
                "VRM_STATE_MODEL_OR_METADATA_MISSING",
                str(self.model_path),
                1.0,
            )
        import torch

        classes = tuple(self.metadata.get("class_order", ()))
        if classes != ("EMPTY", "CORRECT", "ROTATED"):
            return VrmStateEvidence(
                slot.slot_id,
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_STATE_CLASS_ORDER_INVALID",
                str(self.model_path),
                1.0,
            )
        crop_pipeline = str(self.metadata.get("crop_pipeline", ""))
        if crop_pipeline != VRM_STATE_CROP_PIPELINE:
            return VrmStateEvidence(
                slot.slot_id,
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_STATE_CROP_PIPELINE_MISMATCH",
                str(self.model_path),
                1.0,
            )
        minimum = _probability(self.metadata.get("minimum_confidence", 0.80))
        device = next(self.model.parameters()).device
        if registered_board_bgr is None:
            return VrmStateEvidence(
                slot.slot_id,
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_STATE_REGISTERED_BOARD_MISSING",
                str(self.model_path),
                1.0,
            )
        state_crop = crop_vrm_state_slot(registered_board_bgr, slot.geometry)
        rgb = cv2.cvtColor(state_crop, cv2.COLOR_BGR2RGB)
        size = int(self.metadata.get("input_size", 224))
        rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
        mean = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
        std = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
        tensor = ((tensor - mean) / std).unsqueeze(0).to(device)
        with torch.inference_mode():
            probabilities = _classifier_probabilities(self.model(tensor), 3)
        index = int(np.argmax(probabilities))
        confidence = float(probabilities[index])
        validated = self.metadata.get("validated") is True
        requested_authority = str(self.metadata.get("authority", "ADVISORY_ONLY"))
        authority = (
            "AUTHORITATIVE"
            if validated and requested_authority == "AUTHORITATIVE"
            else "ADVISORY_ONLY"
        )
        raw_predicted = classes[index]
        predicted = raw_predicted if confidence >= minimum else "UNKNOWN"
        reason = (
            f"VRM_STATE_{predicted}"
            if predicted != "UNKNOWN"
            else f"VRM_STATE_LOW_CONFIDENCE:{raw_predicted}"
        )
        return VrmStateEvidence(
            slot.slot_id,
            predicted,
            confidence,
            authority,
            reason,
            str(self.model_path),
            minimum,
            raw_predicted,
            {
                class_name: float(probability)
                for class_name, probability in zip(classes, probabilities)
            },
        )


class VrmSeatingClassifier:
    """Optional S22 fixed-slot FLAT/SEATING classifier.

    This provider is independent from EMPTY/CORRECT/ROTATED.  It only runs
    after the state model supplies strong non-empty evidence.  Metadata cannot
    grant authority unless both ``validated`` and ``AUTHORITATIVE`` are set;
    the current physical dataset deliberately leaves it ADVISORY_ONLY.
    """

    def __init__(self, model_root: Path, device: str = "cuda"):
        self.model_root = model_root.expanduser().resolve()
        self.device_name = device
        self.candidate_root = self.model_root / "vrm_seating_candidate"
        self.model_path = self.candidate_root / "vrm_seating.torchscript.pt"
        self.metadata_path = self.candidate_root / "vrm_seating.json"
        self.model = None
        self.metadata: dict[str, Any] | None = None

    def _load(self) -> None:
        if self.metadata is not None:
            return
        if not self.model_path.is_file() or not self.metadata_path.is_file():
            self.metadata = {}
            return
        self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        # Candidate artifacts are never activated merely by being present on
        # disk.  Promotion requires an explicit metadata switch after the
        # cross-scene regression set passes.
        if self.metadata.get("runtime_enabled") is not True:
            return
        import torch

        device = self.device_name if torch.cuda.is_available() else "cpu"
        self.model = torch.jit.load(str(self.model_path), map_location=device).eval()

    def inspect(
        self,
        slot: FixedSlot,
        registered_board_bgr: np.ndarray | None,
        *,
        non_empty_confidence: float,
        minimum_non_empty_confidence: float = 0.90,
    ) -> VrmSeatingEvidence:
        try:
            return self._inspect(
                slot, registered_board_bgr, non_empty_confidence=non_empty_confidence,
                minimum_non_empty_confidence=minimum_non_empty_confidence,
            )
        except Exception as error:
            if not isinstance(self.metadata, dict):
                self.metadata = {}
            return VrmSeatingEvidence(
                slot.slot_id, "UNKNOWN", "UNKNOWN", 0.0, "UNAVAILABLE",
                f"VRM_SEATING_PROVIDER_ERROR:{type(error).__name__}", str(self.model_path), 0.0, 1.0,
            )

    def _inspect(
        self, slot: FixedSlot, registered_board_bgr: np.ndarray | None, *,
        non_empty_confidence: float, minimum_non_empty_confidence: float = 0.90,
    ) -> VrmSeatingEvidence:
        self._load()
        if self.model is None or not self.metadata:
            disabled = bool(self.metadata) and self.metadata.get("runtime_enabled") is not True
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "DISABLED" if disabled else "UNAVAILABLE",
                (
                    "VRM_SEATING_CANDIDATE_NOT_RUNTIME_ENABLED"
                    if disabled
                    else "VRM_SEATING_MODEL_OR_METADATA_MISSING"
                ),
                str(self.model_path),
                0.0,
                1.0,
            )
        if slot.component_type != "VRM":
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_SEATING_PROVIDER_RECEIVED_NON_VRM_SLOT",
                str(self.model_path),
                0.0,
                1.0,
            )
        classes = tuple(self.metadata.get("class_order", ()))
        flat_max = _probability(self.metadata.get("flat_max_seating_probability", 0.0))
        seating_min = _probability(self.metadata.get("seating_min_probability", 1.0))
        if classes != ("FLAT", "SEATING") or not 0.0 <= flat_max < seating_min <= 1.0:
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_SEATING_METADATA_INVALID",
                str(self.model_path),
                flat_max,
                seating_min,
            )
        if self.metadata.get("crop_pipeline") != VRM_SEATING_CROP_PIPELINE:
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_SEATING_CROP_PIPELINE_MISMATCH",
                str(self.model_path),
                flat_max,
                seating_min,
            )
        if registered_board_bgr is None:
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                0.0,
                "INVALID",
                "VRM_SEATING_REGISTERED_BOARD_MISSING",
                str(self.model_path),
                flat_max,
                seating_min,
            )
        non_empty_confidence = _probability(non_empty_confidence)
        minimum_non_empty_confidence = _probability(minimum_non_empty_confidence)
        if non_empty_confidence < minimum_non_empty_confidence:
            return VrmSeatingEvidence(
                slot.slot_id,
                "UNKNOWN",
                "UNKNOWN",
                float(non_empty_confidence),
                "ADVISORY_ONLY",
                "VRM_SEATING_REQUIRES_CONFIRMED_NON_EMPTY_SLOT",
                str(self.model_path),
                flat_max,
                seating_min,
            )

        import torch

        device = next(self.model.parameters()).device
        crop = crop_vrm_seating_slot(registered_board_bgr, slot.geometry)
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        size = int(self.metadata.get("input_size", 224))
        # Match training's PIL Resize (bilinear with antialiasing) exactly.
        from PIL import Image

        rgb = np.array(
            Image.fromarray(rgb).resize((size, size), Image.Resampling.BILINEAR),
            copy=True,
        )
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
        mean = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
        std = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
        tensor = ((tensor - mean) / std).unsqueeze(0).to(device)
        with torch.inference_mode():
            probabilities = _classifier_probabilities(self.model(tensor), 2)
        seating_probability = float(probabilities[1])
        raw_predicted = classes[int(np.argmax(probabilities))]
        if seating_probability >= seating_min:
            predicted, status, reason = "SEATING", "FAIL", "VRM_SEATING_DETECTED"
            confidence = seating_probability
        elif seating_probability <= flat_max:
            predicted, status, reason = "FLAT", "PASS", "VRM_FLAT_SEATING_CONFIRMED"
            confidence = 1.0 - seating_probability
        else:
            predicted, status, reason = "UNKNOWN", "UNKNOWN", "VRM_SEATING_AMBIGUOUS"
            confidence = max(seating_probability, 1.0 - seating_probability)
        validated = self.metadata.get("validated") is True
        requested_authority = str(self.metadata.get("authority", "ADVISORY_ONLY"))
        authority = (
            "AUTHORITATIVE"
            if validated and requested_authority == "AUTHORITATIVE"
            else "ADVISORY_ONLY"
        )
        return VrmSeatingEvidence(
            slot.slot_id,
            predicted,
            status,
            confidence,
            authority,
            reason,
            str(self.model_path),
            flat_max,
            seating_min,
            raw_predicted,
            {
                class_name: float(probability)
                for class_name, probability in zip(classes, probabilities)
            },
        )


class YoloSegAuxiliary:
    """Run the existing S22 segmentation model in its own YOLO environment."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.last_status = "NOT_RUN"
        self.last_reason = ""
        self.python = PROJECT_DIR / "vision_assembly/.venv_obb/bin/python"
        self.script = (
            PROJECT_DIR / "vision_assembly/segmentation/predict_s22_parts_seg.py"
        )
        self.weights = (
            PROJECT_DIR
            / "vision_assembly/segmentation/models/s22_parts_seg_candidate.pt"
        )

    def inspect(self, image_path: Path, output_dir: Path) -> dict[str, dict[str, Any]]:
        if not self.enabled:
            self.last_status = "DISABLED"
            self.last_reason = "YOLO_AUXILIARY_DISABLED"
            return {}
        if not self.python.is_file() or not self.weights.is_file():
            self.last_status = "UNAVAILABLE"
            self.last_reason = "YOLO_ENVIRONMENT_OR_WEIGHTS_MISSING"
            return {}
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python),
            str(self.script),
            "--image",
            str(image_path),
            "--weights",
            str(self.weights),
            "--output",
            str(output_dir),
        ]
        try:
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = str(output_dir / ".matplotlib")
            subprocess.run(
                command,
                cwd=PROJECT_DIR,
                check=True,
                text=True,
                capture_output=True,
                timeout=120,
                env=environment,
            )
        except subprocess.CalledProcessError as error:
            self.last_status = "UNAVAILABLE"
            stderr = (error.stderr or "").strip().splitlines()
            self.last_reason = stderr[-1] if stderr else "YOLO_SUBPROCESS_FAILED"
            return {}
        except (subprocess.SubprocessError, OSError) as error:
            self.last_status = "UNAVAILABLE"
            self.last_reason = f"YOLO_PROVIDER_ERROR:{type(error).__name__}"
            return {}
        report_path = output_dir / "s22_parts_seg_latest.json"
        if not report_path.is_file():
            self.last_status = "UNAVAILABLE"
            self.last_reason = "YOLO_REPORT_MISSING"
            return {}
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            detections = report["detections"]
            if not isinstance(detections, list) or any(not isinstance(item, dict) for item in detections):
                raise ValueError("YOLO detections must be a list of objects")
            items = {}
            for item in detections:
                slot_id = item.get("slot_id")
                if slot_id is None:
                    continue
                if not isinstance(slot_id, str) or not slot_id or slot_id in items:
                    raise ValueError("YOLO slot IDs must be unique nonempty strings")
                items[slot_id] = item
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.last_status = "UNAVAILABLE"
            self.last_reason = f"YOLO_REPORT_INVALID:{type(error).__name__}"
            return {}
        self.last_status = "ADVISORY_ONLY"
        self.last_reason = "YOLO_AUXILIARY_REPORT_AVAILABLE"
        return items
