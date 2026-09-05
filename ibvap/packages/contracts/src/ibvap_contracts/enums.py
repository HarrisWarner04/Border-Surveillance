"""
IBVAP canonical enumerations.

These are the single source of truth for all enum values used across
edge-agent, central-api, and dashboard.  Do not redefine these elsewhere.

Schema version: 1.0
"""

from enum import Enum


class RiskLevel(str, Enum):
    """
    Risk classification levels.

    Canonical thresholds (configurable, these are defaults):
        LOW      0 – 19
        MEDIUM  20 – 49
        HIGH    50 – 79
        CRITICAL 80 – 100
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    """Lifecycle state of a surveillance event."""

    OPEN = "OPEN"
    UPDATED = "UPDATED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class AlertStatus(str, Enum):
    """Delivery and acknowledgement state of an alert."""

    PENDING = "PENDING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


class SyncStatus(str, Enum):
    """State of an outbox item in the store-and-forward sync queue."""

    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    SYNCED = "SYNCED"
    RETRY_WAIT = "RETRY_WAIT"
    FAILED = "FAILED"


class CameraStatus(str, Enum):
    """Operational status of a camera source."""

    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"


class CameraProtocol(str, Enum):
    """Supported camera/stream protocols."""

    RTSP = "RTSP"
    ONVIF = "ONVIF"
    FILE = "FILE"
    MOCK = "MOCK"


class ZoneType(str, Enum):
    """Semantic type of a virtual zone drawn on a camera view."""

    RESTRICTED = "RESTRICTED"
    MONITORING = "MONITORING"
    ENTRY = "ENTRY"
    SAFE = "SAFE"


class GeometryType(str, Enum):
    """Shape of a virtual zone boundary."""

    POLYGON = "POLYGON"
    LINE = "LINE"
    RECTANGLE = "RECTANGLE"


class EvidenceKind(str, Enum):
    """Type of evidence artifact attached to an event."""

    SNAPSHOT = "SNAPSHOT"
    VIDEO_CLIP = "VIDEO_CLIP"
    METADATA = "METADATA"


class EventType(str, Enum):
    """
    Canonical event taxonomy.

    Event names are stable contracts — do not rename without a schema
    version bump and migration.
    """

    # Object presence
    PERSON_DETECTED = "PERSON_DETECTED"
    VEHICLE_DETECTED = "VEHICLE_DETECTED"
    OBJECT_DETECTED = "OBJECT_DETECTED"

    # Zone / boundary
    ZONE_ENTRY = "ZONE_ENTRY"
    ZONE_EXIT = "ZONE_EXIT"
    PERIMETER_INTRUSION = "PERIMETER_INTRUSION"
    LINE_CROSSING = "LINE_CROSSING"

    # Behavior
    LOITERING = "LOITERING"
    RUNNING = "RUNNING"
    SUDDEN_MOVEMENT = "SUDDEN_MOVEMENT"
    CROWD_FORMATION = "CROWD_FORMATION"
    CROWD_ANOMALY = "CROWD_ANOMALY"

    # Identity / watchlist
    WATCHLIST_MATCH = "WATCHLIST_MATCH"
    ANPR_MATCH = "ANPR_MATCH"

    # Correlation
    REPEATED_ACTIVITY = "REPEATED_ACTIVITY"
    CROSS_CAMERA_ACTIVITY = "CROSS_CAMERA_ACTIVITY"

    # Anomaly
    ANOMALY_SIGNAL = "ANOMALY_SIGNAL"

    # System health
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    STREAM_DEGRADED = "STREAM_DEGRADED"
    EDGE_SERVICE_DEGRADED = "EDGE_SERVICE_DEGRADED"
    SYNC_BACKLOG_HIGH = "SYNC_BACKLOG_HIGH"


class RiskSignalCode(str, Enum):
    """
    Canonical risk signal vocabulary.

    These 15 signals are the complete initial scoring vocabulary.
    Weights are configuration-driven — see risk engine config.
    No new signals may be added without updating this enum AND the spec.

    Default weights (from spec, all configurable):
        RESTRICTED_ZONE_ENTRY    20
        UNUSUAL_TIME              5
        RUNNING                  10
        HIDING                   10
        LOITERING                15
        WEAPON_LIKE_OBJECT       30
        GROUP_MOVEMENT           10
        CROWD_ANOMALY            15
        WATCHLIST_MATCH          35
        ANPR_MATCH               30
        REPEATED_ACTIVITY        10
        CAMERA_SITE_SENSITIVITY   5
        PERIMETER_INTRUSION      25
        LINE_CROSSING            15
        CROSS_CAMERA_CORRELATION 10
    """

    RESTRICTED_ZONE_ENTRY = "RESTRICTED_ZONE_ENTRY"
    UNUSUAL_TIME = "UNUSUAL_TIME"
    RUNNING = "RUNNING"
    HIDING = "HIDING"
    LOITERING = "LOITERING"
    WEAPON_LIKE_OBJECT = "WEAPON_LIKE_OBJECT"
    GROUP_MOVEMENT = "GROUP_MOVEMENT"
    CROWD_ANOMALY = "CROWD_ANOMALY"
    WATCHLIST_MATCH = "WATCHLIST_MATCH"
    ANPR_MATCH = "ANPR_MATCH"
    REPEATED_ACTIVITY = "REPEATED_ACTIVITY"
    CAMERA_SITE_SENSITIVITY = "CAMERA_SITE_SENSITIVITY"
    PERIMETER_INTRUSION = "PERIMETER_INTRUSION"
    LINE_CROSSING = "LINE_CROSSING"
    CROSS_CAMERA_CORRELATION = "CROSS_CAMERA_CORRELATION"


class UserRole(str, Enum):
    """RBAC roles for dashboard users."""

    ADMIN = "ADMIN"
    SECURITY_OPERATOR = "SECURITY_OPERATOR"
    INVESTIGATOR = "INVESTIGATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"
