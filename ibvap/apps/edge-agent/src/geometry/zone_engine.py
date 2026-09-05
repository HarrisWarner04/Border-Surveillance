"""
Geometry engine: virtual zone logic.

All coordinates are normalized [0, 1].
Pixel conversion lives here and nowhere else.

Key functions:
  point_in_polygon()   — ray-casting algorithm, boundary counts as inside
  validate_polygon()   — reject invalid zone configurations
  foot_point()         — bottom-center of a bounding box (ground contact)
  ZoneEngine           — per-camera zone membership evaluator
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.observability.logging import get_logger

try:
    from ibvap_contracts.enums import GeometryType
    from ibvap_contracts.models.detection import BoundingBox
    from ibvap_contracts.models.track import Track
    from ibvap_contracts.models.zone import Zone
except ImportError:
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.enums import GeometryType  # type: ignore[no-redef]
    from ibvap_contracts.models.detection import BoundingBox  # type: ignore[no-redef]
    from ibvap_contracts.models.track import Track  # type: ignore[no-redef]
    from ibvap_contracts.models.zone import Zone  # type: ignore[no-redef]

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def foot_point(bbox: BoundingBox) -> tuple[float, float]:
    """
    Return the bottom-centre (foot) point of a bounding box.

    This represents the ground contact point and is used for
    all zone membership checks instead of the bbox centre.

    Returns (x, y) both in normalised [0, 1] range.
    """
    return bbox.foot_x, bbox.foot_y


def to_pixel(normalized_x: float, normalized_y: float, width: int, height: int) -> tuple[int, int]:
    """Convert normalised coordinates to pixel coordinates."""
    return int(normalized_x * width), int(normalized_y * height)


# ---------------------------------------------------------------------------
# Polygon validation
# ---------------------------------------------------------------------------


class PolygonValidationError(ValueError):
    """Raised when a polygon definition is geometrically invalid."""


def validate_polygon(points: list[tuple[float, float]]) -> None:
    """
    Validate a list of (x, y) polygon vertices.

    Raises PolygonValidationError for:
      - fewer than 3 vertices
      - any coordinate outside [0, 1]
      - NaN or infinite values
    """
    if len(points) < 3:
        raise PolygonValidationError(
            f"Polygon must have at least 3 vertices, got {len(points)}"
        )
    for i, (x, y) in enumerate(points):
        if not math.isfinite(x) or not math.isfinite(y):
            raise PolygonValidationError(f"Point {i} contains NaN or Inf: ({x}, {y})")
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise PolygonValidationError(
                f"Point {i} ({x:.4f}, {y:.4f}) is outside normalised range [0, 1]"
            )


# ---------------------------------------------------------------------------
# Point-in-polygon: ray-casting algorithm
# ---------------------------------------------------------------------------


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """
    Return True if the point is inside (or on the boundary of) the polygon.

    Uses the ray-casting algorithm with the convention that boundary
    points count as inside.  This is correct for surveillance zone logic
    where "on the fence line" should trigger an intrusion.

    Parameters
    ----------
    point   : (x, y) in normalised coords
    polygon : list of (x, y) vertices in normalised coords (≥ 3 points)

    Raises PolygonValidationError if polygon is invalid.
    """
    validate_polygon(polygon)

    px, py = point
    n = len(polygon)
    inside = False

    # Fast boundary check: if the point is very close to an edge, count it inside
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        # Check if point is on this edge segment (within floating-point tolerance)
        if _point_on_segment(px, py, ax, ay, bx, by):
            return True

    # Ray-casting from the point to the right (positive x direction)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Does the edge cross the horizontal ray from (px, py)?
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


def _point_on_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
    tol: float = 1e-9,
) -> bool:
    """Return True if point P lies on segment AB within tolerance."""
    # Cross product of (B-A) × (P-A) — zero means collinear
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > tol:
        return False
    # Dot product check: P is between A and B
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if dot < -tol:
        return False
    sq_len = (bx - ax) ** 2 + (by - ay) ** 2
    return dot <= sq_len + tol


# ---------------------------------------------------------------------------
# Zone state per track
# ---------------------------------------------------------------------------


class ZonePresenceState:
    """
    Tracks whether a specific (camera, track, zone) combination is inside
    the zone, outside, or transitioning.

    Maintains consecutive_inside_frames for temporal confirmation.
    """

    OUTSIDE = "OUTSIDE"
    INSIDE = "INSIDE"
    UNKNOWN = "UNKNOWN"

    def __init__(self) -> None:
        self.state: str = self.UNKNOWN
        self.consecutive_inside_frames: int = 0
        self.last_seen: datetime = datetime.now(tz=UTC)

    def update(self, is_inside: bool) -> str:
        """
        Update state with a new observation.

        Returns one of:
          'ENTERED'    — transition from OUTSIDE/UNKNOWN → INSIDE
          'EXITED'     — transition from INSIDE → OUTSIDE
          'INSIDE'     — already inside, no transition
          'OUTSIDE'    — already outside, no transition
        """
        self.last_seen = datetime.now(tz=UTC)
        previous = self.state

        if is_inside:
            self.consecutive_inside_frames += 1
            new_state = self.INSIDE
        else:
            self.consecutive_inside_frames = 0
            new_state = self.OUTSIDE

        self.state = new_state

        if previous in (self.OUTSIDE, self.UNKNOWN) and new_state == self.INSIDE:
            return "ENTERED"
        elif previous == self.INSIDE and new_state == self.OUTSIDE:
            return "EXITED"
        elif new_state == self.INSIDE:
            return "INSIDE"
        else:
            return "OUTSIDE"

    def is_expired(self, ttl_seconds: float) -> bool:
        elapsed = (datetime.now(tz=UTC) - self.last_seen).total_seconds()
        return elapsed >= ttl_seconds


# ---------------------------------------------------------------------------
# ZoneEngine
# ---------------------------------------------------------------------------


@dataclass
class ZoneCrossing:
    """Describes a zone entry/exit event for a single track."""
    zone: Zone
    track_id: int
    camera_id: str
    transition: str   # 'ENTERED' | 'EXITED' | 'INSIDE' | 'OUTSIDE'
    consecutive_inside_frames: int
    foot_point_xy: tuple[float, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def is_entry(self) -> bool:
        return self.transition == "ENTERED"

    @property
    def is_confirmed_entry(self) -> bool:
        """True once consecutive_inside_frames matches the confirmation threshold."""
        return self.transition in ("ENTERED", "INSIDE") and self.consecutive_inside_frames >= 1


def segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """Return True if line segment p1-p2 intersects line segment p3-p4."""
    def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))


def point_to_segment_distance(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Return shortest distance from point p to segment a-b in normalised coordinates."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class ZoneEngine:
    """
    Evaluates zone membership for each active track on every frame.

    Per-camera, per-zone, per-track state is maintained internally.
    State expires after ttl_seconds to prevent memory leaks.
    """

    def __init__(self, zones: list[Zone], ttl_seconds: float = 30.0) -> None:
        self._zones = [z for z in zones if z.enabled]
        self._ttl = ttl_seconds
        # Key: (zone_id, track_id) → ZonePresenceState
        self._state: dict[tuple[str, int], ZonePresenceState] = {}

    def evaluate(self, tracks: list[Track]) -> list[ZoneCrossing]:
        """
        Evaluate all tracks against all zones.

        Returns a list of ZoneCrossing events (may be empty).
        Call this once per processed frame.
        """
        crossings: list[ZoneCrossing] = []
        self._expire_stale_states()

        for track in tracks:
            fp = foot_point(track.bbox)
            for zone in self._zones:
                if zone.geometry_type == GeometryType.LINE:
                    if len(zone.coordinates) == 2:
                        p1 = (float(zone.coordinates[0][0]), float(zone.coordinates[0][1]))
                        p2 = (float(zone.coordinates[1][0]), float(zone.coordinates[1][1]))
                        near = point_to_segment_distance(fp, p1, p2) <= 0.025
                        crossed = False
                        if len(track.trajectory) >= 2:
                            crossed = segments_intersect(track.trajectory[-2], fp, p1, p2)
                        inside = near or crossed
                    else:
                        inside = False
                else:
                    polygon = [(float(pt[0]), float(pt[1])) for pt in zone.coordinates]
                    try:
                        inside = point_in_polygon(fp, polygon)
                    except PolygonValidationError as exc:
                        logger.warning(
                            "zone_validation_error",
                            zone_id=zone.id,
                            error=str(exc),
                        )
                        continue

                key = (zone.id, track.track_id)
                if key not in self._state:
                    self._state[key] = ZonePresenceState()

                presence = self._state[key]
                transition = presence.update(inside)

                crossing = ZoneCrossing(
                    zone=zone,
                    track_id=track.track_id,
                    camera_id=track.camera_id,
                    transition=transition,
                    consecutive_inside_frames=presence.consecutive_inside_frames,
                    foot_point_xy=fp,
                )
                crossings.append(crossing)

        return crossings

    def reset(self) -> None:
        """Clear all state. Call on camera reconnect."""
        self._state.clear()

    def _expire_stale_states(self) -> None:
        expired_keys = [k for k, v in self._state.items() if v.is_expired(self._ttl)]
        for k in expired_keys:
            del self._state[k]
        if expired_keys:
            logger.debug("zone_states_expired", count=len(expired_keys))


# ---------------------------------------------------------------------------
# YAML zone loader
# ---------------------------------------------------------------------------


def load_zones_from_yaml(path: str) -> list[Zone]:
    """
    Load zone definitions from a YAML configuration file.

    Returns a list of Zone objects with validation applied.
    Raises ValueError on malformed configuration.
    """
    from datetime import datetime

    import yaml

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ValueError(f"Zone config file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in zone config {path}: {exc}") from exc

    now = datetime.now(tz=UTC)
    zones: list[Zone] = []

    for raw_zone in data.get("zones", []):
        try:
            zone = Zone(
                id=raw_zone["zone_id"],
                camera_id=data["camera_id"],
                name=raw_zone["name"],
                type=raw_zone["type"].upper(),
                geometry_type=raw_zone.get("geometry_type", "polygon").upper(),
                coordinates=raw_zone["polygon"],
                enabled=raw_zone.get("enabled", True),
                created_at=now,
                updated_at=now,
            )
            zones.append(zone)
        except Exception as exc:
            raise ValueError(f"Invalid zone definition {raw_zone.get('zone_id')!r}: {exc}") from exc

    return zones
