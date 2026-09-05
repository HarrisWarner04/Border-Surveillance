"""Risk domain models. Schema version: 1.0"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ibvap_contracts.enums import RiskLevel, RiskSignalCode


class RiskSignal(BaseModel):
    """A single contributing signal in the risk calculation."""

    code: RiskSignalCode
    score_contribution: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_event_id: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RiskResult(BaseModel):
    """
    The output of the risk engine for a single event.

    score is clamped to [0, 100].
    level is derived from canonical thresholds:
        0-19   LOW
        20-49  MEDIUM
        50-79  HIGH
        80-100 CRITICAL
    """

    score: int = Field(ge=0, le=100)
    level: RiskLevel
    signals: list[RiskSignal] = Field(default_factory=list)
    reason_codes: list[RiskSignalCode] = Field(default_factory=list)
    scoring_version: str = "rules-v1"
    calculated_at: datetime
