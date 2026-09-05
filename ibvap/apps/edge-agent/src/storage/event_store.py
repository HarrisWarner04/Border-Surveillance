"""
SQLite event store.

Persists events, evidence, and alerts to a local SQLite database.
Uses SQLAlchemy Core for simplicity; no heavy ORM mapping needed here.

Failure policy:
  - Write failures are logged and counted in metrics.
  - They do NOT crash the video pipeline.
  - The caller decides whether to continue after a write failure.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from src.observability.logging import get_logger
from src.observability.metrics import metrics

try:
    from ibvap_contracts.models.alert import Alert
    from ibvap_contracts.models.event import Event
    from ibvap_contracts.models.evidence import Evidence
except ImportError:
    import pathlib as _p
    import sys
    sys.path.insert(0, str(_p.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.models.alert import Alert  # type: ignore[no-redef]
    from ibvap_contracts.models.event import Event  # type: ignore[no-redef]
    from ibvap_contracts.models.evidence import Evidence  # type: ignore[no-redef]

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    schema_version  TEXT NOT NULL DEFAULT '1.0',
    site_id         TEXT NOT NULL,
    camera_id       TEXT,
    event_type      TEXT NOT NULL,
    status          TEXT NOT NULL,
    timestamp_start TEXT NOT NULL,
    timestamp_end   TEXT,
    zone_id         TEXT,
    track_ids       TEXT,          -- JSON array
    risk_score      INTEGER,
    risk_level      TEXT,
    risk_json       TEXT,          -- full RiskResult JSON
    evidence_ids    TEXT,          -- JSON array
    model_versions  TEXT,          -- JSON object
    metadata        TEXT,          -- JSON object
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_camera_ts
    ON events (camera_id, timestamp_start);
CREATE INDEX IF NOT EXISTS idx_events_type_ts
    ON events (event_type, timestamp_start);
CREATE INDEX IF NOT EXISTS idx_events_status
    ON events (status, timestamp_start);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id     TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL REFERENCES events(event_id),
    kind            TEXT NOT NULL,
    storage_uri     TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    created_at      TEXT NOT NULL,
    retention_until TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_event
    ON evidence (event_id);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL REFERENCES events(event_id),
    channel         TEXT NOT NULL,
    priority        TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    resolved_at     TEXT,
    last_error      TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_event
    ON alerts (event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status
    ON alerts (status, created_at);
"""


# ---------------------------------------------------------------------------
# SQLiteEventStore
# ---------------------------------------------------------------------------


class SQLiteEventStore:
    """
    Lightweight SQLite persistence for edge-agent events, evidence, and alerts.

    Thread-safe: each call acquires its own connection from a connection-per-call
    pattern (SQLite handles WAL mode concurrency).
    """

    def __init__(self, db_path: str | Path = "./data/edge.db") -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Context manager for connections
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._path), timeout=10)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent read performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)
        logger.info("sqlite_schema_ready", path=str(self._path))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def upsert_event(self, event: Event) -> bool:
        """Insert or replace an event record. Returns True on success."""
        try:
            risk_score = None
            risk_level = None
            risk_json = None
            if event.risk is not None:
                risk_score = event.risk.score
                risk_level = event.risk.level.value
                risk_json = event.risk.model_dump_json()

            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events (
                        event_id, schema_version, site_id, camera_id,
                        event_type, status, timestamp_start, timestamp_end,
                        zone_id, track_ids, risk_score, risk_level, risk_json,
                        evidence_ids, model_versions, metadata,
                        created_at, updated_at
                    ) VALUES (
                        :event_id, :schema_version, :site_id, :camera_id,
                        :event_type, :status, :timestamp_start, :timestamp_end,
                        :zone_id, :track_ids, :risk_score, :risk_level, :risk_json,
                        :evidence_ids, :model_versions, :metadata,
                        :created_at, :updated_at
                    )
                    """,
                    {
                        "event_id": event.event_id,
                        "schema_version": event.schema_version,
                        "site_id": event.site_id,
                        "camera_id": event.camera_id,
                        "event_type": event.event_type.value,
                        "status": event.status.value,
                        "timestamp_start": event.timestamp_start.isoformat(),
                        "timestamp_end": event.timestamp_end.isoformat() if event.timestamp_end else None,
                        "zone_id": event.zone_id,
                        "track_ids": json.dumps(event.track_ids),
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "risk_json": risk_json,
                        "evidence_ids": json.dumps(event.evidence_ids),
                        "model_versions": json.dumps(event.model_versions),
                        "metadata": json.dumps(event.metadata),
                        "created_at": event.created_at.isoformat(),
                        "updated_at": event.updated_at.isoformat(),
                    },
                )
            return True
        except Exception as exc:
            metrics.db_write_failures_total.inc()
            logger.error("sqlite_upsert_event_failed", event_id=event.event_id, error=str(exc))
            return False

    def get_event(self, event_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_events(
        self,
        camera_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if camera_id:
            clauses.append("camera_id = ?")
            params.append(camera_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT * FROM events {where}
            ORDER BY timestamp_start DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def insert_evidence(self, evidence: Evidence) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO evidence (
                        evidence_id, event_id, kind, storage_uri,
                        sha256, size_bytes, created_at, retention_until
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence.evidence_id,
                        evidence.event_id,
                        evidence.kind.value,
                        evidence.storage_uri,
                        evidence.sha256,
                        evidence.size_bytes,
                        evidence.created_at.isoformat(),
                        evidence.retention_until.isoformat() if evidence.retention_until else None,
                    ),
                )
            return True
        except Exception as exc:
            metrics.db_write_failures_total.inc()
            logger.error("sqlite_insert_evidence_failed", evidence_id=evidence.evidence_id, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def insert_alert(self, alert: Alert) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO alerts (
                        alert_id, event_id, channel, priority, status,
                        created_at, acknowledged_at, acknowledged_by,
                        resolved_at, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert.alert_id,
                        alert.event_id,
                        alert.channel,
                        alert.priority.value,
                        alert.status.value,
                        alert.created_at.isoformat(),
                        alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                        alert.acknowledged_by,
                        alert.resolved_at.isoformat() if alert.resolved_at else None,
                        alert.last_error,
                    ),
                )
            return True
        except Exception as exc:
            metrics.db_write_failures_total.inc()
            logger.error("sqlite_insert_alert_failed", alert_id=alert.alert_id, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if the database is accessible."""
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
