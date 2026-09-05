"""
IBVAP Edge Agent — Main pipeline orchestrator.

Startup sequence:
  1. Load and validate configuration
  2. Configure structured logging
  3. Ensure data directories exist
  4. Initialise components
  5. Start per-camera pipeline thread
  6. Start FastAPI server (health + metrics + API endpoints)
  7. Wait for shutdown signal (Ctrl+C / SIGTERM)
  8. Graceful shutdown: stop camera → flush evidence → close DB

Per-camera pipeline loop (one thread per camera):
  Frame → Detect → Track → Zone → Event → Evidence → Store → Alert
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.alerts.local import AlertCooldown, AlertDispatcher, ConsoleAlertSink
from src.camera.models import CameraConfig
from src.camera.rtsp_client import make_camera_source
from src.config.settings import settings
from src.events.intrusion import IntrusionEngine
from src.evidence.snapshot import EvidenceStore
from src.geometry.zone_engine import ZoneEngine, load_zones_from_yaml
from src.inference.detector import make_detector
from src.observability.health import HealthStatus, health_registry
from src.observability.logging import configure_logging, get_logger
from src.observability.metrics import metrics
from src.storage.event_store import SQLiteEventStore
from src.tracking.tracker import make_tracker

try:
    from ibvap_contracts.enums import EventStatus
except ImportError:
    import pathlib as _p
    sys.path.insert(0, str(_p.Path(__file__).parents[4] / "packages" / "contracts" / "src"))
    from ibvap_contracts.enums import EventStatus  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Logging must be configured before any module-level loggers fire
# ---------------------------------------------------------------------------
configure_logging(log_level=settings.log_level, app_env=settings.app_env)
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-camera pipeline worker
# ---------------------------------------------------------------------------


class CameraPipeline:
    """
    Runs the full surveillance pipeline for a single camera in a dedicated thread.

    Components are fully isolated per camera.
    """

    def __init__(
        self,
        camera_config: CameraConfig,
        store: SQLiteEventStore,
        evidence_store: EvidenceStore,
        alert_dispatcher: AlertDispatcher,
        zone_config_path: str | None = None,
    ) -> None:
        self._config = camera_config
        self._store = store
        self._evidence_store = evidence_store
        self._alert_dispatcher = alert_dispatcher
        self._zone_config_path = zone_config_path
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Per-camera components (isolated state)
        self._detector = make_detector(
            model_name=settings.model_detector,
            model_path=str(settings.model_path),
            device=settings.model_device,
            confidence_threshold=settings.model_confidence_threshold,
            allowed_classes=settings.allowed_classes,
        )
        self._tracker = make_tracker(
            use_mock=(settings.model_detector == "mock"),
            model_path=str(settings.model_path),
            device=settings.model_device,
            allowed_classes=settings.allowed_classes,
        )

        # Check if tracker has a built-in detector (ByteTrackTracker Option A)
        # If so, skip the standalone detector to avoid double inference.
        self._tracker_has_detector = getattr(self._tracker, "has_builtin_detector", False)

        zones: list = []
        if zone_config_path and Path(zone_config_path).exists():
            try:
                zones = load_zones_from_yaml(zone_config_path)
                logger.info("zones_loaded", camera_id=camera_config.camera_id, count=len(zones))
            except Exception as exc:
                logger.error("zones_load_failed", path=zone_config_path, error=str(exc))

        self._zone_engine = ZoneEngine(zones, ttl_seconds=settings.track_state_ttl_seconds)
        self._intrusion_engine = IntrusionEngine(
            confirmation_frames=settings.intrusion_confirmation_frames,
            ttl_seconds=settings.track_state_ttl_seconds,
            site_id=settings.edge_site_id,
            detector_version=self._detector.model_version,
            tracker_version="bytetrack",
        )
        self._health = health_registry.get_or_create(camera_config.camera_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name=f"pipeline-{self._config.camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("pipeline_started", camera_id=self._config.camera_id)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("pipeline_stopped", camera_id=self._config.camera_id)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        source = make_camera_source(self._config)
        self._detector.warmup()

        last_detection_time = 0.0
        detection_interval = 1.0 / settings.detection_fps
        last_session_id: str | None = None
        frame_fps_tracker = _FPSTracker()

        try:
            for packet in source.frames():
                if self._stop_event.is_set():
                    break

                if not packet.is_valid:
                    self._health.mark_degraded("empty frame")
                    continue

                # Reset per-session state on reconnect
                if packet.session_id != last_session_id:
                    logger.info(
                        "pipeline_session_reset",
                        camera_id=self._config.camera_id,
                        session_id=packet.session_id,
                    )
                    self._tracker.reset()
                    self._zone_engine.reset()
                    self._intrusion_engine.reset()
                    last_session_id = packet.session_id
                    self._health.mark_connected(packet.session_id)

                frame = packet.image  # type: ignore[assignment]
                self._health.mark_frame(fps=frame_fps_tracker.tick())

                # Frame pacing — only run detection at target fps
                now = time.monotonic()
                if (now - last_detection_time) < detection_interval:
                    continue
                last_detection_time = now

                pipeline_t0 = time.monotonic()
                self._process_frame(frame, packet)
                pipeline_ms = (time.monotonic() - pipeline_t0) * 1000
                metrics.pipeline_latency_ms.observe(pipeline_ms)

        except Exception as exc:
            logger.error(
                "pipeline_fatal_error",
                camera_id=self._config.camera_id,
                error=str(exc),
                exc_info=True,
            )
            self._health.mark_offline(str(exc))
        finally:
            source.stop()

    def _process_frame(self, frame: np.ndarray, packet: object) -> None:
        camera_id = self._config.camera_id

        if self._tracker_has_detector:
            # Option A: ByteTrackTracker combines detection+tracking in one YOLO call.
            # Pass a minimal detection list for camera_id extraction only.
            import uuid
            from datetime import datetime

            from ibvap_contracts.models.detection import BoundingBox, Detection
            stub_det = Detection(
                id=uuid.uuid4(),
                camera_id=camera_id,
                timestamp=datetime.now(tz=UTC),
                class_id=0, class_name="stub", confidence=0.0,
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=0.01, y2=0.01),
                model_name="stub", model_version="0",
            )
            tracks = self._tracker.update(frame, [stub_det])
            # No separate detection step — tracker did it
        else:
            # Standard path: Detector → Tracker
            # 1. Detect
            detections = self._detector.detect(frame, camera_id)
            # 2. Track
            tracks = self._tracker.update(frame, detections)

        # 3. Zone evaluation
        crossings = self._zone_engine.evaluate(tracks)

        # 4. Intrusion events
        events = self._intrusion_engine.process(crossings)

        # 5. For each new/resolved event: evidence → store → alert
        for event in events:
            if event.status == EventStatus.OPEN:
                # Capture snapshot
                track_id = event.track_ids[0] if event.track_ids else None
                ev_snapshot = self._evidence_store.capture_snapshot(event, frame, track_id)
                ev_metadata = self._evidence_store.write_metadata(event)

                # Attach evidence IDs to event
                evidence_list = [e for e in [ev_snapshot, ev_metadata] if e is not None]
                event.evidence_ids = [e.evidence_id for e in evidence_list]

                # Persist event
                self._store.upsert_event(event)

                # Persist evidence
                for ev in evidence_list:
                    self._store.insert_evidence(ev)

                if evidence_list:
                    self._evidence_store.write_checksums(event, evidence_list)

                # Dispatch alerts
                alerts = self._alert_dispatcher.dispatch(event)
                for alert in alerts:
                    self._store.insert_alert(alert)

            elif event.status == EventStatus.RESOLVED:
                # Update the resolved state in DB
                self._store.upsert_event(event)


class _FPSTracker:
    """Simple rolling FPS estimator using deque for bounded memory."""

    def __init__(self, window: int = 30) -> None:
        self._times: deque[float] = deque(maxlen=window)

    def tick(self) -> float:
        now = time.monotonic()
        self._times.append(now)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

_store: SQLiteEventStore | None = None
_pipeline: CameraPipeline | None = None


def _extract_db_path(database_url: str) -> str:
    """Extract the filesystem path from a SQLite database URL safely."""
    # Handle both "sqlite+aiosqlite:///" and "sqlite:///" prefixes
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            return database_url[len(prefix):]
    # Fallback: treat the whole string as a path
    return database_url


def init_components() -> None:
    """Initialise all singletons (store, pipeline, etc.). Idempotent."""
    global _store, _pipeline
    if _store is not None and _pipeline is not None:
        return

    settings.ensure_dirs()
    logger.info(
        "edge_agent_starting",
        site_id=settings.edge_site_id,
        device_id=settings.edge_device_id,
        env=settings.app_env,
        detector=settings.model_detector,
    )

    _store = SQLiteEventStore(_extract_db_path(settings.edge_database_url))

    evidence_store = EvidenceStore(settings.edge_media_dir)
    cooldown = AlertCooldown(cooldown_seconds=settings.intrusion_alert_cooldown_seconds)
    dispatcher = AlertDispatcher(
        sinks=[ConsoleAlertSink()],
        cooldown=cooldown,
    )

    import os

    from pydantic import SecretStr

    # Determine protocol: mock detector → MOCK, else use env or default to FILE
    protocol_str = os.environ.get("CAMERA_0_PROTOCOL", "FILE")
    if settings.model_detector == "mock":
        protocol_str = "MOCK"

    cam_config = CameraConfig(
        camera_id=os.environ.get("CAMERA_0_ID", "demo-camera-01"),
        name=os.environ.get("CAMERA_0_NAME", "Demo Perimeter Camera"),
        protocol=protocol_str,  # type: ignore[arg-type]
        stream_uri=SecretStr(os.environ.get("CAMERA_0_STREAM_URI", "")),
        enabled=True,
        target_fps=settings.detection_fps,
    )

    # Locate zone configuration file robustly
    zone_base = Path(__file__).resolve().parent.parent / "configs" / "zones" / "demo-camera-01.yaml"
    zone_path = str(zone_base) if zone_base.exists() else "configs/zones/demo-camera-01.yaml"

    _pipeline = CameraPipeline(
        camera_config=cam_config,
        store=_store,
        evidence_store=evidence_store,
        alert_dispatcher=dispatcher,
        zone_config_path=zone_path,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Modern FastAPI lifespan handler — replaces deprecated on_event()."""
    init_components()

    if _pipeline is not None:
        _pipeline.start()
        logger.info("edge_agent_ready", port=settings.edge_api_port)

    yield

    if _pipeline is not None:
        logger.info("edge_agent_shutdown_start")
        _pipeline.stop()
        logger.info("edge_agent_shutdown_complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="IBVAP Edge Agent",
    version="0.1.0",
    description="Intelligent Border Video Analytics Platform — Edge Surveillance Agent",
    lifespan=lifespan,
)


@app.get("/health/live", tags=["health"])
def health_live() -> JSONResponse:
    """Liveness probe: returns 200 if the process is running."""
    return JSONResponse({"status": "ok"})


@app.get("/health/ready", tags=["health"])
def health_ready() -> JSONResponse:
    """Readiness probe: returns 200 if at least one camera is healthy/degraded."""
    h = health_registry.overall_status()
    code = 200 if h in (HealthStatus.HEALTHY, HealthStatus.DEGRADED) else 503
    return JSONResponse(health_registry.to_dict(), status_code=code)


@app.get("/metrics", tags=["observability"])
def get_metrics() -> JSONResponse:
    """Prometheus-compatible metrics snapshot."""
    return JSONResponse(metrics.snapshot())


@app.get("/api/v1/events", tags=["events"])
def list_events(
    camera_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    store = _get_store()
    rows = store.list_events(camera_id=camera_id, event_type=event_type, limit=limit, offset=offset)
    return JSONResponse({"events": rows, "count": len(rows)})


def _get_store() -> SQLiteEventStore:
    """Lazily return the singleton SQLiteEventStore."""
    init_components()
    return _store  # type: ignore[return-value]


def build_app() -> FastAPI:
    """Initialise all singletons and return the configured FastAPI app."""
    init_components()
    return app


def main() -> None:
    """CLI entry point."""
    app_instance = build_app()

    # Handle SIGTERM for Docker / process managers
    def _sigterm_handler(sig: int, frame: object) -> None:
        logger.info("sigterm_received")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    uvicorn.run(
        app_instance,
        host="0.0.0.0",
        port=settings.edge_api_port,
        log_config=None,  # structlog handles logging
    )


if __name__ == "__main__":
    main()
