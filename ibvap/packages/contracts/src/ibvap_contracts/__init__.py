"""
IBVAP Contracts — Canonical cross-service domain models.

This package is the single source of truth for:
- Domain enumerations
- Pydantic domain models
- API request/response models
- WebSocket event payloads
- Sync envelopes

Do NOT redefine these types in edge-agent, central-api, or dashboard.
Import from here instead.
"""

from ibvap_contracts.enums import (
    AlertStatus,
    CameraProtocol,
    CameraStatus,
    EvidenceKind,
    EventStatus,
    EventType,
    GeometryType,
    RiskLevel,
    RiskSignalCode,
    SyncStatus,
    ZoneType,
)
from ibvap_contracts.models.alert import Alert
from ibvap_contracts.models.audit import AuditLog
from ibvap_contracts.models.camera import Camera
from ibvap_contracts.models.detection import BoundingBox, Detection
from ibvap_contracts.models.event import Event
from ibvap_contracts.models.evidence import Evidence
from ibvap_contracts.models.risk import RiskResult, RiskSignal
from ibvap_contracts.models.sync import SyncEnvelope
from ibvap_contracts.models.track import Track
from ibvap_contracts.models.zone import Zone

__version__ = "1.0.0"

__all__ = [
    # Enums
    "AlertStatus",
    "CameraProtocol",
    "CameraStatus",
    "EvidenceKind",
    "EventStatus",
    "EventType",
    "GeometryType",
    "RiskLevel",
    "RiskSignalCode",
    "SyncStatus",
    "ZoneType",
    # Models
    "Alert",
    "AuditLog",
    "BoundingBox",
    "Camera",
    "Detection",
    "Event",
    "Evidence",
    "RiskResult",
    "RiskSignal",
    "SyncEnvelope",
    "Track",
    "Zone",
]
