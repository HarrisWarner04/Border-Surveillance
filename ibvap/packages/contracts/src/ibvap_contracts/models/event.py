"""Event domain model. Schema version: 1.0"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ibvap_contracts.enums import EventStatus, EventType
from ibvap_contracts.models.risk import RiskResult


class Event(BaseModel):
    """
    A canonical surveillance event.

    One event represents one meaningful occurrence (e.g. a perimeter intrusion)
    regardless of how many frames were involved.  Use OPEN→UPDATED→RESOLVED
    lifecycle rather than creating duplicate events.
    """

    schema_version: str = Field(default="1.0", frozen=True)
    event_id: str
    site_id: str
    camera_id: str | None = None
    event_type: EventType
    status: EventStatus = EventStatus.OPEN
    timestamp_start: datetime
    timestamp_end: datetime | None = None
    zone_id: str | None = None
    track_ids: list[int] = Field(default_factory=list)
    risk: RiskResult | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    # Maps component name → version string
    model_versions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": False, "protected_namespaces": ()}
