"""
Alerts layer: AlertSink protocol, ConsoleAlertSink, cooldown/throttle.

Design rules:
  - Event creation and alert delivery are separate concerns.
  - An event is always persisted.  An alert may be suppressed by cooldown.
  - Cooldown key: (camera_id, zone_id, track_id, event_type)
  - New CRITICAL events bypass the cooldown window.
  - Each AlertSink is independently pluggable via the protocol.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from src.observability.logging import get_logger
from src.observability.metrics import metrics

try:
    from ibvap_contracts.enums import AlertStatus, RiskLevel
    from ibvap_contracts.models.alert import Alert
    from ibvap_contracts.models.event import Event
except ImportError:
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.enums import AlertStatus, RiskLevel  # type: ignore[no-redef]
    from ibvap_contracts.models.alert import Alert  # type: ignore[no-redef]
    from ibvap_contracts.models.event import Event  # type: ignore[no-redef]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# AlertSink Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AlertSink(Protocol):
    """Interface that every alert channel must satisfy."""

    def send(self, alert: Alert, event: Event) -> bool:
        """
        Send the alert.

        Returns True on success, False on failure (non-raising).
        """
        ...


# ---------------------------------------------------------------------------
# ConsoleAlertSink — stdout, for development / demo
# ---------------------------------------------------------------------------


class ConsoleAlertSink:
    """Prints alerts to stdout. No external dependencies."""

    PRIORITY_COLOUR = {
        RiskLevel.LOW: "\033[37m",       # white
        RiskLevel.MEDIUM: "\033[33m",    # yellow
        RiskLevel.HIGH: "\033[91m",      # bright red
        RiskLevel.CRITICAL: "\033[31;1m", # bold red
    }
    RESET = "\033[0m"

    def send(self, alert: Alert, event: Event) -> bool:
        colour = self.PRIORITY_COLOUR.get(alert.priority, "")
        print(
            f"\n{colour}[ALERT] {event.event_type.value}{self.RESET}\n"
            f"  alert_id  = {alert.alert_id}\n"
            f"  event_id  = {alert.event_id}\n"
            f"  priority  = {alert.priority.value}\n"
            f"  camera    = {event.camera_id}\n"
            f"  zone      = {event.zone_id}\n"
            f"  track_ids = {event.track_ids}\n"
            f"  time      = {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"  channel   = {alert.channel}\n"
        )
        return True


# ---------------------------------------------------------------------------
# Alert Cooldown Manager
# ---------------------------------------------------------------------------


class AlertCooldown:
    """
    Tracks the last alert time per (camera_id, zone_id, track_id, event_type).

    Rules:
      - If an alert for the same key was sent within cooldown_seconds, suppress.
      - CRITICAL priority always bypasses cooldown (configurable).
      - Suppressed alerts are counted in metrics.
    """

    def __init__(
        self,
        cooldown_seconds: float = 10.0,
        critical_bypasses: bool = True,
    ) -> None:
        self._cooldown = cooldown_seconds
        self._critical_bypasses = critical_bypasses
        # key → monotonic time of last alert
        self._last_sent: dict[tuple[str, str | None, int | None, str], float] = {}

    def should_send(self, alert: Alert, event: Event) -> bool:
        """Return True if the alert should be dispatched."""
        if self._critical_bypasses and alert.priority == RiskLevel.CRITICAL:
            return True

        key = self._make_key(event)
        now = time.monotonic()
        last = self._last_sent.get(key)

        return last is None or (now - last) >= self._cooldown

    def record_sent(self, alert: Alert, event: Event) -> None:
        """Record that an alert was sent (update the cooldown timer)."""
        key = self._make_key(event)
        self._last_sent[key] = time.monotonic()

    def reset(self) -> None:
        """Clear all cooldown state. Call on camera reconnect if desired."""
        self._last_sent.clear()

    @staticmethod
    def _make_key(event: Event) -> tuple[str, str | None, int | None, str]:
        track_id = event.track_ids[0] if event.track_ids else None
        return (
            event.camera_id or "",
            event.zone_id,
            track_id,
            event.event_type.value,
        )


# ---------------------------------------------------------------------------
# AlertDispatcher
# ---------------------------------------------------------------------------


def _derive_risk_level(event: Event) -> RiskLevel:
    """Derive a priority from the event's risk result, or default to MEDIUM."""
    if event.risk is not None:
        return event.risk.level
    return RiskLevel.MEDIUM


class AlertDispatcher:
    """
    Builds Alert objects and dispatches them through registered sinks.

    Respects the cooldown window and tracks delivery metrics.
    """

    def __init__(
        self,
        sinks: list[AlertSink],
        cooldown: AlertCooldown | None = None,
    ) -> None:
        self._sinks = sinks
        self._cooldown = cooldown or AlertCooldown()

    def dispatch(self, event: Event) -> list[Alert]:
        """
        Create and dispatch alerts for the given event.

        Returns the list of Alert objects that were sent.
        """
        alerts: list[Alert] = []
        priority = _derive_risk_level(event)

        for sink in self._sinks:
            channel_name = type(sink).__name__

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                event_id=event.event_id,
                channel=channel_name,
                priority=priority,
                status=AlertStatus.PENDING,
                created_at=datetime.now(tz=UTC),
            )

            if not self._cooldown.should_send(alert, event):
                metrics.alerts_suppressed_total.inc()
                logger.debug(
                    "alert_suppressed_cooldown",
                    event_id=event.event_id,
                    channel=channel_name,
                    cooldown_seconds=self._cooldown._cooldown,
                )
                alert.status = AlertStatus.FAILED
                alert.last_error = "suppressed by cooldown"
                alerts.append(alert)
                continue

            try:
                success = sink.send(alert, event)
                if success:
                    alert.status = AlertStatus.DELIVERED
                    self._cooldown.record_sent(alert, event)
                    metrics.alerts_sent_total.inc()
                    logger.info(
                        "alert_sent",
                        event_id=event.event_id,
                        alert_id=alert.alert_id,
                        channel=channel_name,
                        priority=priority.value,
                    )
                else:
                    alert.status = AlertStatus.FAILED
                    alert.last_error = "sink returned False"
            except Exception as exc:
                alert.status = AlertStatus.FAILED
                alert.last_error = str(exc)
                logger.error(
                    "alert_send_error",
                    event_id=event.event_id,
                    channel=channel_name,
                    error=str(exc),
                )

            alerts.append(alert)

        return alerts
