"""
Evidence layer: snapshot capture, metadata JSON, SHA-256 checksum, atomic write.

Directory layout:
    evidence_root/
      YYYY/
        MM/
          DD/
            <event_id>/
              snapshot.jpg      (annotated frame)
              metadata.json     (event context)
              checksums.txt     (sha256 of each file)

Atomic write strategy:
  1. Write to a temp file (same directory)
  2. fsync
  3. Rename to final path
  This ensures readers never see a partial file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.observability.logging import get_logger
from src.observability.metrics import metrics

try:
    from ibvap_contracts.enums import EvidenceKind
    from ibvap_contracts.models.event import Event
    from ibvap_contracts.models.evidence import Evidence
except ImportError:
    import pathlib as _pathlib
    import sys
    sys.path.insert(0, str(_pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.enums import EvidenceKind  # type: ignore[no-redef]
    from ibvap_contracts.models.event import Event  # type: ignore[no-redef]
    from ibvap_contracts.models.evidence import Evidence  # type: ignore[no-redef]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> str:
    """
    Write bytes to path atomically.

    Returns the SHA-256 hex digest of the written data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    return hashlib.sha256(data).hexdigest()


def _event_dir(evidence_root: Path, event_id: str, ts: datetime) -> Path:
    """Return the date-organised directory for an event's evidence."""
    return evidence_root / ts.strftime("%Y") / ts.strftime("%m") / ts.strftime("%d") / event_id


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


def _annotate_frame(
    frame: np.ndarray,
    event: Event,
    track_id: int | None = None,
) -> np.ndarray:
    """Draw diagnostic overlay on the frame for the evidence snapshot."""
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Semi-transparent overlay strip at top
    overlay = annotated.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, annotated, 0.5, 0, annotated)

    # Text info
    cam_text = f"CAM: {event.camera_id or 'unknown'}"
    evt_text = f"EVENT: {event.event_type.value}"
    zone_text = f"ZONE: {event.zone_id or 'unknown'}"
    tid_text = f"TRACK: {track_id}" if track_id is not None else ""
    ts_text = event.timestamp_start.strftime("%Y-%m-%d %H:%M:%S UTC")

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(annotated, cam_text, (8, 16), font, 0.45, (255, 255, 255), 1)
    cv2.putText(annotated, evt_text, (8, 30), font, 0.45, (0, 80, 255), 1)
    cv2.putText(annotated, zone_text, (8, 44), font, 0.40, (200, 200, 200), 1)
    if tid_text:
        cv2.putText(annotated, tid_text, (w - 140, 16), font, 0.45, (0, 255, 255), 1)
    cv2.putText(annotated, ts_text, (w // 2 - 90, h - 8), font, 0.38, (200, 200, 200), 1)

    return annotated


# ---------------------------------------------------------------------------
# EvidenceStore
# ---------------------------------------------------------------------------


class EvidenceStore:
    """
    Captures and stores evidence for events.

    Responsibilities:
      - Annotate and write snapshot JPEG
      - Write metadata JSON
      - Write checksums.txt
      - Return Evidence domain objects
      - Increment failure metrics on write errors
    """

    def __init__(self, evidence_root: Path | str) -> None:
        self._root = Path(evidence_root)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def capture_snapshot(
        self,
        event: Event,
        frame: np.ndarray,
        track_id: int | None = None,
    ) -> Evidence | None:
        """
        Annotate the frame and write it as evidence for the event.

        Returns an Evidence object on success, None on failure.
        The event.evidence_ids list is NOT mutated here — the caller
        must attach the returned Evidence ID.
        """
        try:
            return self._write_snapshot(event, frame, track_id)
        except Exception as exc:
            metrics.evidence_write_failures_total.inc()
            logger.error(
                "evidence_snapshot_failed",
                event_id=event.event_id,
                error=str(exc),
            )
            return None

    def write_metadata(self, event: Event, extra: dict[str, Any] | None = None) -> Evidence | None:
        """Write a JSON metadata artifact for the event."""
        try:
            return self._write_metadata_json(event, extra or {})
        except Exception as exc:
            metrics.evidence_write_failures_total.inc()
            logger.error(
                "evidence_metadata_failed",
                event_id=event.event_id,
                error=str(exc),
            )
            return None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _write_snapshot(
        self,
        event: Event,
        frame: np.ndarray,
        track_id: int | None,
    ) -> Evidence:
        annotated = _annotate_frame(frame, event, track_id)
        _, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
        jpg_bytes = encoded.tobytes()

        event_dir = _event_dir(self._root, event.event_id, event.timestamp_start)
        dest = event_dir / "snapshot.jpg"
        sha256 = _atomic_write_bytes(dest, jpg_bytes)

        relative_uri = str(dest.relative_to(self._root))
        evidence_id = str(uuid.uuid4())

        logger.info(
            "evidence_snapshot_written",
            event_id=event.event_id,
            path=relative_uri,
            sha256=sha256[:12] + "...",
            size_bytes=len(jpg_bytes),
        )

        return Evidence(
            evidence_id=evidence_id,
            event_id=event.event_id,
            kind=EvidenceKind.SNAPSHOT,
            storage_uri=relative_uri,
            sha256=sha256,
            size_bytes=len(jpg_bytes),
            created_at=datetime.now(tz=UTC),
        )

    def _write_metadata_json(
        self,
        event: Event,
        extra: dict[str, Any],
    ) -> Evidence:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "camera_id": event.camera_id,
            "zone_id": event.zone_id,
            "event_type": event.event_type.value,
            "status": event.status.value,
            "timestamp_start": event.timestamp_start.isoformat(),
            "track_ids": event.track_ids,
            "model_versions": event.model_versions,
            "metadata": event.metadata,
            **extra,
        }
        json_bytes = json.dumps(payload, indent=2, default=str).encode("utf-8")

        event_dir = _event_dir(self._root, event.event_id, event.timestamp_start)
        dest = event_dir / "metadata.json"
        sha256 = _atomic_write_bytes(dest, json_bytes)

        relative_uri = str(dest.relative_to(self._root))
        evidence_id = str(uuid.uuid4())

        return Evidence(
            evidence_id=evidence_id,
            event_id=event.event_id,
            kind=EvidenceKind.METADATA,
            storage_uri=relative_uri,
            sha256=sha256,
            size_bytes=len(json_bytes),
            created_at=datetime.now(tz=UTC),
        )

    def write_checksums(self, event: Event, evidences: list[Evidence]) -> None:
        """Write a checksums.txt file listing all evidence files for the event."""
        try:
            lines = [f"{ev.sha256}  {Path(ev.storage_uri).name}" for ev in evidences]
            content = "\n".join(lines).encode("utf-8")
            event_dir = _event_dir(self._root, event.event_id, event.timestamp_start)
            dest = event_dir / "checksums.txt"
            _atomic_write_bytes(dest, content)
        except Exception as exc:
            logger.warning("evidence_checksums_failed", event_id=event.event_id, error=str(exc))
