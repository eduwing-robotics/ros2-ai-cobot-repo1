from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Detection:
    name: str
    class_id: int
    score: float
    x: int
    y: int
    width: int
    height: int
    angle_deg: Optional[float] = None


class Detector(ABC):
    @abstractmethod
    def detect(self, image) -> List[Detection]:
        """Return detections in original-image pixel coordinates."""
