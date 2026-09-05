"""Zone domain model. Schema version: 1.0"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ibvap_contracts.enums import GeometryType, ZoneType


class Zone(BaseModel):
    """
    A virtual zone drawn on a camera view.

    coordinates are normalized to [0, 1] so the zone definition
    survives resolution changes.

    For POLYGON / RECTANGLE: list of [x, y] pairs (≥3 vertices).
    For LINE: exactly 2 [x, y] points.
    """

    id: str
    camera_id: str
    name: str = Field(min_length=1, max_length=128)
    type: ZoneType
    geometry_type: GeometryType
    # Each inner list is [x, y] in normalized coords
    coordinates: list[list[float]]
    enabled: bool = True
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_coordinates(self) -> "Zone":
        if self.geometry_type == GeometryType.LINE:
            if len(self.coordinates) != 2:
                raise ValueError("LINE zone must have exactly 2 points")
        else:
            if len(self.coordinates) < 3:
                raise ValueError(
                    f"{self.geometry_type} zone must have at least 3 vertices, "
                    f"got {len(self.coordinates)}"
                )
        for i, pt in enumerate(self.coordinates):
            if len(pt) != 2:
                raise ValueError(f"Point {i} must have exactly 2 values [x, y], got {pt}")
            x, y = pt
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(
                    f"Point {i} ({x}, {y}) is outside normalized range [0, 1]"
                )
        return self

    model_config = {"frozen": False, "protected_namespaces": ()}
