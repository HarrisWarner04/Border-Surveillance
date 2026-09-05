"""
Integration tests: full pipeline end-to-end.

Uses only mock components (no model weights, no camera hardware).
conftest.py at edge-agent root sets sys.path.

Scenarios:
  1. walk_through_zone  → PERIMETER_INTRUSION event created
  2. walk_through_zone  → evidence files on disk
  3. walk_through_zone  → event persisted in SQLite
  4. static_inside      → NO alert spam (cooldown enforced)
  5. outside_only       → NO intrusion events
  6. walk_through_zone  → evidence_ids populated on event
  7. any               → DB health check passes after pipeline run
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from ibvap_contracts.enums import EventStatus, EventType, GeometryType, ZoneType
from ibvap_contracts.models.zone import Zone

from src.alerts.local import AlertCooldown, AlertDispatcher, ConsoleAlertSink
from src.events.intrusion import IntrusionEngine
from src.evidence.snapshot import EvidenceStore
from src.geometry.zone_engine import ZoneEngine
from src.inference.detector import MockDetector
from src.storage.event_store import SQLiteEventStore
from src.tracking.tracker import MockTracker


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_zone_inside() -> Zone:
    """Restricted zone that spans most of the frame."""
    return Zone(
        id="perimeter-01",
        camera_id="cam-01",
        name="Outer Perimeter",
        type=ZoneType.RESTRICTED,
        geometry_type=GeometryType.POLYGON,
        coordinates=[[0.05, 0.20], [0.95, 0.20], [0.95, 0.90], [0.05, 0.90]],
        created_at=_now(),
        updated_at=_now(),
    )


def _run_pipeline(
    zone: Zone,
    frame_sequence: str,
    n_frames: int,
    confirmation_frames: int,
    cooldown_seconds: float,
    tmp_path: Path,
) -> tuple[list, list, SQLiteEventStore]:
    """Run n_frames through the full mock pipeline. Returns (events, alerts, store)."""
    detector = MockDetector(frame_sequence=frame_sequence)
    tracker = MockTracker()
    zone_engine = ZoneEngine([zone], ttl_seconds=60.0)
    intrusion_engine = IntrusionEngine(
        confirmation_frames=confirmation_frames,
        ttl_seconds=60.0,
        site_id="site-demo-01",
    )
    store = SQLiteEventStore(tmp_path / "test_integration.db")
    evidence_store = EvidenceStore(tmp_path / "evidence")

    cooldown = AlertCooldown(cooldown_seconds=cooldown_seconds)
    dispatcher = AlertDispatcher(sinks=[ConsoleAlertSink()], cooldown=cooldown)

    all_events = []
    all_alerts = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    for _ in range(n_frames):
        detections = detector.detect(frame, "cam-01")
        tracks = tracker.update(frame, detections)
        crossings = zone_engine.evaluate(tracks)
        events = intrusion_engine.process(crossings)

        for event in events:
            if event.status == EventStatus.OPEN:
                track_id = event.track_ids[0] if event.track_ids else None
                ev_snap = evidence_store.capture_snapshot(event, frame, track_id)
                ev_meta = evidence_store.write_metadata(event)
                evidence_list = [e for e in [ev_snap, ev_meta] if e is not None]
                event.evidence_ids = [e.evidence_id for e in evidence_list]
                store.upsert_event(event)
                for ev in evidence_list:
                    store.insert_evidence(ev)
                sent = dispatcher.dispatch(event)
                all_alerts.extend(sent)
            elif event.status == EventStatus.RESOLVED:
                store.upsert_event(event)
            all_events.append(event)

    return all_events, all_alerts, store


# =========================================================================
# Integration scenarios
# =========================================================================


@pytest.mark.integration
def test_intrusion_event_created(tmp_path: Path) -> None:
    """walk_through_zone: at least one OPEN intrusion event after confirmation."""
    all_events, _, _ = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="walk_through_zone",
        n_frames=40,
        confirmation_frames=3,
        cooldown_seconds=999.0,
        tmp_path=tmp_path,
    )
    open_events = [e for e in all_events if e.status == EventStatus.OPEN]
    assert len(open_events) >= 1
    e = open_events[0]
    assert e.event_type == EventType.PERIMETER_INTRUSION
    assert e.camera_id == "cam-01"
    assert e.zone_id == "perimeter-01"
    assert len(e.track_ids) >= 1


@pytest.mark.integration
def test_evidence_files_created(tmp_path: Path) -> None:
    """Each confirmed intrusion must produce snapshot.jpg and metadata.json."""
    all_events, _, _ = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="walk_through_zone",
        n_frames=40,
        confirmation_frames=3,
        cooldown_seconds=999.0,
        tmp_path=tmp_path,
    )
    open_events = [e for e in all_events if e.status == EventStatus.OPEN]
    assert len(open_events) >= 1

    evidence_root = tmp_path / "evidence"
    assert evidence_root.exists()
    assert len(list(evidence_root.rglob("snapshot.jpg"))) >= 1
    assert len(list(evidence_root.rglob("metadata.json"))) >= 1


@pytest.mark.integration
def test_event_persisted_in_sqlite(tmp_path: Path) -> None:
    """Confirmed events must be queryable from the SQLite store."""
    all_events, _, store = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="walk_through_zone",
        n_frames=40,
        confirmation_frames=3,
        cooldown_seconds=999.0,
        tmp_path=tmp_path,
    )
    open_events = [e for e in all_events if e.status == EventStatus.OPEN]
    assert len(open_events) >= 1
    rows = store.list_events(camera_id="cam-01")
    assert len(rows) >= 1
    assert rows[0]["event_type"] == EventType.PERIMETER_INTRUSION.value


@pytest.mark.integration
def test_no_alert_spam_while_inside(tmp_path: Path) -> None:
    """
    Person stays continuously inside (static_inside).
    With cooldown_seconds=999 only 1 alert should be delivered.
    """
    _, all_alerts, _ = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="static_inside",
        n_frames=60,
        confirmation_frames=3,
        cooldown_seconds=999.0,
        tmp_path=tmp_path,
    )
    delivered = [a for a in all_alerts if a.status.value == "DELIVERED"]
    assert len(delivered) <= 1, (
        f"Expected ≤1 delivered alert with 999s cooldown, got {len(delivered)}"
    )


@pytest.mark.integration
def test_no_event_outside_zone(tmp_path: Path) -> None:
    """Person stays outside zone — zero intrusion events."""
    all_events, _, _ = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="outside_only",
        n_frames=30,
        confirmation_frames=3,
        cooldown_seconds=10.0,
        tmp_path=tmp_path,
    )
    open_events = [e for e in all_events if e.status == EventStatus.OPEN]
    assert open_events == [], f"Expected 0 events, got {len(open_events)}"


@pytest.mark.integration
def test_evidence_ids_attached_to_event(tmp_path: Path) -> None:
    """Events must have evidence_ids populated after capture."""
    all_events, _, _ = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="walk_through_zone",
        n_frames=40,
        confirmation_frames=3,
        cooldown_seconds=999.0,
        tmp_path=tmp_path,
    )
    open_events = [e for e in all_events if e.status == EventStatus.OPEN]
    assert len(open_events) >= 1
    assert len(open_events[0].evidence_ids) >= 1


@pytest.mark.integration
def test_db_health_after_pipeline(tmp_path: Path) -> None:
    """SQLite store must still be healthy after a full pipeline run."""
    _, _, store = _run_pipeline(
        zone=_make_zone_inside(),
        frame_sequence="walk_through_zone",
        n_frames=20,
        confirmation_frames=3,
        cooldown_seconds=10.0,
        tmp_path=tmp_path,
    )
    assert store.health_check() is True
