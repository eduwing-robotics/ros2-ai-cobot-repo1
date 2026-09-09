#!/usr/bin/env python3
"""Interactive polygon labeler for six S22 PCB component classes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from common import (
    CLASS_COLORS,
    CLASS_NAMES,
    NORMAL_CLASS_COUNTS,
    class_counts,
    load_yolo_segments,
    polygon_area,
    save_yolo_segments,
)


WINDOW = "S22 Parts Segmentation Labeler"
PANEL_WIDTH = 430
MIN_DRAG_PX = 8
CLASS_PANEL_TOP = 188
CLASS_PANEL_ROW_HEIGHT = 27


def parse_args() -> argparse.Namespace:
    source = Path(__file__).resolve().parent / "s22_source"
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=source / "images")
    parser.add_argument("--metadata", type=Path, default=source / "metadata")
    parser.add_argument("--labels", type=Path, default=source / "labels")
    parser.add_argument("--reviews", type=Path, default=source / "reviews")
    parser.add_argument("--default-class", choices=CLASS_NAMES, default="gpu")
    parser.add_argument("--match", default="*")
    parser.add_argument("--relabel", action="store_true")
    parser.add_argument(
        "--sam-model",
        type=Path,
        default=Path(__file__).resolve().parent / "models" / "sam2.1_t.pt",
    )
    parser.add_argument("--sam-device", default="auto")
    parser.add_argument("--no-sam", action="store_true")
    return parser.parse_args()


def metadata_for(image: Path, metadata_dir: Path) -> dict:
    path = metadata_dir / f"{image.stem}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def put_lines(panel: np.ndarray, lines: list[str], y: int, color=(225, 225, 225)) -> int:
    for line in lines:
        cv2.putText(
            panel,
            line,
            (18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color,
            1,
            cv2.LINE_AA,
        )
        y += 27
    return y


def ordered_box(
    start: tuple[int, int],
    end: tuple[int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int] | None:
    x1, x2 = sorted((max(0, start[0]), min(width - 1, end[0])))
    y1, y2 = sorted((max(0, start[1]), min(height - 1, end[1])))
    if x2 - x1 < MIN_DRAG_PX or y2 - y1 < MIN_DRAG_PX:
        return None
    return x1, y1, x2, y2


def mask_to_prompt_polygon(
    mask: np.ndarray,
    box: tuple[int, int, int, int],
) -> np.ndarray | None:
    """Convert a prompt mask into one body polygon near the dragged box."""
    binary = (np.asarray(mask) > 0.5).astype(np.uint8)
    if binary.ndim != 2:
        return None
    height, width = binary.shape
    x1, y1, x2, y2 = box
    pad_x = max(3, int(round((x2 - x1) * 0.08)))
    pad_y = max(3, int(round((y2 - y1) * 0.08)))
    ax1, ay1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    ax2, ay2 = min(width - 1, x2 + pad_x), min(height - 1, y2 + pad_y)
    allowed = np.zeros_like(binary)
    allowed[ay1 : ay2 + 1, ax1 : ax2 + 1] = 1
    binary &= allowed
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None

    prompt_area = float(max(1, (x2 - x1 + 1) * (y2 - y1 + 1)))
    best: tuple[float, np.ndarray] | None = None
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < max(8.0, prompt_area * 0.04):
            continue
        component = np.zeros_like(binary)
        cv2.drawContours(component, [contour], -1, 1, -1)
        inside = float(component[y1 : y2 + 1, x1 : x2 + 1].sum())
        if inside < prompt_area * 0.04:
            continue
        score = inside - max(0.0, area - inside) * 0.35
        if best is None or score > best[0]:
            best = (score, contour)
    if best is None:
        return None

    contour = best[1]
    perimeter = cv2.arcLength(contour, True)
    simplified = cv2.approxPolyDP(contour, max(1.0, perimeter * 0.003), True)
    points = simplified.reshape(-1, 2).astype(np.float32)
    if len(points) < 3 or polygon_area(points) < 4.0:
        return None
    return points


def sam_box_polygon(
    sam_model,
    image: np.ndarray,
    box: tuple[int, int, int, int],
    device: str,
) -> np.ndarray | None:
    results = sam_model.predict(
        image,
        bboxes=[list(box)],
        device=device,
        verbose=False,
    )
    if not results or results[0].masks is None:
        return None
    masks = results[0].masks.data.detach().cpu().numpy()
    height, width = image.shape[:2]
    candidates = []
    for mask in masks:
        if mask.shape != (height, width):
            mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
        polygon = mask_to_prompt_polygon(mask, box)
        if polygon is not None:
            candidates.append(polygon)
    if not candidates:
        return None
    x1, y1, x2, y2 = box
    center = np.asarray(((x1 + x2) * 0.5, (y1 + y2) * 0.5), np.float32)
    return min(
        candidates,
        key=lambda points: float(np.linalg.norm(np.mean(points, axis=0) - center)),
    )


def main() -> None:
    args = parse_args()
    args.labels.mkdir(parents=True, exist_ok=True)
    args.reviews.mkdir(parents=True, exist_ok=True)
    selected = CLASS_NAMES.index(args.default_class)
    images = sorted(
        path
        for suffix in ("*.png", "*.jpg", "*.jpeg")
        for path in args.images.glob(suffix)
        if path.match(args.match) or path.name.startswith(args.match.rstrip("*"))
    )
    images = list(dict.fromkeys(images))
    if not args.relabel:
        images = [
            image
            for image in images
            if not (args.reviews / f"{image.stem}.json").is_file()
        ]
    if not images:
        raise RuntimeError(f"No images awaiting labels in {args.images}")

    sam_model = None
    sam_device = args.sam_device
    if not args.no_sam:
        if args.sam_model.is_file():
            from ultralytics import SAM
            import torch

            print(f"Loading drag-to-mask model: {args.sam_model}")
            sam_model = SAM(str(args.sam_model.resolve()))
            if sam_device == "auto":
                sam_device = "0" if torch.cuda.is_available() else "cpu"
            print(f"SAM2 device: {sam_device}")
        else:
            print(
                f"SAM model is missing: {args.sam_model}. "
                "Drag boxes are disabled; manual polygon clicks remain available."
            )

    print("Label only the physical component body; exclude sockets, shadows, GPU/HBM pins, and the white orientation dot.")
    print("0-5 class | left drag auto-mask | left click manual points | ENTER close manual polygon")
    print("C copy previous image | D delete polygon under cursor | U undo last polygon")
    print("S save complete | F force-save expected-count mismatch | Q quit")
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    index = 0
    previous_segments: list[tuple[int, np.ndarray]] | None = None
    while index < len(images):
        image_path = images[index]
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot read image: {image_path}")
        height, width = image.shape[:2]
        label_path = args.labels / f"{image_path.stem}.txt"
        review_path = args.reviews / f"{image_path.stem}.json"
        segments = load_yolo_segments(label_path, width, height)
        current: list[tuple[int, int]] = []
        meta = metadata_for(image_path, args.metadata)
        expected = meta.get("expected_visible_instances")
        expected_classes = (
            NORMAL_CLASS_COUNTS
            if meta.get("board_state") in ("normal", "print_variation")
            else None
        )
        mismatch_warning = False
        cursor = [0, 0]
        drag = {"start": None, "end": None, "pending": None}
        status_message = "Drag tightly around one component body"

        def mouse(event, x, y, flags, parameter):
            nonlocal selected, status_message
            del flags, parameter
            if x >= width:
                row = (y - CLASS_PANEL_TOP) // CLASS_PANEL_ROW_HEIGHT
                if (
                    event == cv2.EVENT_LBUTTONDOWN
                    and x < width + PANEL_WIDTH
                    and 0 <= row < len(CLASS_NAMES)
                ):
                    selected = int(row)
                    status_message = f"Selected {selected}: {CLASS_NAMES[selected]}"
                return
            cursor[:] = (x, y)
            if y >= height:
                return
            if event == cv2.EVENT_LBUTTONDOWN:
                drag["start"] = (x, y)
                drag["end"] = (x, y)
            elif event == cv2.EVENT_MOUSEMOVE and drag["start"] is not None:
                drag["end"] = (x, y)
            elif event == cv2.EVENT_LBUTTONUP and drag["start"] is not None:
                drag["end"] = (x, y)
                box = ordered_box(drag["start"], drag["end"], width, height)
                if box is None:
                    current.append((x, y))
                else:
                    drag["pending"] = box
                drag["start"] = None
                drag["end"] = None
            elif event == cv2.EVENT_RBUTTONDOWN and current:
                current.pop()

        cv2.setMouseCallback(WINDOW, mouse)
        while True:
            if drag["pending"] is not None:
                box = drag["pending"]
                drag["pending"] = None
                if sam_model is None:
                    status_message = "SAM missing: use clicks or install the model"
                else:
                    status_message = "Running SAM2 box prompt..."
                    try:
                        points = sam_box_polygon(
                            sam_model, image, box, sam_device
                        )
                    except Exception as exc:
                        print(f"SAM2 prompt failed: {exc}")
                        points = None
                        status_message = "SAM2 error: use clicks or retry"
                    if points is None:
                        status_message = "No mask: drag a tighter box or use clicks"
                    else:
                        segments.append((selected, points))
                        mismatch_warning = False
                        status_message = (
                            f"Added {CLASS_NAMES[selected]} mask ({len(points)} points)"
                        )
            canvas = image.copy()
            for class_id, points in segments:
                cv2.polylines(
                    canvas,
                    [np.rint(points).astype(np.int32)],
                    True,
                    CLASS_COLORS[class_id],
                    1,
                    cv2.LINE_AA,
                )
            if current:
                cv2.polylines(
                    canvas,
                    [np.asarray(current, np.int32)],
                    False,
                    CLASS_COLORS[selected],
                    1,
                    cv2.LINE_AA,
                )
                for point in current:
                    cv2.circle(canvas, point, 2, CLASS_COLORS[selected], 1, cv2.LINE_AA)
            if drag["start"] is not None and drag["end"] is not None:
                cv2.rectangle(
                    canvas,
                    drag["start"],
                    drag["end"],
                    CLASS_COLORS[selected],
                    1,
                    cv2.LINE_AA,
                )

            panel = np.full((height, PANEL_WIDTH, 3), 24, np.uint8)
            y = put_lines(
                panel,
                [
                    f"{index + 1}/{len(images)}",
                    image_path.name[:38],
                    f"selected {selected}: {CLASS_NAMES[selected]}",
                    f"polygons: {len(segments)}",
                    f"expected: {expected if expected is not None else 'not set'}",
                    status_message[:42],
                ],
                35,
                (245, 245, 245),
            )
            y += 12
            counts = class_counts(segments)
            for class_id, name in enumerate(CLASS_NAMES):
                expected_suffix = (
                    f"/{expected_classes[name]}" if expected_classes is not None else ""
                )
                y = put_lines(
                    panel,
                    [f"{class_id}  {name}: {counts[name]}{expected_suffix}"],
                    y,
                    CLASS_COLORS[class_id],
                )
            y += 18
            y = put_lines(
                panel,
                [
                    "DRAG   SAM2 automatic mask",
                    "CLICK  manual polygon point",
                    "PANEL  click a class name",
                    "ENTER  close polygon",
                    "C      copy previous labels",
                    "D      delete under cursor",
                    "U      undo polygon",
                    "S      save and next",
                    "F      force save mismatch",
                    "Q/ESC  quit",
                    "",
                    "BODY ONLY:",
                    "no socket / shadow / pins / dot",
                ],
                y,
                (205, 205, 205),
            )
            if mismatch_warning:
                put_lines(panel, ["COUNT MISMATCH: verify or press F"], y + 12, (80, 80, 255))
            display = np.hstack((canvas, panel))
            cv2.imshow(WINDOW, display)
            raw_key = cv2.waitKeyEx(25)
            key = raw_key & 0xFF
            if ord("0") <= key <= ord("5"):
                selected = key - ord("0")
                status_message = f"Selected {selected}: {CLASS_NAMES[selected]}"
            elif 0xFFB0 <= (raw_key & 0xFFFF) <= 0xFFB5:
                selected = (raw_key & 0xFFFF) - 0xFFB0
                status_message = f"Selected {selected}: {CLASS_NAMES[selected]}"
            elif key in (10, 13) and len(current) >= 3:
                points = np.asarray(current, np.float32)
                if polygon_area(points) >= 4.0:
                    segments.append((selected, points))
                current.clear()
                mismatch_warning = False
            elif key in (8, 127) and current:
                current.pop()
            elif key in (ord("c"), ord("C")):
                if current or segments:
                    print("Copy is allowed only before this image has polygons.")
                elif previous_segments is None:
                    print("No previous saved image is available in this session.")
                else:
                    segments = [
                        (class_id, points.copy())
                        for class_id, points in previous_segments
                    ]
                    print(f"Copied {len(segments)} polygons from the previous image.")
            elif key in (ord("d"), ord("D")) and not current and segments:
                location = (float(cursor[0]), float(cursor[1]))
                distances = [
                    cv2.pointPolygonTest(
                        np.asarray(points, np.float32), location, True
                    )
                    for _, points in segments
                ]
                selected_index = int(np.argmax(distances))
                if distances[selected_index] >= -80.0:
                    removed_class, _ = segments.pop(selected_index)
                    print(
                        f"Deleted {CLASS_NAMES[removed_class]} polygon near the cursor."
                    )
                else:
                    print("Move the cursor closer to the polygon to delete it.")
            elif key in (ord("u"), ord("U")):
                if current:
                    current.pop()
                elif segments:
                    segments.pop()
                mismatch_warning = False
            elif key in (ord("s"), ord("S"), ord("f"), ord("F")):
                if current:
                    print("Close or undo the current polygon before saving.")
                    continue
                total_mismatch = expected is not None and len(segments) != int(expected)
                class_mismatch = (
                    expected_classes is not None and counts != expected_classes
                )
                mismatch = total_mismatch or class_mismatch
                force = key in (ord("f"), ord("F"))
                if mismatch and force and meta.get("board_state") not in (
                    "controlled_defect",
                    "unknown",
                ):
                    print(
                        "Force-save is disabled for normal/print_variation metadata; "
                        "fix the labels or recapture with the correct board state."
                    )
                    continue
                if mismatch and not force:
                    mismatch_warning = True
                    print(
                        f"Expected total/classes {expected}/{expected_classes} but labelled "
                        f"{len(segments)}/{counts}. Verify labels or press F only for an "
                        "intentional metadata mismatch."
                    )
                    continue
                save_yolo_segments(label_path, segments, width, height)
                review = {
                    "schema_version": 1,
                    "status": "COMPLETE",
                    "image": str(image_path.resolve()),
                    "label": str(label_path.resolve()),
                    "reviewed_at": datetime.now().isoformat(timespec="seconds"),
                    "instance_count": len(segments),
                    "class_counts": class_counts(segments),
                    "expected_visible_instances": expected,
                    "expected_count_override": bool(mismatch and force),
                    "label_policy": "component body only; excludes socket, shadow, GPU/HBM pins and white dot",
                }
                review_path.write_text(
                    json.dumps(review, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                print(f"Saved {len(segments)} polygons: {label_path.name}")
                previous_segments = [
                    (class_id, points.copy()) for class_id, points in segments
                ]
                index += 1
                break
            elif key in (ord("q"), ord("Q"), 27):
                cv2.destroyAllWindows()
                return
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
