"""
Events layer: intrusion detection, temporal confirmation, deduplication,
and canonical Event builder.

Core rules (from spec):
  1. OUTSIDE → INSIDE is an intrusion candidate.
  2. After confirmation_frames consecutive inside observations → CONFIRMED.
  3. While the same track stays INSIDE → no new event (dedup).
  4. INSIDE → OUTSIDE resolves the event.
  5. One event per (camera, track, zone, event_type) within an active window.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.geometry.zone_engine import ZoneCrossing
from src.observability.logging import get_logger
from src.observability.metrics import metrics

try:
    from ibvap_contracts.enums import EventStatus, EventType, ZoneType
    from ibvap_contracts.models.event import Event
except ImportError:
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.enums import EventStatus, EventType, ZoneType  # type: ignore[no-redef]
    from ibvap_contracts.models.event import Event  # type: ignore[no-redef]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Active intrusion tracking (per camera + track + zone)
# ---------------------------------------------------------------------------


@dataclass
class ActiveIntrusion:
    """Tracks an ongoing intrusion for one (camera, track, zone) combination."""

    event_id: str
    camera_id: str
    zone_id: str
    track_id: int
    event_type: EventType
    started_at: datetime
    confirmed: bool = False
    consecutive_frames: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# ---------------------------------------------------------------------------
# IntrusionEngine
# ---------------------------------------------------------------------------


class IntrusionEngine:
    """
    Evaluates ZoneCrossings from the ZoneEngine and emits canonical Events.

    Rules enforced:
      - confirmation_frames consecutive inside observations required before
        an event is emitted (reduces false positives from single-frame noise)
      - only one OPEN event per (camera, track_id, zone_id, event_type)
      - INSIDE→OUTSIDE resolves the open event
      - active intrusion states expire after ttl_seconds
    """

    def __init__(
        self,
        confirmation_frames: int = 3,
        ttl_seconds: float = 30.0,
        site_id: str = "site-demo-01",
        detector_version: str = "unknown",
        tracker_version: str = "bytetrack",
    ) -> None:
        self._confirmation = confirmation_frames
        self._ttl = ttl_seconds
        self._site_id = site_id
        self._detector_version = detector_version
        self._tracker_version = tracker_version
        # Key: (camera_id, track_id, zone_id) → ActiveIntrusion
        self._active: dict[tuple[str, int, str], ActiveIntrusion] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def process(self, crossings: list[ZoneCrossing]) -> list[Event]:
        """
        Process a batch of ZoneCrossings and return any newly confirmed Events.

        This is called once per processed frame.
        """
        self._expire_stale()
        events: list[Event] = []

        for crossing in crossings:
            # Determine event type based on zone type
            if crossing.zone.type == ZoneType.RESTRICTED:
                event_type = EventType.PERIMETER_INTRUSION
            elif crossing.zone.type == ZoneType.ENTRY:
                event_type = EventType.ZONE_ENTRY
            else:
                # Only restricted and entry zones generate events in Phase 1
                continue

            key = (crossing.camera_id, crossing.track_id, crossing.zone.id)
            active = self._active.get(key)

            if crossing.transition == "ENTERED" and active is None:
                active = ActiveIntrusion(
                    event_id=str(uuid.uuid4()),
                    camera_id=crossing.camera_id,
                    zone_id=crossing.zone.id,
                    track_id=crossing.track_id,
                    event_type=event_type,
                    started_at=crossing.timestamp,
                )
                self._active[key] = active

            if active is not None and crossing.transition in ("ENTERED", "INSIDE"):
                active.consecutive_frames = crossing.consecutive_inside_frames
                active.last_updated = crossing.timestamp

                if (
                    not active.confirmed
                    and active.consecutive_frames >= self._confirmation
                ):
                    active.confirmed = True
                    event = self._build_event(active, EventStatus.OPEN)
                    events.append(event)
                    metrics.intrusions_total.inc()
                    logger.info(
                        "intrusion_confirmed",
                        camera_id=crossing.camera_id,
                        zone_id=crossing.zone.id,
                        track_id=crossing.track_id,
                        event_id=active.event_id,
                        consecutive_frames=active.consecutive_frames,
                    )

            elif crossing.transition == "EXITED":
                if active is not None and active.confirmed:
                    # Resolve the open event
                    event = self._build_event(active, EventStatus.RESOLVED)
                    event.timestamp_end = crossing.timestamp
                    events.append(event)
                    logger.info(
                        "intrusion_resolved",
                        camera_id=crossing.camera_id,
                        zone_id=crossing.zone.id,
                        track_id=crossing.track_id,
                        event_id=active.event_id,
                    )
                if active is not None:
                    del self._active[key]

        return events

    def reset(self) -> None:
        """Clear all state. Call on camera reconnect."""
        self._active.clear()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_event(self, intrusion: ActiveIntrusion, status: EventStatus) -> Event:
        now = datetime.now(tz=UTC)
        return Event(
            event_id=intrusion.event_id,
            site_id=self._site_id,
            camera_id=intrusion.camera_id,
            event_type=intrusion.event_type,
            status=status,
            timestamp_start=intrusion.started_at,
            timestamp_end=None,
            zone_id=intrusion.zone_id,
            track_ids=[intrusion.track_id],
            risk=None,
            evidence_ids=[],
            model_versions={
                "detector": self._detector_version,
                "tracker": self._tracker_version,
            },
            metadata={
                "class_name": "person",
                "consecutive_frames": intrusion.consecutive_frames,
            },
            created_at=intrusion.started_at,
            updated_at=now,
        )

    def _expire_stale(self) -> None:
        now = datetime.now(tz=UTC)
        expired = [
            k for k, v in self._active.items()
            if (now - v.last_updated).total_seconds() > self._ttl
        ]
        for k in expired:
            del self._active[k]
        if expired:
            logger.debug("intrusion_states_expired", count=len(expired))
