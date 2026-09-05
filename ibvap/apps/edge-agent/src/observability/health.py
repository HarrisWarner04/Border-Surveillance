"""
Health state for the edge agent and individual camera pipelines.

States:
    HEALTHY   — stream connected, frames fresh, pipeline heartbeat active
    DEGRADED  — reconnecting, low FPS, or a non-critical sink failing
    OFFLINE   — stream unavailable beyond timeout threshold
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


@dataclass
class CameraHealth:
    camera_id: str
    status: HealthStatus = HealthStatus.OFFLINE
    last_frame_at: datetime | None = None
    session_id: str | None = None
    fps_actual: float = 0.0
    reconnect_count: int = 0
    message: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def mark_connected(self, session_id: str) -> None:
        self.status = HealthStatus.HEALTHY
        self.session_id = session_id
        self.updated_at = datetime.now(tz=UTC)

    def mark_frame(self, fps: float = 0.0) -> None:
        self.last_frame_at = datetime.now(tz=UTC)
        self.fps_actual = fps
        if self.status == HealthStatus.OFFLINE:
            self.status = HealthStatus.DEGRADED

    def mark_degraded(self, message: str = "") -> None:
        self.status = HealthStatus.DEGRADED
        self.message = message
        self.updated_at = datetime.now(tz=UTC)

    def mark_offline(self, message: str = "") -> None:
        self.status = HealthStatus.OFFLINE
        self.message = message
        self.fps_actual = 0.0
        self.updated_at = datetime.now(tz=UTC)

    def to_dict(self) -> dict[str, object]:
        return {
            "camera_id": self.camera_id,
            "status": self.status.value,
            "last_frame_at": self.last_frame_at.isoformat() if self.last_frame_at else None,
            "session_id": self.session_id,
            "fps_actual": round(self.fps_actual, 2),
            "reconnect_count": self.reconnect_count,
            "message": self.message,
            "updated_at": self.updated_at.isoformat(),
        }


class HealthRegistry:
    """Thread-safe registry of per-camera health states."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cameras: dict[str, CameraHealth] = {}

    def get_or_create(self, camera_id: str) -> CameraHealth:
        with self._lock:
            if camera_id not in self._cameras:
                self._cameras[camera_id] = CameraHealth(camera_id=camera_id)
            return self._cameras[camera_id]

    def all_cameras(self) -> list[CameraHealth]:
        with self._lock:
            return list(self._cameras.values())

    def overall_status(self) -> HealthStatus:
        cameras = self.all_cameras()
        if not cameras:
            return HealthStatus.OFFLINE
        statuses = {c.status for c in cameras}
        if HealthStatus.HEALTHY in statuses and HealthStatus.OFFLINE not in statuses:
            return HealthStatus.HEALTHY
        if HealthStatus.HEALTHY in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.OFFLINE

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall_status().value,
            "cameras": [c.to_dict() for c in self.all_cameras()],
        }


# Module-level singleton
health_registry = HealthRegistry()
