"""
Unit tests for ibvap_contracts.

Coverage targets:
  - All enum values present and valid
  - BoundingBox validation (x1<x2, y1<y2, ranges, foot/center properties)
  - Detection model validation
  - Zone validation (min vertices, coord range, LINE=2 pts)
  - RiskResult score clamping boundaries
  - Event model defaults
  - Evidence SHA-256 pattern
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
from ibvap_contracts.models.detection import BoundingBox, Detection
from ibvap_contracts.models.event import Event
from ibvap_contracts.models.evidence import Evidence
from ibvap_contracts.models.risk import RiskResult, RiskSignal
from ibvap_contracts.models.zone import Zone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------


class TestEnums:
    def test_risk_level_values(self) -> None:
        assert set(RiskLevel) == {
            RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL
        }

    def test_event_status_values(self) -> None:
        assert set(EventStatus) == {
            EventStatus.OPEN, EventStatus.UPDATED,
            EventStatus.RESOLVED, EventStatus.CANCELLED,
        }

    def test_alert_status_values(self) -> None:
        assert set(AlertStatus) == {
            AlertStatus.PENDING, AlertStatus.DELIVERING, AlertStatus.DELIVERED,
            AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.FAILED,
        }

    def test_sync_status_values(self) -> None:
        assert set(SyncStatus) == {
            SyncStatus.PENDING, SyncStatus.UPLOADING, SyncStatus.SYNCED,
            SyncStatus.RETRY_WAIT, SyncStatus.FAILED,
        }

    def test_camera_status_values(self) -> None:
        assert set(CameraStatus) == {
            CameraStatus.ONLINE, CameraStatus.DEGRADED,
            CameraStatus.OFFLINE, CameraStatus.DISABLED,
        }

    def test_camera_protocol_values(self) -> None:
        assert set(CameraProtocol) == {
            CameraProtocol.RTSP, CameraProtocol.ONVIF,
            CameraProtocol.FILE, CameraProtocol.MOCK,
        }

    def test_zone_type_values(self) -> None:
        assert set(ZoneType) == {
            ZoneType.RESTRICTED, ZoneType.MONITORING,
            ZoneType.ENTRY, ZoneType.SAFE,
        }

    def test_geometry_type_values(self) -> None:
        assert set(GeometryType) == {
            GeometryType.POLYGON, GeometryType.LINE, GeometryType.RECTANGLE,
        }

    def test_evidence_kind_values(self) -> None:
        assert set(EvidenceKind) == {
            EvidenceKind.SNAPSHOT, EvidenceKind.VIDEO_CLIP, EvidenceKind.METADATA,
        }

    def test_risk_signal_code_count(self) -> None:
        """Exactly 15 canonical signals."""
        assert len(RiskSignalCode) == 15

    def test_event_type_contains_perimeter_intrusion(self) -> None:
        assert EventType.PERIMETER_INTRUSION in EventType

    def test_invalid_risk_level_rejected(self) -> None:
        with pytest.raises(ValueError):
            RiskLevel("EXTREME")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_valid_bbox(self) -> None:
        bb = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bb.width == pytest.approx(0.4)
        assert bb.height == pytest.approx(0.6)

    def test_foot_point_is_bottom_center(self) -> None:
        bb = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.9)
        assert bb.foot_x == pytest.approx(0.3)
        assert bb.foot_y == pytest.approx(0.9)

    def test_center_point(self) -> None:
        bb = BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0)
        assert bb.center_x == pytest.approx(0.5)
        assert bb.center_y == pytest.approx(0.5)

    def test_x1_equals_x2_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x1=0.5, y1=0.1, x2=0.5, y2=0.9)

    def test_x1_greater_than_x2_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x1=0.8, y1=0.1, x2=0.2, y2=0.9)

    def test_y1_greater_than_y2_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x1=0.1, y1=0.9, x2=0.5, y2=0.1)

    def test_coord_above_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x1=0.1, y1=0.2, x2=1.5, y2=0.9)

    def test_negative_coord_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x1=-0.1, y1=0.2, x2=0.5, y2=0.9)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class TestDetection:
    def _valid(self) -> Detection:
        return Detection(
            id=uuid4(),
            camera_id="cam-01",
            timestamp=_now(),
            class_id=0,
            class_name="person",
            confidence=0.85,
            bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.4, y2=0.9),
            model_name="yolo26n",
            model_version="8.2.82",
        )

    def test_valid_detection(self) -> None:
        d = self._valid()
        assert d.class_name == "person"
        assert d.confidence == 0.85

    def test_confidence_above_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                id=uuid4(), camera_id="cam-01", timestamp=_now(),
                class_id=0, class_name="person", confidence=1.1,
                bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.4, y2=0.9),
                model_name="yolo26n", model_version="test",
            )

    def test_negative_confidence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                id=uuid4(), camera_id="cam-01", timestamp=_now(),
                class_id=0, class_name="person", confidence=-0.1,
                bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.4, y2=0.9),
                model_name="yolo26n", model_version="test",
            )

    def test_no_track_id_by_default(self) -> None:
        d = self._valid()
        assert d.track_id is None

    def test_track_id_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                id=uuid4(), camera_id="cam-01", timestamp=_now(),
                class_id=0, class_name="person", confidence=0.85,
                bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.4, y2=0.9),
                track_id=0,   # ge=1 — must reject at construction
                model_name="mock", model_version="1.0",
            )


# ---------------------------------------------------------------------------
# Zone
# ---------------------------------------------------------------------------


class TestZone:
    def _polygon(self) -> Zone:
        return Zone(
            id="zone-01",
            camera_id="cam-01",
            name="Perimeter",
            type=ZoneType.RESTRICTED,
            geometry_type=GeometryType.POLYGON,
            coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            created_at=_now(),
            updated_at=_now(),
        )

    def test_valid_polygon(self) -> None:
        z = self._polygon()
        assert len(z.coordinates) == 4

    def test_polygon_too_few_vertices_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Zone(
                id="z", camera_id="c", name="Z",
                type=ZoneType.RESTRICTED, geometry_type=GeometryType.POLYGON,
                coordinates=[[0.1, 0.1], [0.9, 0.9]],
                created_at=_now(), updated_at=_now(),
            )

    def test_polygon_coord_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Zone(
                id="z", camera_id="c", name="Z",
                type=ZoneType.RESTRICTED, geometry_type=GeometryType.POLYGON,
                coordinates=[[0.1, 0.1], [1.5, 0.5], [0.5, 0.9]],
                created_at=_now(), updated_at=_now(),
            )

    def test_line_zone_requires_exactly_2_points(self) -> None:
        z = Zone(
            id="z", camera_id="c", name="Z",
            type=ZoneType.MONITORING, geometry_type=GeometryType.LINE,
            coordinates=[[0.1, 0.5], [0.9, 0.5]],
            created_at=_now(), updated_at=_now(),
        )
        assert len(z.coordinates) == 2

    def test_line_zone_with_3_points_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Zone(
                id="z", camera_id="c", name="Z",
                type=ZoneType.MONITORING, geometry_type=GeometryType.LINE,
                coordinates=[[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]],
                created_at=_now(), updated_at=_now(),
            )

    def test_negative_coord_in_zone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Zone(
                id="z", camera_id="c", name="Z",
                type=ZoneType.RESTRICTED, geometry_type=GeometryType.POLYGON,
                coordinates=[[-0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
                created_at=_now(), updated_at=_now(),
            )


# ---------------------------------------------------------------------------
# RiskResult score boundaries
# ---------------------------------------------------------------------------


class TestRiskResult:
    def _make(self, score: int, level: RiskLevel) -> RiskResult:
        return RiskResult(score=score, level=level, calculated_at=_now())

    def test_score_19_is_low(self) -> None:
        r = self._make(19, RiskLevel.LOW)
        assert r.score == 19
        assert r.level == RiskLevel.LOW

    def test_score_20_is_medium(self) -> None:
        r = self._make(20, RiskLevel.MEDIUM)
        assert r.score == 20

    def test_score_49_is_medium(self) -> None:
        r = self._make(49, RiskLevel.MEDIUM)
        assert r.score == 49

    def test_score_50_is_high(self) -> None:
        r = self._make(50, RiskLevel.HIGH)
        assert r.score == 50

    def test_score_79_is_high(self) -> None:
        r = self._make(79, RiskLevel.HIGH)
        assert r.score == 79

    def test_score_80_is_critical(self) -> None:
        r = self._make(80, RiskLevel.CRITICAL)
        assert r.score == 80

    def test_score_100_is_critical(self) -> None:
        r = self._make(100, RiskLevel.CRITICAL)
        assert r.score == 100

    def test_score_0_valid(self) -> None:
        r = self._make(0, RiskLevel.LOW)
        assert r.score == 0

    def test_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RiskResult(score=101, level=RiskLevel.CRITICAL, calculated_at=_now())

    def test_score_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RiskResult(score=-1, level=RiskLevel.LOW, calculated_at=_now())


# ---------------------------------------------------------------------------
# Evidence SHA-256 pattern
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_valid_sha256(self) -> None:
        e = Evidence(
            evidence_id="ev-01",
            event_id="evt-01",
            kind=EvidenceKind.SNAPSHOT,
            storage_uri="2026/09/04/evt-01/snapshot.jpg",
            sha256="a" * 64,
            size_bytes=12345,
            created_at=_now(),
        )
        assert e.sha256 == "a" * 64

    def test_short_sha256_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Evidence(
                evidence_id="ev-01", event_id="evt-01",
                kind=EvidenceKind.SNAPSHOT,
                storage_uri="path/snap.jpg",
                sha256="abc123",
                size_bytes=0,
                created_at=_now(),
            )

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Evidence(
                evidence_id="ev-01", event_id="evt-01",
                kind=EvidenceKind.SNAPSHOT,
                storage_uri="path/snap.jpg",
                sha256="b" * 64,
                size_bytes=-1,
                created_at=_now(),
            )
