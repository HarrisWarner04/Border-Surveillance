"""Camera configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class CameraConfig(BaseModel):
    """
    Configuration for a single camera source.

    stream_uri is stored as SecretStr so it is never accidentally
    printed or serialised into logs.
    """

    camera_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=128)
    # Protocol determines which adapter handles the stream
    protocol: Literal["RTSP", "FILE", "MOCK"] = "MOCK"
    # SecretStr prevents the URI (which may contain credentials) from leaking
    stream_uri: SecretStr = SecretStr("")
    enabled: bool = True
    target_fps: int = Field(default=10, ge=1, le=30)
    # RTSP transport — tcp is more reliable over unstable networks
    transport: Literal["tcp", "udp"] = "tcp"
    # Reconnect parameters (seconds)
    reconnect_initial_seconds: float = Field(default=1.0, gt=0)
    reconnect_max_seconds: float = Field(default=30.0, gt=0)
    reconnect_max_attempts: int = Field(
        default=0, ge=0,
        description="0 = retry indefinitely",
    )

    def safe_name(self) -> str:
        """Return camera identification safe for logs (no credentials)."""
        return f"camera_id={self.camera_id} name={self.name} protocol={self.protocol}"
