"""
Unit tests: geometry layer.

Covers:
  - point_in_polygon: inside, outside, boundary, vertex, concave polygon
  - validate_polygon: < 3 vertices, out-of-range coords, NaN, Inf
  - foot_point: bottom-centre calculation
  - ZonePresenceState: transitions, consecutive frames, TTL expiry
  - ZoneEngine: evaluate crossings, reset
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

# conftest.py at edge-agent root adds both src/ parent and contracts/src to sys.path
from ibvap_contracts.enums import GeometryType, ZoneType
from ibvap_contracts.models.detection import BoundingBox
from ibvap_contracts.models.track import Track
from ibvap_contracts.models.zone import Zone

from src.geometry.zone_engine import (
    PolygonValidationError,
    ZoneCrossing,
    ZoneEngine,
    ZonePresenceState,
    foot_point,
    point_in_polygon,
    validate_polygon,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_zone(
    zone_id: str = "z1",
    coords: list[list[float]] | None = None,
    ztype: ZoneType = ZoneType.RESTRICTED,
) -> Zone:
    if coords is None:
        coords = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    return Zone(
        id=zone_id,
        camera_id="cam-01",
        name="Test Zone",
        type=ztype,
        geometry_type=GeometryType.POLYGON,
        coordinates=coords,
        created_at=_now(),
        updated_at=_now(),
    )


def _make_track(
    track_id: int = 1,
    x1: float = 0.3,
    y1: float = 0.3,
    x2: float = 0.5,
    y2: float = 0.7,
) -> Track:
    return Track(
        track_id=track_id,
        camera_id="cam-01",
        class_id=0,
        class_name="person",
        confidence=0.85,
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        first_seen=_now(),
        last_seen=_now(),
    )


# ---------------------------------------------------------------------------
# validate_polygon
# ---------------------------------------------------------------------------


class TestValidatePolygon:
    def test_valid_triangle(self) -> None:
        validate_polygon([(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)])

    def test_valid_rectangle(self) -> None:
        validate_polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])

    def test_too_few_vertices(self) -> None:
        with pytest.raises(PolygonValidationError, match="at least 3"):
            validate_polygon([(0.1, 0.1), (0.9, 0.9)])

    def test_empty_polygon(self) -> None:
        with pytest.raises(PolygonValidationError, match="at least 3"):
            validate_polygon([])

    def test_coord_x_above_1(self) -> None:
        with pytest.raises(PolygonValidationError, match="outside normalised range"):
            validate_polygon([(0.1, 0.1), (1.5, 0.5), (0.5, 0.9)])

    def test_coord_y_negative(self) -> None:
        with pytest.raises(PolygonValidationError, match="outside normalised range"):
            validate_polygon([(0.1, -0.1), (0.9, 0.1), (0.5, 0.9)])

    def test_nan_coordinate(self) -> None:
        with pytest.raises(PolygonValidationError, match="NaN or Inf"):
            validate_polygon([(0.1, float("nan")), (0.9, 0.1), (0.5, 0.9)])

    def test_inf_coordinate(self) -> None:
        with pytest.raises(PolygonValidationError, match="NaN or Inf"):
            validate_polygon([(0.1, float("inf")), (0.9, 0.1), (0.5, 0.9)])

    def test_boundary_coords_valid(self) -> None:
        validate_polygon([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)])


# ---------------------------------------------------------------------------
# point_in_polygon
# ---------------------------------------------------------------------------

UNIT_SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
DEMO_ZONE = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]


class TestPointInPolygon:
    def test_clearly_inside(self) -> None:
        assert point_in_polygon((0.5, 0.5), UNIT_SQUARE) is True

    def test_clearly_outside(self) -> None:
        assert point_in_polygon((2.0, 2.0), UNIT_SQUARE) is False

    def test_outside_just_beyond_edge(self) -> None:
        # Slightly below bottom edge y=0 — outside unit square
        assert point_in_polygon((0.5, -0.01), UNIT_SQUARE) is False

    def test_inside_demo_zone(self) -> None:
        assert point_in_polygon((0.5, 0.5), DEMO_ZONE) is True

    def test_outside_demo_zone_above(self) -> None:
        # y=0.05, above zone top edge (y=0.1)
        assert point_in_polygon((0.5, 0.05), DEMO_ZONE) is False

    def test_outside_demo_zone_left(self) -> None:
        assert point_in_polygon((0.05, 0.5), DEMO_ZONE) is False

    def test_on_top_edge_is_inside(self) -> None:
        # Boundary counts as inside
        assert point_in_polygon((0.5, 0.1), DEMO_ZONE) is True

    def test_on_left_edge_is_inside(self) -> None:
        assert point_in_polygon((0.1, 0.5), DEMO_ZONE) is True

    def test_on_corner_vertex_is_inside(self) -> None:
        assert point_in_polygon((0.1, 0.1), DEMO_ZONE) is True

    def test_concave_polygon_inside_notch(self) -> None:
        # L-shaped polygon
        l_shape = [
            (0.0, 0.0), (0.5, 0.0), (0.5, 0.5),
            (1.0, 0.5), (1.0, 1.0), (0.0, 1.0),
        ]
        assert point_in_polygon((0.25, 0.75), l_shape) is True

    def test_concave_polygon_outside_notch(self) -> None:
        l_shape = [
            (0.0, 0.0), (0.5, 0.0), (0.5, 0.5),
            (1.0, 0.5), (1.0, 1.0), (0.0, 1.0),
        ]
        # In the "missing" corner of the L
        assert point_in_polygon((0.75, 0.25), l_shape) is False

    def test_invalid_polygon_raises(self) -> None:
        with pytest.raises(PolygonValidationError):
            point_in_polygon((0.5, 0.5), [(0.1, 0.1), (0.9, 0.9)])


# ---------------------------------------------------------------------------
# foot_point
# ---------------------------------------------------------------------------


class TestFootPoint:
    def test_foot_is_bottom_center(self) -> None:
        bb = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.9)
        fx, fy = foot_point(bb)
        assert fx == pytest.approx(0.3)
        assert fy == pytest.approx(0.9)

    def test_foot_y_equals_y2(self) -> None:
        bb = BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=0.75)
        _, fy = foot_point(bb)
        assert fy == pytest.approx(0.75)

    def test_foot_x_is_midpoint(self) -> None:
        bb = BoundingBox(x1=0.2, y1=0.1, x2=0.8, y2=0.9)
        fx, _ = foot_point(bb)
        assert fx == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# ZonePresenceState transitions
# ---------------------------------------------------------------------------


class TestZonePresenceState:
    def test_initial_state_is_unknown(self) -> None:
        s = ZonePresenceState()
        assert s.state == ZonePresenceState.UNKNOWN

    def test_unknown_to_inside_returns_entered(self) -> None:
        s = ZonePresenceState()
        result = s.update(True)
        assert result == "ENTERED"
        assert s.state == ZonePresenceState.INSIDE
        assert s.consecutive_inside_frames == 1

    def test_outside_to_inside_returns_entered(self) -> None:
        s = ZonePresenceState()
        s.update(False)   # → OUTSIDE
        result = s.update(True)
        assert result == "ENTERED"

    def test_inside_to_inside_returns_inside(self) -> None:
        s = ZonePresenceState()
        s.update(True)
        result = s.update(True)
        assert result == "INSIDE"
        assert s.consecutive_inside_frames == 2

    def test_inside_to_outside_returns_exited(self) -> None:
        s = ZonePresenceState()
        s.update(True)
        result = s.update(False)
        assert result == "EXITED"
        assert s.state == ZonePresenceState.OUTSIDE

    def test_outside_stays_outside(self) -> None:
        s = ZonePresenceState()
        s.update(False)
        result = s.update(False)
        assert result == "OUTSIDE"

    def test_consecutive_resets_on_exit(self) -> None:
        s = ZonePresenceState()
        s.update(True)
        s.update(True)
        assert s.consecutive_inside_frames == 2
        s.update(False)
        assert s.consecutive_inside_frames == 0

    def test_ttl_expiry_zero_threshold(self) -> None:
        s = ZonePresenceState()
        s.update(True)
        assert not s.is_expired(999.0)
        assert s.is_expired(0.0)

    def test_not_expired_within_ttl(self) -> None:
        s = ZonePresenceState()
        s.update(True)
        assert not s.is_expired(60.0)


# ---------------------------------------------------------------------------
# ZoneEngine
# ---------------------------------------------------------------------------


class TestZoneEngine:
    def _engine(self, ztype: ZoneType = ZoneType.RESTRICTED) -> ZoneEngine:
        return ZoneEngine([_make_zone(ztype=ztype)], ttl_seconds=60.0)

    def test_track_inside_zone_returns_crossing(self) -> None:
        engine = self._engine()
        # foot at (0.4, 0.7) — inside demo zone x=[0.1,0.9] y=[0.1,0.9]
        track = _make_track(x1=0.3, y1=0.3, x2=0.5, y2=0.7)
        crossings = engine.evaluate([track])
        assert len(crossings) == 1
        assert crossings[0].transition in ("ENTERED", "INSIDE")

    def test_track_outside_zone(self) -> None:
        engine = self._engine()
        # foot at (0.5, 0.05) — above zone top edge y=0.1
        track = _make_track(x1=0.45, y1=0.0, x2=0.55, y2=0.05)
        crossings = engine.evaluate([track])
        assert len(crossings) == 1
        assert crossings[0].transition == "OUTSIDE"

    def test_reset_clears_state(self) -> None:
        engine = self._engine()
        engine.evaluate([_make_track()])
        engine.reset()
        assert len(engine._state) == 0

    def test_entry_then_exit_transitions(self) -> None:
        engine = self._engine()
        inside_track = _make_track(x1=0.3, y1=0.3, x2=0.5, y2=0.7)
        c1 = engine.evaluate([inside_track])
        assert c1[0].transition == "ENTERED"
        c2 = engine.evaluate([inside_track])
        assert c2[0].transition == "INSIDE"
        # Move track outside: foot at (0.5, 0.05)
        outside_track = _make_track(track_id=1, x1=0.45, y1=0.0, x2=0.55, y2=0.05)
        c3 = engine.evaluate([outside_track])
        assert c3[0].transition == "EXITED"

    def test_multiple_tracks_independent(self) -> None:
        engine = self._engine()
        tracks = [
            _make_track(track_id=1, x1=0.3, y1=0.3, x2=0.5, y2=0.7),
            _make_track(track_id=2, x1=0.3, y1=0.3, x2=0.5, y2=0.7),
        ]
        crossings = engine.evaluate(tracks)
        assert len(crossings) == 2

    def test_no_crossings_for_empty_tracks(self) -> None:
        engine = self._engine()
        assert engine.evaluate([]) == []

    def test_disabled_zone_not_evaluated(self) -> None:
        zone = _make_zone()
        zone.enabled = False
        engine = ZoneEngine([zone], ttl_seconds=60.0)
        crossings = engine.evaluate([_make_track()])
        assert crossings == []

    def test_no_zones_returns_empty(self) -> None:
        engine = ZoneEngine([], ttl_seconds=60.0)
        crossings = engine.evaluate([_make_track()])
        assert crossings == []
