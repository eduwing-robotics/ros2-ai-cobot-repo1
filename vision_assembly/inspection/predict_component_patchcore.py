#!/usr/bin/env python3
"""Run the six component PatchCore candidates on one aligned board image."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from build_component_patchcore_dataset import OUTPUT_SIZE, TYPE_DIRS, _crop_slot
from full_board_inspector import (
    _load_image,
    _load_json,
    _project_path,
    align_board,
    board_alignment_mask,
    slot_geometry,
)
from layout_overrides import apply_component_slot_overrides
from train_pcb_patchcore import _items, json_safe


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
DEFAULT_MODELS = PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_smd_v3"
DEFAULT_OUTPUT = PROJECT_DIR / "runtime/inspection/patchcore/component_live_v3"
DIR_TYPES = {directory: component_type for component_type, directory in TYPE_DIRS.items()}


def _checkpoint(model_root: Path, component: str) -> Path:
    candidates = sorted(
        (model_root / component).glob(
            "Patchcore/*/v*/weights/lightning/model.ckpt"
        )
    )
    if not candidates:
        raise FileNotFoundError(f"No checkpoint for {component}")
    return candidates[-1]


def _predict_outputs(component: str, crop_dir: Path, checkpoint: Path, output: Path):
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    width, height = OUTPUT_SIZE[DIR_TYPES[component]]
    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=("layer2", "layer3"),
        # Inference restores the complete trained checkpoint below.  Asking
        # timm for ImageNet weights here performs an unnecessary network HEAD
        # request and can stall an offline production cell.
        pre_trained=False,
        coreset_sampling_ratio=0.1,
        num_neighbors=9,
        pre_processor=Patchcore.configure_pre_processor(image_size=(height, width)),
        visualizer=False,
    )
    engine = Engine(
        accelerator="gpu", devices=1, default_root_dir=output,
        logger=False, enable_model_summary=False,
    )
    predictions = engine.predict(
        model=model, ckpt_path=checkpoint, data_path=crop_dir,
        return_predictions=True,
    )
    outputs: dict[str, dict[str, object]] = {}
    for batch in predictions or []:
        paths = getattr(batch, "image_path", None)
        paths = list(paths) if isinstance(paths, (list, tuple)) else [paths]
        values = _items(getattr(batch, "pred_score", float("nan")), len(paths))
        maps = _items(getattr(batch, "anomaly_map", None), len(paths))
        for path, value, anomaly in zip(paths, values, maps):
            slot_id = Path(str(path)).stem
            anomaly_map = None
            if anomaly is not None:
                anomaly_map = np.asarray(json_safe(anomaly), dtype=np.float32).squeeze()
                if anomaly_map.ndim != 2:
                    raise RuntimeError(
                        f"Unexpected anomaly map shape for {slot_id}: {anomaly_map.shape}"
                    )
            outputs[slot_id] = {
                "score": float(json_safe(value)), "anomaly_map": anomaly_map,
            }
    return outputs


def _restore_slot_map(anomaly_map, source_crop_size, rotated_to_horizontal):
    """Undo crop normalization so a model map fits its original board slot."""
    crop_width, crop_height = source_crop_size
    if rotated_to_horizontal:
        restored = cv2.resize(
            anomaly_map, (crop_height, crop_width), interpolation=cv2.INTER_LINEAR
        )
        return cv2.rotate(restored, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.resize(
        anomaly_map, (crop_width, crop_height), interpolation=cv2.INTER_LINEAR
    )


def _paste_max(destination, coverage, slot_map, center):
    """Paste a slot map with clipping and max fusion for overlapping margins."""
    height, width = slot_map.shape
    x0, y0 = int(round(center[0] - width / 2)), int(round(center[1] - height / 2))
    x1, y1 = x0 + width, y0 + height
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(destination.shape[1], x1), min(destination.shape[0], y1)
    if dx0 >= dx1 or dy0 >= dy1:
        return
    sx0, sy0 = dx0 - x0, dy0 - y0
    sx1, sy1 = sx0 + dx1 - dx0, sy0 + dy1 - dy0
    destination[dy0:dy1, dx0:dx1] = np.maximum(
        destination[dy0:dy1, dx0:dx1], slot_map[sy0:sy1, sx0:sx1]
    )
    coverage[dy0:dy1, dx0:dx1] = 255


def _trim_map_to_slot(slot_map, slot_size):
    """Remove the 22% context margin used by the PatchCore training crop."""
    slot_width = min(slot_map.shape[1], max(1, int(round(slot_size[0]))))
    slot_height = min(slot_map.shape[0], max(1, int(round(slot_size[1]))))
    x0 = max(0, (slot_map.shape[1] - slot_width) // 2)
    y0 = max(0, (slot_map.shape[0] - slot_height) // 2)
    return slot_map[y0:y0 + slot_height, x0:x0 + slot_width]


def _normalize_component_maps(items):
    """Normalize only maps from the same model; scales differ by component."""
    values = np.concatenate([item[1].ravel() for item in items])
    low, high = np.percentile(values, (2.0, 99.5))
    if high <= low:
        return [(slot_id, np.zeros_like(slot_map)) for slot_id, slot_map in items]
    return [
        (slot_id, np.clip((slot_map - low) / (high - low), 0.0, 1.0))
        for slot_id, slot_map in items
    ]


def _fixed_excess_map(slot_map, normal_pixel_p999: float):
    """Show only response above a held-out-normal absolute pixel baseline."""
    normal_limit = max(float(normal_pixel_p999), 0.01)
    display_span = max(normal_limit * 0.75, 0.04)
    return np.clip((np.asarray(slot_map, np.float32) - normal_limit) / display_span, 0.0, 1.0)


def _heatmap_images(aligned, anomaly, coverage):
    """Render a component-only heatmap without darkening uncovered board areas."""
    anomaly_u8 = np.clip(anomaly * 255.0, 0, 255).astype(np.uint8)
    color = cv2.applyColorMap(anomaly_u8, cv2.COLORMAP_TURBO)
    grayscale = cv2.cvtColor(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    heatmap = cv2.addWeighted(grayscale, 0.28, np.zeros_like(grayscale), 0.72, 0.0)
    heatmap[coverage > 0] = color[coverage > 0]
    overlay = aligned.copy()
    blended = cv2.addWeighted(aligned, 0.58, color, 0.42, 0.0)
    overlay[coverage > 0] = blended[coverage > 0]
    return heatmap, overlay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--component", choices=("all",) + tuple(sorted(DIR_TYPES)), default="all",
        help="Run one component model only; useful for independent validation.",
    )
    parser.add_argument(
        "--normal-calibration", type=Path, default=None,
        help="Held-out normal calibration JSON; defaults to MODELS/normal_calibration.json",
    )
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; component PatchCore requires the GPU")
    torch.set_float32_matmul_precision("high")

    config = _load_json(args.config.expanduser().resolve())
    reference = _load_image(_project_path(config["reference_image"]))
    sample = _load_image(args.image.expanduser().resolve())
    layout = _load_json(_project_path(config["board_layout"]))
    physical = _load_json(_project_path(config["physical_board"]))
    layout, overrides = apply_component_slot_overrides(layout, physical)
    board = layout["board"]["size_mm"]
    board_size = (float(board["x"]), float(board["y"]))
    mask = board_alignment_mask(
        layout, reference.shape, board_size, config["coordinate_mapping"],
        float(config["global_alignment"].get("component_exclusion_margin_mm", 2.5)),
    )
    aligned, alignment_score, _, alignment_reason = align_board(
        reference, sample, config["global_alignment"], mask
    )

    output = args.output.expanduser().resolve()
    calibration_path = (
        args.normal_calibration.expanduser().resolve()
        if args.normal_calibration else args.models.expanduser().resolve() / "normal_calibration.json"
    )
    if not calibration_path.is_file():
        raise RuntimeError(f"Fixed heatmap calibration is missing: {calibration_path}")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    run_dir = output / datetime.now().strftime("%Y%m%d_%H%M%S")
    crop_root = run_dir / "crops"
    placements_by_component: dict[str, list[dict]] = {}
    geometry_by_slot: dict[str, tuple[float, float, float, float]] = {}
    crop_meta_by_slot: dict[str, dict[str, object]] = {}
    for placement in layout["placements"]:
        component_type = str(placement["component_type"])
        if component_type not in TYPE_DIRS:
            continue
        component = TYPE_DIRS[component_type]
        if args.component != "all" and component != args.component:
            continue
        geometry = slot_geometry(
            placement, aligned.shape, board_size, config["coordinate_mapping"]
        )
        crop, rotated, source_crop_size = _crop_slot(
            aligned, geometry, 0.22, OUTPUT_SIZE[component_type]
        )
        destination = crop_root / component / f"{placement['slot_id']}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2])
        placements_by_component.setdefault(component, []).append(placement)
        geometry_by_slot[str(placement["slot_id"])] = geometry
        crop_meta_by_slot[str(placement["slot_id"])] = {
            "rotated": rotated, "source_crop_size": source_crop_size,
        }

    results = []
    board_anomaly = np.zeros(aligned.shape[:2], dtype=np.float32)
    board_coverage = np.zeros(aligned.shape[:2], dtype=np.uint8)
    restored_maps_by_component: dict[str, list[tuple[str, np.ndarray]]] = {}
    for component, placements in placements_by_component.items():
        predictions = _predict_outputs(
            component, crop_root / component,
            _checkpoint(args.models.expanduser().resolve(), component), run_dir / component,
        )
        for placement in placements:
            slot_id = str(placement["slot_id"])
            prediction = predictions[slot_id]
            anomaly_map = prediction["anomaly_map"]
            if anomaly_map is not None:
                metadata = crop_meta_by_slot[slot_id]
                restored = _restore_slot_map(
                    anomaly_map, metadata["source_crop_size"], metadata["rotated"]
                )
                geometry = geometry_by_slot[slot_id]
                restored_maps_by_component.setdefault(component, []).append(
                    (slot_id, _trim_map_to_slot(restored, (geometry[2], geometry[3])))
                )
            results.append({
                "slot_id": slot_id,
                "component_type": placement["component_type"],
                "anomaly_score": prediction["score"],
                "verdict": "UNVERIFIED_SCORE_ONLY",
            })

    for component, component_maps in restored_maps_by_component.items():
        component_calibration = calibration.get("components", {}).get(component, {})
        normal_pixel_p999 = (
            component_calibration.get("pixel", {}).get("percentiles", {}).get("99.9")
        )
        if normal_pixel_p999 is None:
            raise RuntimeError(f"Missing normal pixel p99.9 for {component}")
        for slot_id, slot_map in component_maps:
            normalized_map = _fixed_excess_map(slot_map, float(normal_pixel_p999))
            geometry = geometry_by_slot[slot_id]
            _paste_max(
                board_anomaly, board_coverage, normalized_map,
                (geometry[0], geometry[1]),
            )

    canvas = aligned.copy()
    for item in results:
        cx, cy, sx, sy = geometry_by_slot[item["slot_id"]]
        x0, y0 = int(round(cx - sx / 2)), int(round(cy - sy / 2))
        x1, y1 = int(round(cx + sx / 2)), int(round(cy + sy / 2))
        component = TYPE_DIRS[item["component_type"]]
        normal_p99 = float(
            calibration["components"][component]["score"]["percentiles"]["99.0"]
        )
        color = (255, 190, 40) if item["anomaly_score"] <= normal_p99 else (40, 140, 255)
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2, cv2.LINE_AA)
        cv2.putText(
            canvas, f"{item['slot_id']} {item['anomaly_score']:.3f}",
            (x0 + 2, max(14, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
            0.38, color, 1, cv2.LINE_AA,
        )
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1] - 1, 58), (17, 20, 24), -1)
    cv2.putText(
        canvas,
        f"COMPONENT PATCHCORE | SCORE ONLY | ALIGN {alignment_score:.3f}",
        (20, 39), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (80, 220, 255), 2, cv2.LINE_AA,
    )
    slots_image = run_dir / "component_patchcore_slots.png"
    cv2.imwrite(str(slots_image), canvas, [cv2.IMWRITE_PNG_COMPRESSION, 2])

    heatmap, heatmap_overlay = _heatmap_images(
        aligned, board_anomaly, board_coverage
    )
    for image, title in (
        (heatmap, "FIXED EXCESS ABOVE NORMAL P99.9 | ADVISORY"),
        (heatmap_overlay, "FIXED EXCESS OVERLAY | ADVISORY"),
    ):
        cv2.rectangle(image, (0, 0), (image.shape[1] - 1, 58), (17, 20, 24), -1)
        cv2.putText(
            image, title, (20, 39), cv2.FONT_HERSHEY_SIMPLEX,
            0.72, (80, 220, 255), 2, cv2.LINE_AA,
        )
    heatmap_path = run_dir / "component_patchcore_heatmap.png"
    heatmap_overlay_path = run_dir / "component_patchcore_heatmap_overlay.png"
    cv2.imwrite(str(heatmap_path), heatmap, [cv2.IMWRITE_PNG_COMPRESSION, 2])
    cv2.imwrite(str(heatmap_overlay_path), heatmap_overlay, [cv2.IMWRITE_PNG_COMPRESSION, 2])
    panel_path = run_dir / "component_patchcore_panel.png"
    cv2.imwrite(str(panel_path), np.hstack((aligned, heatmap, heatmap_overlay)), [cv2.IMWRITE_PNG_COMPRESSION, 2])
    report = {
        "schema_version": 1,
        "status": "UNVERIFIED_SCORE_ONLY",
        "input_image": str(args.image.expanduser().resolve()),
        "alignment": {"reason": alignment_reason, "score": alignment_score},
        "smd_excluded": False,
        "physical_override_slots": overrides,
        "visualization": {
            "mode": "fixed_per_component_excess_above_normal_pixel_p99.9",
            "normal_calibration": str(calibration_path),
            "panel": str(panel_path), "heatmap": str(heatmap_path),
            "heatmap_overlay": str(heatmap_overlay_path),
            "slot_scores": str(slots_image),
        },
        "components": results,
        "limitation": (
            "No slot-level defect labels exist yet; scores localize unusual slots "
            "but are not production PASS/FAIL thresholds."
        ),
    }
    report_path = run_dir / "component_patchcore_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for source, link_name in (
        (panel_path, "component_patchcore_latest.png"),
        (heatmap_path, "component_patchcore_heatmap_latest.png"),
        (heatmap_overlay_path, "component_patchcore_heatmap_overlay_latest.png"),
        (slots_image, "component_patchcore_slots_latest.png"),
        (report_path, "component_patchcore_latest.json"),
    ):
        link = output / link_name
        link.unlink(missing_ok=True)
        link.symlink_to(source.resolve())
    print(f"COMPONENT_PATCHCORE_PANEL={panel_path}")
    print(f"COMPONENT_PATCHCORE_HEATMAP={heatmap_path}")
    print(f"COMPONENT_PATCHCORE_OVERLAY={heatmap_overlay_path}")
    print(f"COMPONENT_PATCHCORE_SLOTS={slots_image}")
    print(f"COMPONENT_PATCHCORE_REPORT={report_path}")
    print("COMPONENT_PATCHCORE_VERDICT=UNVERIFIED_SCORE_ONLY")


if __name__ == "__main__":
    main()
