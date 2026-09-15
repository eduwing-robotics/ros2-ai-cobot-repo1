from pathlib import Path
from typing import List

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

    def detect(self, image) -> List[Detection]:
        results = self._model.predict(
            source=image,
            imgsz=self._image_size,
            conf=self._confidence,
            iou=self._iou,
            device=self._device,
            verbose=False,
        )

        detections = []
        for result in results:
            names = result.names
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
        return detections
