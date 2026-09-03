#!/usr/bin/env python3
"""Build checked SMD close-view segmentation samples without moving the robot."""
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from detect_smd_section import register_clean_section


CLASS_ID = 2


def find_smd_polygons(rectified):
    height, width = rectified.shape[:2]
    scale = width / 800.0
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] >= 35) & (hsv[:, :, 2] <= 190)).astype(np.uint8) * 255
    k1 = max(3, int(round(3 * scale)) | 1)
    k2 = max(5, int(round(5 * scale)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k1, k1), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k2, k2), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not 300.0 * scale * scale <= area <= 900.0 * scale * scale:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if x < 8 * scale or y < 8 * scale or x + w > width - 8 * scale or y + h > height - 8 * scale:
            continue
        (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
        sizes = sorted((float(rw), float(rh)))
        if sizes[0] < 14 * scale or sizes[1] > 50 * scale:
            continue
        moments = cv2.moments(contour)
        if abs(moments["m00"]) < 1e-6:
            continue
        center = np.array([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])
        epsilon = max(0.7, .002 * cv2.arcLength(contour, True))
        polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(polygon) >= 4:
            candidates.append((center, polygon, area))
    if len(candidates) != 10:
        raise RuntimeError(f"expected exactly 10 SMD label masks, got {len(candidates)}")
    by_y = sorted(candidates, key=lambda item: item[0][1])
    ordered = []
    for start in (0, 5):
        ordered.extend(sorted(by_y[start:start + 5], key=lambda item: item[0][0]))
    return ordered, mask


def write_label(path, polygons, width, height):
    rows = []
    for _, polygon, _ in polygons:
        values = []
        for x, y in polygon:
            values.extend((f"{x / width:.6f}", f"{y / height:.6f}"))
        rows.append(f"{CLASS_ID} " + " ".join(values))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def variant(image, index):
    if index == 0:
        return image
    alpha = [0.92, 0.96, 1.04, 1.08, 1.0, 1.0, 0.98][index - 1]
    beta = [-7, -3, 3, 7, 0, 0, 2][index - 1]
    output = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    if index == 5:
        output = cv2.GaussianBlur(output, (3, 3), 0.45)
    elif index == 6:
        lab = cv2.cvtColor(output, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=1.3, tileGridSize=(8, 8)).apply(l)
        output = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    elif index == 7:
        output = cv2.detailEnhance(output, sigma_s=3, sigma_r=.08)
    return output


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=root / "data/smd_section_live_frames_1920")
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--dataset", type=Path, default=root / "datasets/tray_segmentation/yolo")
    parser.add_argument("--variants", type=int, default=8)
    parser.add_argument("--session", default="smd_close_1920_01")
    args = parser.parse_args()
    if not 1 <= args.variants <= 8:
        raise ValueError("variants must be in [1,8]")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output_images = args.dataset / "images/all"
    output_labels = args.dataset / "labels/all"
    review = root / "data/smd_close_label_review"
    output_images.mkdir(parents=True, exist_ok=True)
    output_labels.mkdir(parents=True, exist_ok=True)
    if review.exists():
        shutil.rmtree(review)
    review.mkdir(parents=True)
    summary = []
    width, height = map(int, config["canonical_size"])
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    for frame_index, path in enumerate(sorted(args.frames.glob("*.jpg")), 1):
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"cannot read {path}")
        section, registration = register_clean_section(image, config, args.config)
        transform = cv2.getPerspectiveTransform(section.astype(np.float32), destination)
        rectified = cv2.warpPerspective(image, transform, (width, height), flags=cv2.INTER_CUBIC)
        polygons, _ = find_smd_polygons(rectified)
        overlay = rectified.copy()
        for number, (center, polygon, _) in enumerate(polygons, 1):
            cv2.polylines(overlay, [polygon], True, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(overlay, str(number), tuple(np.rint(center + [8, -8]).astype(int)),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(review / f"frame_{frame_index:02d}.jpg"), overlay, [cv2.IMWRITE_JPEG_QUALITY, 95])
        for variant_index in range(args.variants):
            stem = f"{args.session}__frame_{frame_index:02d}_v{variant_index:02d}__right_white_brown"
            cv2.imwrite(str(output_images / f"{stem}.jpg"), variant(rectified, variant_index),
                        [cv2.IMWRITE_JPEG_QUALITY, 92 if variant_index else 96])
            write_label(output_labels / f"{stem}.txt", polygons, width, height)
        summary.append({"frame": str(path), "registration_inliers": registration["inliers"],
                        "mask_count": len(polygons), "areas_px": [round(item[2], 1) for item in polygons]})
    payload = {"schema_version": 1, "session": args.session, "source_frames": len(summary),
               "variants_per_frame": args.variants, "generated_samples": len(summary) * args.variants,
               "class_id": CLASS_ID, "label_review": str(review), "frames": summary}
    (review / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
