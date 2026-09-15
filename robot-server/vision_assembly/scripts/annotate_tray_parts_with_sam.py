#!/usr/bin/env python3
"""Interactive box-prompted SAM annotator that writes YOLO segmentation labels."""

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np
from ultralytics import SAM, YOLO


CLASSES = {"black_block": 0, "marked_white": 1, "right_white_brown": 2,
           "long_orange": 3, "gpu": 4, "hbm": 5}
DISPLAY = {"black_block": "VRM", "marked_white": "INDUCTOR", "right_white_brown": "SMD CAPACITOR",
           "long_orange": "POWER MODULE", "gpu": "GPU", "hbm": "HBM"}
EXPECTED = {"black_block": 10, "marked_white": 4, "right_white_brown": 10,
            "long_orange": 8, "gpu": 2, "hbm": 16}


def largest_polygon(mask):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    epsilon = max(0.5, 0.003 * cv2.arcLength(contour, True))
    polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
    return polygon if len(polygon) >= 3 else None


class Annotator:
    def __init__(self, args):
        self.args = args
        self.model = SAM(str(args.model))
        self.items = []
        for part in CLASSES:
            all_files = sorted((args.session / "crops" / part).glob("*.jpg"))
            files = all_files[args.start : args.start + args.limit if args.limit else None]
            self.items.extend((part, path) for path in files)
        self.items.sort(key=lambda item: (item[1].name, CLASSES[item[0]]))
        self.prelabel_model = YOLO(str(args.prelabel_model)) if args.prelabel_model else None
        self.output_images = args.output / "images" / "all"
        self.output_labels = args.output / "labels" / "all"
        self.output_images.mkdir(parents=True, exist_ok=True)
        self.output_labels.mkdir(parents=True, exist_ok=True)
        if args.only_incomplete:
            expected = EXPECTED
            remaining = []
            for part, path in self.items:
                label = self.output_labels / f"{self.output_stem(part, path)}.txt"
                count = len([row for row in label.read_text().splitlines() if row.strip()]) if label.exists() else 0
                if count != expected[part]:
                    remaining.append((part, path))
            self.items = remaining
        self.index = 0
        self.boxes = []
        self.polygons = []
        self.drag_start = None
        self.cursor = None
        cv2.namedWindow("SAM tray annotation", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("SAM tray annotation", self.mouse)

    def output_stem(self, part, path):
        return f"{self.args.session.name}__{path.stem}__{part}"

    def load(self):
        part, path = self.items[self.index]
        self.part, self.path = part, path
        self.image = cv2.imread(str(path))
        if self.image is None:
            raise RuntimeError(f"Cannot read {path}")
        self.boxes, self.polygons = [], []
        label = self.output_labels / f"{self.output_stem(part, path)}.txt"
        if label.exists():
            h, w = self.image.shape[:2]
            for row in label.read_text(encoding="utf-8").splitlines():
                fields = row.split()
                if len(fields) < 7:
                    continue
                values = np.asarray([float(value) for value in fields[1:]], dtype=np.float32).reshape(-1, 2)
                values[:, 0] *= w; values[:, 1] *= h
                self.polygons.append(np.rint(values).astype(np.int32))
                x, y, bw, bh = cv2.boundingRect(self.polygons[-1])
                self.boxes.append((x, y, x + bw, y + bh))
        elif self.prelabel_model is not None:
            result = self.prelabel_model.predict(
                self.image, imgsz=640, conf=self.args.prelabel_conf, device=self.args.device,
                retina_masks=True, verbose=False
            )[0]
            candidates = []
            if result.masks is not None and result.boxes is not None:
                for score, cls, polygon in zip(
                    result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist(), result.masks.xy
                ):
                    if int(cls) != CLASSES[part] or len(polygon) < 3:
                        continue
                    poly = np.rint(polygon).astype(np.int32)
                    moments = cv2.moments(poly)
                    if abs(moments["m00"]) < 1e-6:
                        continue
                    center = np.array([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])
                    candidates.append((float(score), center, poly))
            radius = {"black_block": 14.0, "marked_white": 12.0, "right_white_brown": 7.0,
                      "long_orange": 30.0, "gpu": 35.0, "hbm": 12.0}[part]
            accepted = []
            for score, center, poly in sorted(candidates, reverse=True, key=lambda item: item[0]):
                if any(np.linalg.norm(center - old_center) < radius for _, old_center, _ in accepted):
                    continue
                accepted.append((score, center, poly))
            for _, _, poly in accepted:
                self.polygons.append(poly)
                x, y, bw, bh = cv2.boundingRect(poly)
                self.boxes.append((x, y, x + bw, y + bh))

    def mouse(self, event, x, y, _flags, _param):
        self.cursor = (x, y)
        if event == cv2.EVENT_RBUTTONDOWN and self.polygons:
            inside = [i for i, polygon in enumerate(self.polygons)
                      if cv2.pointPolygonTest(polygon.astype(np.float32), (float(x), float(y)), False) >= 0]
            if inside:
                index = inside[-1]
            else:
                centers = [np.mean(polygon, axis=0) for polygon in self.polygons]
                index = int(np.argmin([np.linalg.norm(center - (x, y)) for center in centers]))
                if np.linalg.norm(centers[index] - (x, y)) > 25:
                    return
            self.polygons.pop(index); self.boxes.pop(index)
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drag_start = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self.drag_start is not None:
            x1, y1 = self.drag_start
            self.drag_start = None
            x1, x2 = sorted((max(0, x1), min(self.image.shape[1] - 1, x)))
            y1, y2 = sorted((max(0, y1), min(self.image.shape[0] - 1, y)))
            if x2 - x1 < 3 or y2 - y1 < 3:
                return
            result = self.model.predict(
                self.image, bboxes=[[x1, y1, x2, y2]], device=self.args.device, verbose=False
            )[0]
            if result.masks is None or len(result.masks.data) == 0:
                return
            mask = result.masks.data[0].cpu().numpy()
            mask = cv2.resize(mask, (self.image.shape[1], self.image.shape[0]), interpolation=cv2.INTER_NEAREST) > 0.5
            polygon = largest_polygon(mask)
            if polygon is not None:
                self.boxes.append((x1, y1, x2, y2))
                self.polygons.append(polygon)

    def save(self):
        stem = self.output_stem(self.part, self.path)
        shutil.copy2(self.path, self.output_images / f"{stem}.jpg")
        h, w = self.image.shape[:2]
        rows = []
        for polygon in self.polygons:
            coords = []
            for x, y in polygon:
                coords.extend((f"{x / w:.6f}", f"{y / h:.6f}"))
            rows.append(f"{CLASSES[self.part]} " + " ".join(coords))
        (self.output_labels / f"{stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")

    def draw(self):
        canvas = self.image.copy()
        overlay = canvas.copy()
        for polygon in self.polygons:
            cv2.fillPoly(overlay, [polygon.astype(np.int32)], (40, 220, 40))
            cv2.polylines(canvas, [polygon.astype(np.int32)], True, (0, 255, 0), 2, cv2.LINE_AA)
        canvas = cv2.addWeighted(overlay, 0.28, canvas, 0.72, 0)
        if self.drag_start and self.cursor:
            cv2.rectangle(canvas, self.drag_start, self.cursor, (0, 255, 255), 1)
        expected = EXPECTED[self.part]
        text = f"{self.index + 1}/{len(self.items)}  {DISPLAY[self.part]}  masks {len(self.polygons)}/{expected}"
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 54), (0, 0, 0), -1)
        cv2.putText(canvas, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(canvas, "drag=add  right-click=remove  Z=undo  R=reset  N=save+next  P=previous  Q=quit", (8, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

    def run(self):
        if not self.items:
            raise RuntimeError("No crop images found")
        self.load()
        while True:
            cv2.imshow("SAM tray annotation", self.draw())
            key = cv2.waitKey(20) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("z") and self.polygons:
                self.polygons.pop(); self.boxes.pop()
            elif key == ord("r"):
                self.polygons, self.boxes = [], []
            elif key == ord("n"):
                self.save()
                if self.index + 1 >= len(self.items):
                    break
                self.index += 1; self.load()
            elif key == ord("p") and self.index > 0:
                self.index -= 1; self.load()
        cv2.destroyAllWindows()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, default=root / "datasets/tray_segmentation/raw/tray_parts_01")
    parser.add_argument("--output", type=Path, default=root / "datasets/tray_segmentation/yolo")
    parser.add_argument("--model", type=Path, default=root.parent / "sam2.1_t.pt")
    parser.add_argument("--device", default="0")
    parser.add_argument("--limit", type=int, default=20, help="Images per part class for the first training round")
    parser.add_argument("--start", type=int, default=0, help="Start index per part class")
    parser.add_argument("--prelabel-model", type=Path, default=None)
    parser.add_argument("--prelabel-conf", type=float, default=0.20)
    parser.add_argument("--only-incomplete", action="store_true")
    Annotator(parser.parse_args()).run()


if __name__ == "__main__":
    main()
