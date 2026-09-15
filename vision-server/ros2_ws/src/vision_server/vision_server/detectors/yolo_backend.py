from pathlib import Path
import math
from typing import List

import cv2
import numpy as np

from .base import Detection, Detector


class YoloBackend(Detector):
    """Small adapter that keeps Ultralytics details outside ROS nodes."""

    def __init__(
        self,
        model_path: str,
        image_size: int = 640,
        confidence: float = 0.5,
        iou: float = 0.45,
        device: str = 'auto',
        obb_duplicate_iou: float = 0.25,
        half: bool = False,
        max_detections: int = 300,
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f'YOLO model not found: {path}')

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                'Ultralytics is not installed. Install it before live YOLO inference.'
            ) from exc

        self._model = YOLO(str(path))
        self._image_size = int(image_size)
        self._confidence = float(confidence)
        self._iou = float(iou)
        self._device = None if device == 'auto' else device
        self._obb_duplicate_iou = float(obb_duplicate_iou)
        self._half = bool(half)
        self._max_detections = max(1, int(max_detections))

    @staticmethod
    def _polygon_iou(first: Detection, second: Detection) -> float:
        if not first.obb_points or not second.obb_points:
            return 0.0
        polygon_a = np.asarray(first.obb_points, dtype=np.float32)
        polygon_b = np.asarray(second.obb_points, dtype=np.float32)
        area_a = abs(float(cv2.contourArea(polygon_a)))
        area_b = abs(float(cv2.contourArea(polygon_b)))
        if area_a <= 0.0 or area_b <= 0.0:
            return 0.0
        intersection, _ = cv2.intersectConvexConvex(polygon_a, polygon_b)
        union = area_a + area_b - float(intersection)
        return 0.0 if union <= 0.0 else float(intersection) / union

    def _remove_duplicate_obbs(self, detections: List[Detection]) -> List[Detection]:
        kept = []
        for candidate in sorted(detections, key=lambda item: item.score, reverse=True):
            duplicate = any(
                candidate.class_id == previous.class_id
                and self._polygon_iou(candidate, previous) >= self._obb_duplicate_iou
                for previous in kept
            )
            if not duplicate:
                kept.append(candidate)
        return kept

    def detect(self, image) -> List[Detection]:
        results = self._model.predict(
            source=image,
            imgsz=self._image_size,
            conf=self._confidence,
            iou=self._iou,
            device=self._device,
            quantize=16 if self._half else None,
            max_det=self._max_detections,
            verbose=False,
        )

        detections = []
        for result in results:
            names = result.names
            if result.obb is not None:
                polygons = result.obb.xyxyxyxy.cpu().numpy()
                boxes = result.obb.xywhr.cpu().numpy()
                classes = result.obb.cls.int().cpu().tolist()
                confidences = result.obb.conf.cpu().tolist()
                for polygon, box, class_id, score in zip(
                    polygons, boxes, classes, confidences
                ):
                    center_x, center_y, width, height, angle_rad = box.tolist()
                    # Publish the long-axis orientation with 180-degree
                    # periodicity so robot alignment is model-version neutral.
                    if width < height:
                        width, height = height, width
                        angle_rad += math.pi / 2.0
                    angle_deg = math.degrees(angle_rad) % 180.0
                    x1, y1 = polygon.min(axis=0).tolist()
                    x2, y2 = polygon.max(axis=0).tolist()
                    detections.append(
                        Detection(
                            name=str(names[class_id]),
                            class_id=int(class_id),
                            score=float(score),
                            x=int(round(x1)),
                            y=int(round(y1)),
                            width=max(0, int(round(x2 - x1))),
                            height=max(0, int(round(y2 - y1))),
                            angle_deg=float(angle_deg),
                            obb_points=tuple(
                                (float(point[0]), float(point[1]))
                                for point in polygon
                            ),
                        )
                    )
                continue
            if result.boxes is None:
                continue
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                score = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        name=str(names[class_id]),
                        class_id=class_id,
                        score=score,
                        x=int(round(x1)),
                        y=int(round(y1)),
                        width=max(0, int(round(x2 - x1))),
                        height=max(0, int(round(y2 - y1))),
                    )
                )
        return self._remove_duplicate_obbs(detections)
