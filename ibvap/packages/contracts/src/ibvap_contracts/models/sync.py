"""SyncEnvelope domain model. Schema version: 1.0"""

from datetime import datetime

from pydantic import BaseModel, Field

from ibvap_contracts.models.event import Event
from ibvap_contracts.models.evidence import Evidence


class SyncEnvelope(BaseModel):
    """
    Wire payload sent from edge to central API.
    idempotency_key must be treated as unique by the server.
    """

    schema_version: str = Field(default="1.0", frozen=True)
    sync_id: str
    site_id: str
    edge_device_id: str
    event_id: str
    idempotency_key: str
    payload_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    event: Event
    evidence_refs: list[Evidence] = Field(default_factory=list)
    created_at: datetime
