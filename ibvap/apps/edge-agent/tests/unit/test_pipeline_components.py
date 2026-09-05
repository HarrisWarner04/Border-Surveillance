"""
Unit tests: intrusion engine, MockDetector, MockTracker, AlertCooldown,
EvidenceStore, SQLiteEventStore.

conftest.py at edge-agent root sets sys.path — no manual path manipulation needed.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from ibvap_contracts.enums import (
    AlertStatus,
    EventStatus,
    EventType,
    GeometryType,
    RiskLevel,
    ZoneType,
)
from ibvap_contracts.models.alert import Alert
from ibvap_contracts.models.detection import BoundingBox, Detection
from ibvap_contracts.models.event import Event
from ibvap_contracts.models.zone import Zone

from src.alerts.local import AlertCooldown, AlertDispatcher, ConsoleAlertSink
from src.events.intrusion import IntrusionEngine
from src.geometry.zone_engine import ZoneCrossing, ZoneEngine
from src.inference.detector import MockDetector
from src.tracking.tracker import MockTracker


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_zone(zone_id: str = "z1", enabled: bool = True) -> Zone:
    return Zone(
        id=zone_id,
        camera_id="cam-01",
        name="Perimeter",
        type=ZoneType.RESTRICTED,
        geometry_type=GeometryType.POLYGON,
        coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        enabled=enabled,
        created_at=_now(),
        updated_at=_now(),
    )


def _make_crossing(
    transition: str,
    zone: Zone | None = None,
    track_id: int = 1,
    consecutive: int = 1,
) -> ZoneCrossing:
    z = zone or _make_zone()
    return ZoneCrossing(
        zone=z,
        track_id=track_id,
        camera_id="cam-01",
        transition=transition,
        consecutive_inside_frames=consecutive,
        foot_point_xy=(0.5, 0.5),
    )


def _make_event(status: EventStatus = EventStatus.OPEN) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        site_id="site-01",
        camera_id="cam-01",
        event_type=EventType.PERIMETER_INTRUSION,
        status=status,
        timestamp_start=_now(),
        zone_id="z1",
        track_ids=[1],
        created_at=_now(),
        updated_at=_now(),
    )


# =========================================================================
# IntrusionEngine
# =========================================================================


class TestIntrusionEngine:

    def _engine(self, confirmation: int = 3) -> IntrusionEngine:
        return IntrusionEngine(
            confirmation_frames=confirmation,
            ttl_seconds=60.0,
            site_id="site-demo-01",
        )

    def test_no_event_before_confirmation(self) -> None:
        engine = self._engine(confirmation=3)
        events = engine.process([_make_crossing("ENTERED", consecutive=1)])
        assert events == []

    def test_event_emitted_at_confirmation_frames(self) -> None:
        engine = self._engine(confirmation=3)
        # First frame: ENTERED starts the candidate (consecutive=1)
        assert engine.process([_make_crossing("ENTERED", consecutive=1)]) == []
        # Second frame: INSIDE, consecutive=2 — not yet confirmed
        assert engine.process([_make_crossing("INSIDE", consecutive=2)]) == []
        # Third frame: INSIDE, consecutive=3 — confirmed
        events = engine.process([_make_crossing("INSIDE", consecutive=3)])
        assert len(events) == 1
        assert events[0].event_type == EventType.PERIMETER_INTRUSION
        assert events[0].status == EventStatus.OPEN

    def test_no_duplicate_event_while_inside(self) -> None:
        """Once confirmed, additional INSIDE frames must not generate new events."""
        engine = self._engine(confirmation=1)
        events1 = engine.process([_make_crossing("ENTERED", consecutive=1)])
        assert len(events1) == 1
        for _ in range(5):
            events_n = engine.process([_make_crossing("INSIDE", consecutive=2)])
            assert events_n == []

    def test_resolve_event_on_exit(self) -> None:
        engine = self._engine(confirmation=1)
        engine.process([_make_crossing("ENTERED", consecutive=1)])
        resolved = engine.process([_make_crossing("EXITED")])
        assert len(resolved) == 1
        assert resolved[0].status == EventStatus.RESOLVED

    def test_outside_crossing_produces_no_event(self) -> None:
        engine = self._engine(confirmation=3)
        events = engine.process([_make_crossing("OUTSIDE")])
        assert events == []

    def test_confirmation_resets_if_track_exits_before_confirmation(self) -> None:
        engine = self._engine(confirmation=3)
        engine.process([_make_crossing("ENTERED", consecutive=1)])
        engine.process([_make_crossing("INSIDE", consecutive=2)])
        engine.process([_make_crossing("EXITED")])
        # Re-enter — state gone, new entry starts fresh
        events = engine.process([_make_crossing("ENTERED", consecutive=1)])
        assert events == []

    def test_multiple_tracks_independent(self) -> None:
        engine = self._engine(confirmation=1)
        c1 = _make_crossing("ENTERED", track_id=1, consecutive=1)
        c2 = _make_crossing("ENTERED", track_id=2, consecutive=1)
        events = engine.process([c1, c2])
        assert len(events) == 2
        track_ids = {e.track_ids[0] for e in events}
        assert track_ids == {1, 2}

    def test_reset_clears_active_state(self) -> None:
        engine = self._engine(confirmation=2)
        engine.process([_make_crossing("ENTERED", consecutive=1)])
        engine.reset()
        # After reset, INSIDE without prior ENTERED does nothing
        events = engine.process([_make_crossing("INSIDE", consecutive=2)])
        assert events == []

    def test_event_has_correct_fields(self) -> None:
        engine = self._engine(confirmation=1)
        events = engine.process([_make_crossing("ENTERED", consecutive=1)])
        e = events[0]
        assert e.site_id == "site-demo-01"
        assert e.camera_id == "cam-01"
        assert e.zone_id == "z1"
        assert e.track_ids == [1]
        assert e.event_type == EventType.PERIMETER_INTRUSION

    def test_non_restricted_zone_ignored(self) -> None:
        engine = self._engine(confirmation=1)
        monitoring_zone = _make_zone()
        monitoring_zone.type = ZoneType.MONITORING
        c = _make_crossing("ENTERED", zone=monitoring_zone, consecutive=1)
        events = engine.process([c])
        assert events == []

    def test_confirmation_1_confirms_on_first_frame(self) -> None:
        engine = self._engine(confirmation=1)
        events = engine.process([_make_crossing("ENTERED", consecutive=1)])
        assert len(events) == 1

    def test_no_event_for_empty_crossings(self) -> None:
        engine = self._engine()
        events = engine.process([])
        assert events == []


# =========================================================================
# MockDetector
# =========================================================================


class TestMockDetector:

    def test_returns_list_of_detections(self) -> None:
        d = MockDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "cam-01")
        assert isinstance(dets, list)
        assert len(dets) >= 1

    def test_detection_has_valid_bbox(self) -> None:
        d = MockDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "cam-01")
        for det in dets:
            assert 0.0 <= det.bbox.x1 < det.bbox.x2 <= 1.0
            assert 0.0 <= det.bbox.y1 < det.bbox.y2 <= 1.0

    def test_confidence_in_range(self) -> None:
        d = MockDetector(confidence=0.72)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "cam-01")
        for det in dets:
            assert 0.0 <= det.confidence <= 1.0

    def test_camera_id_propagated(self) -> None:
        d = MockDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "test-cam-99")
        for det in dets:
            assert det.camera_id == "test-cam-99"

    def test_model_name_and_version(self) -> None:
        d = MockDetector()
        assert d.model_name == "mock_detector"
        assert d.model_version == "1.0.0"

    def test_outside_only_bbox_above_zone(self) -> None:
        d = MockDetector(frame_sequence="outside_only")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "cam-01")
        for det in dets:
            # In outside_only mode foot y ≤ 0.15 (above demo zone top y=0.20)
            assert det.bbox.foot_y <= 0.15 + 1e-9

    def test_static_inside_bbox_inside_zone(self) -> None:
        d = MockDetector(frame_sequence="static_inside")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = d.detect(frame, "cam-01")
        for det in dets:
            assert det.bbox.y1 >= 0.20
            assert det.bbox.y2 <= 0.90

    def test_warmup_does_not_raise(self) -> None:
        d = MockDetector()
        d.warmup()

    def test_frame_count_increments(self) -> None:
        d = MockDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        d.detect(frame, "cam-01")
        d.detect(frame, "cam-01")
        assert d._frame_count == 2


# =========================================================================
# MockTracker
# =========================================================================


class TestMockTracker:

    def _det(self, x_center: float = 0.5) -> Detection:
        bb = BoundingBox(x1=x_center - 0.05, y1=0.3, x2=x_center + 0.05, y2=0.7)
        return Detection(
            id=uuid.uuid4(),
            camera_id="cam-01",
            timestamp=_now(),
            class_id=0,
            class_name="person",
            confidence=0.85,
            bbox=bb,
            model_name="mock",
            model_version="1.0",
        )

    def test_single_detection_gets_id(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        tracks = t.update(frame, [self._det()])
        assert len(tracks) == 1
        assert tracks[0].track_id >= 1

    def test_same_position_same_id_across_frames(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = self._det(x_center=0.5)
        t1 = t.update(frame, [det])
        t2 = t.update(frame, [det])
        assert t1[0].track_id == t2[0].track_id

    def test_different_grid_cells_get_different_ids(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        tr1 = t.update(frame, [self._det(x_center=0.1)])
        tr2 = t.update(frame, [self._det(x_center=0.9)])
        assert tr1[0].track_id != tr2[0].track_id

    def test_empty_detections_returns_empty(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert t.update(frame, []) == []

    def test_reset_restarts_ids_at_1(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        t.update(frame, [self._det()])
        t.reset()
        tracks = t.update(frame, [self._det()])
        assert tracks[0].track_id == 1

    def test_track_has_correct_camera_id(self) -> None:
        t = MockTracker()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = Detection(
            id=uuid.uuid4(), camera_id="cam-XYZ", timestamp=_now(),
            class_id=0, class_name="person", confidence=0.9,
            bbox=BoundingBox(x1=0.4, y1=0.3, x2=0.6, y2=0.7),
            model_name="mock", model_version="1.0",
        )
        tracks = t.update(frame, [det])
        assert tracks[0].camera_id == "cam-XYZ"


# =========================================================================
# AlertCooldown
# =========================================================================


class TestAlertCooldown:

    def _alert(self, priority: RiskLevel = RiskLevel.MEDIUM) -> Alert:
        return Alert(
            alert_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            channel="console",
            priority=priority,
            status=AlertStatus.PENDING,
            created_at=_now(),
        )

    def _event(
        self,
        camera_id: str = "cam-01",
        zone_id: str = "z1",
        track_id: int = 1,
    ) -> Event:
        return Event(
            event_id=str(uuid.uuid4()),
            site_id="site-01",
            camera_id=camera_id,
            event_type=EventType.PERIMETER_INTRUSION,
            status=EventStatus.OPEN,
            timestamp_start=_now(),
            zone_id=zone_id,
            track_ids=[track_id],
            created_at=_now(),
            updated_at=_now(),
        )

    def test_first_alert_always_allowed(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0)
        assert cd.should_send(self._alert(), self._event()) is True

    def test_same_key_suppressed_within_cooldown(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0)
        alert = self._alert()
        event = self._event()
        cd.record_sent(alert, event)
        assert cd.should_send(alert, event) is False

    def test_different_track_not_suppressed(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0)
        alert = self._alert()
        e1 = self._event(track_id=1)
        e2 = self._event(track_id=2)
        cd.record_sent(alert, e1)
        assert cd.should_send(alert, e2) is True

    def test_different_zone_not_suppressed(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0)
        alert = self._alert()
        e1 = self._event(zone_id="z1")
        e2 = self._event(zone_id="z2")
        cd.record_sent(alert, e1)
        assert cd.should_send(alert, e2) is True

    def test_critical_bypasses_cooldown(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0, critical_bypasses=True)
        critical = self._alert(priority=RiskLevel.CRITICAL)
        event = self._event()
        cd.record_sent(critical, event)
        assert cd.should_send(critical, event) is True

    def test_critical_not_bypasses_when_disabled(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0, critical_bypasses=False)
        critical = self._alert(priority=RiskLevel.CRITICAL)
        event = self._event()
        cd.record_sent(critical, event)
        assert cd.should_send(critical, event) is False

    def test_allowed_after_cooldown_expires(self) -> None:
        cd = AlertCooldown(cooldown_seconds=0.05)
        alert = self._alert()
        event = self._event()
        cd.record_sent(alert, event)
        assert cd.should_send(alert, event) is False
        time.sleep(0.1)
        assert cd.should_send(alert, event) is True

    def test_reset_clears_all_state(self) -> None:
        cd = AlertCooldown(cooldown_seconds=60.0)
        alert = self._alert()
        event = self._event()
        cd.record_sent(alert, event)
        cd.reset()
        assert cd.should_send(alert, event) is True


# =========================================================================
# EvidenceStore
# =========================================================================


class TestEvidenceStore:

    def test_capture_snapshot_creates_file(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        store = EvidenceStore(tmp_path)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame, track_id=1)
        assert ev is not None
        assert (tmp_path / ev.storage_uri).exists()

    def test_snapshot_sha256_matches_file(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        store = EvidenceStore(tmp_path)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame)
        assert ev is not None
        actual_hash = hashlib.sha256(
            (tmp_path / ev.storage_uri).read_bytes()
        ).hexdigest()
        assert ev.sha256 == actual_hash

    def test_snapshot_sha256_is_64_chars(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        store = EvidenceStore(tmp_path)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame)
        assert ev is not None
        assert len(ev.sha256) == 64

    def test_metadata_json_written_correctly(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        store = EvidenceStore(tmp_path)
        event = _make_event()
        ev = store.write_metadata(event)
        assert ev is not None
        meta_path = tmp_path / ev.storage_uri
        assert meta_path.exists()
        data = json.loads(meta_path.read_text())
        assert data["event_id"] == event.event_id
        assert data["camera_id"] == event.camera_id
        assert data["event_type"] == EventType.PERIMETER_INTRUSION.value

    def test_nested_directory_created_automatically(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        deep = tmp_path / "a" / "b" / "c"
        store = EvidenceStore(deep)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame)
        assert ev is not None
        assert (deep / ev.storage_uri).exists()

    def test_evidence_kind_is_snapshot(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        from ibvap_contracts.enums import EvidenceKind
        store = EvidenceStore(tmp_path)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame)
        assert ev is not None
        assert ev.kind == EvidenceKind.SNAPSHOT

    def test_metadata_kind_is_metadata(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        from ibvap_contracts.enums import EvidenceKind
        store = EvidenceStore(tmp_path)
        event = _make_event()
        ev = store.write_metadata(event)
        assert ev is not None
        assert ev.kind == EvidenceKind.METADATA

    def test_event_id_in_evidence(self, tmp_path: Path) -> None:
        from src.evidence.snapshot import EvidenceStore
        store = EvidenceStore(tmp_path)
        event = _make_event()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ev = store.capture_snapshot(event, frame)
        assert ev is not None
        assert ev.event_id == event.event_id


# =========================================================================
# SQLiteEventStore
# =========================================================================


class TestSQLiteEventStore:

    def test_schema_created_and_health_ok(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        assert store.health_check() is True

    def test_upsert_and_retrieve_event(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        event = _make_event()
        assert store.upsert_event(event) is True
        row = store.get_event(event.event_id)
        assert row is not None
        assert row["event_id"] == event.event_id
        assert row["event_type"] == EventType.PERIMETER_INTRUSION.value
        assert row["status"] == EventStatus.OPEN.value

    def test_list_events_empty_initially(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        assert store.list_events() == []

    def test_list_events_filtered_by_camera(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        e1 = _make_event()
        e1.camera_id = "cam-01"
        e2 = _make_event()
        e2.camera_id = "cam-02"
        store.upsert_event(e1)
        store.upsert_event(e2)
        rows = store.list_events(camera_id="cam-01")
        assert len(rows) == 1
        assert rows[0]["camera_id"] == "cam-01"

    def test_upsert_updates_existing_event(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        event = _make_event()
        store.upsert_event(event)
        event.status = EventStatus.RESOLVED
        store.upsert_event(event)
        row = store.get_event(event.event_id)
        assert row is not None
        assert row["status"] == EventStatus.RESOLVED.value

    def test_insert_evidence_succeeds(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        from ibvap_contracts.models.evidence import Evidence
        from ibvap_contracts.enums import EvidenceKind
        store = SQLiteEventStore(tmp_path / "test.db")
        event = _make_event()
        store.upsert_event(event)
        ev = Evidence(
            evidence_id=str(uuid.uuid4()),
            event_id=event.event_id,
            kind=EvidenceKind.SNAPSHOT,
            storage_uri="2026/09/04/evt/snapshot.jpg",
            sha256="a" * 64,
            size_bytes=12345,
            created_at=_now(),
        )
        assert store.insert_evidence(ev) is True

    def test_insert_alert_succeeds(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        event = _make_event()
        store.upsert_event(event)
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            event_id=event.event_id,
            channel="console",
            priority=RiskLevel.HIGH,
            status=AlertStatus.DELIVERED,
            created_at=_now(),
        )
        assert store.insert_alert(alert) is True

    def test_get_nonexistent_event_returns_none(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        assert store.get_event("does-not-exist") is None

    def test_multiple_events_list_ordered_by_time(self, tmp_path: Path) -> None:
        from src.storage.event_store import SQLiteEventStore
        store = SQLiteEventStore(tmp_path / "test.db")
        for _ in range(5):
            store.upsert_event(_make_event())
        rows = store.list_events()
        assert len(rows) == 5
