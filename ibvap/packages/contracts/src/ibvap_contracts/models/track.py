"""Track domain model. Schema version: 1.0"""

from datetime import datetime

from pydantic import BaseModel, Field

from ibvap_contracts.models.detection import BoundingBox


class Track(BaseModel):
    """
    A persistent multi-frame track produced by the tracker.

    track_id is scoped to a single camera session.  It must be reset
    when the camera reconnects.  Do not use it as a global identifier.

    trajectory contains normalized (x, y) foot-point history, newest last.
    """

    track_id: int = Field(ge=1)
    camera_id: str
    class_id: int = Field(ge=0)
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    first_seen: datetime
    last_seen: datetime
    # Normalized (x, y) foot points, oldest first
    trajectory: list[tuple[float, float]] = Field(default_factory=list)
    # Zone IDs this track is currently inside
    zone_ids: list[str] = Field(default_factory=list)

    model_config = {"frozen": False, "protected_namespaces": ()}
