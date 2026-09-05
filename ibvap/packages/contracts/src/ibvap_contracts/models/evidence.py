"""Evidence domain model. Schema version: 1.0"""

from datetime import datetime

from pydantic import BaseModel, Field

from ibvap_contracts.enums import EvidenceKind


class Evidence(BaseModel):
    """
    An evidence artifact attached to an event.

    storage_uri is a relative path under the configured evidence root.
    sha256 is the hex digest of the final file contents.
    """

    evidence_id: str
    event_id: str
    kind: EvidenceKind
    storage_uri: str
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    size_bytes: int = Field(ge=0)
    created_at: datetime
    retention_until: datetime | None = None

    model_config = {"frozen": False, "protected_namespaces": ()}
