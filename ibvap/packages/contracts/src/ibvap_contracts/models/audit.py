"""AuditLog domain model. Schema version: 1.0"""

from datetime import datetime

from pydantic import BaseModel


class AuditLog(BaseModel):
    """Append-only record of privileged actions."""

    audit_id: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    timestamp: datetime
    source_ip: str | None = None
    metadata: dict[str, str | int | float | bool | None] = {}
