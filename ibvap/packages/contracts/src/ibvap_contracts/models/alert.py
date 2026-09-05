"""Alert domain model. Schema version: 1.0"""

from datetime import datetime

from pydantic import BaseModel

from ibvap_contracts.enums import AlertStatus, RiskLevel


class Alert(BaseModel):
    """
    An alert notification generated from an event.
    One event may produce multiple alerts (one per channel).
    """

    alert_id: str
    event_id: str
    channel: str
    priority: RiskLevel
    status: AlertStatus = AlertStatus.PENDING
    created_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    last_error: str | None = None

    model_config = {"frozen": False, "protected_namespaces": ()}
