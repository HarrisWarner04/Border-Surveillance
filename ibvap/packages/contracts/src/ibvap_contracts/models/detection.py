"""Detection domain models. Schema version: 1.0"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    """
    Axis-aligned bounding box in normalized image coordinates.
    All values are in [0.0, 1.0].  x1 < x2 and y1 < y2 are enforced.
    """

    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_ordering(self) -> "BoundingBox":
        if self.x1 >= self.x2:
            raise ValueError(f"x1 ({self.x1}) must be less than x2 ({self.x2})")
        if self.y1 >= self.y2:
            raise ValueError(f"y1 ({self.y1}) must be less than y2 ({self.y2})")
        return self

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def foot_x(self) -> float:
        """Bottom-center x — used as ground contact point for zone logic."""
        return (self.x1 + self.x2) / 2.0

    @property
    def foot_y(self) -> float:
        """Bottom-center y — used as ground contact point for zone logic."""
        return self.y2


class Detection(BaseModel):
    """
    A single object detection from the detector.
    Coordinates are normalized to [0,1].
    """

    id: UUID
    camera_id: str
    timestamp: datetime
    class_id: int = Field(ge=0)
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    track_id: int | None = Field(default=None, ge=1)
    model_name: str
    model_version: str

    model_config = {"frozen": False, "protected_namespaces": ()}
