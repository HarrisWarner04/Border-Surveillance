"""Camera domain model. Schema version: 1.0"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ibvap_contracts.enums import CameraProtocol, CameraStatus


class Camera(BaseModel):
    """
    Represents a physical or virtual camera source.

    stream_uri_ref is a configuration key reference, NOT the raw URI.
    Credentials must never appear in this model or in logs.
    """

    schema_version: str = Field(default="1.0", frozen=True)
    id: UUID
    site_id: UUID
    name: str = Field(min_length=1, max_length=128)
    protocol: CameraProtocol
    # Reference to a secret/config key that resolves to the actual stream URI.
    # Example: "cameras.cam01.stream_uri" or an env var name.
    stream_uri_ref: str = Field(min_length=1)
    enabled: bool = True
    target_fps: int = Field(default=5, ge=1, le=60)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    timezone: str = Field(default="UTC")
    status: CameraStatus
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": False, "str_strip_whitespace": True, "protected_namespaces": ()}
