# IBVAP — Core Surveillance Progress

## Current Phase
**Phase 1 — Core Surveillance (COMPLETE)**

## Environment
- OS: Windows 11 / Linux
- Python: 3.12.x
- PyTorch: install separately — see docs/setup.md
- CUDA: optional (CPU fallback implemented)
- GPU: optional
- Ultralytics: 8.2.82 (pinned in pyproject.toml)
- OpenCV: 4.10.0.84 (opencv-python-headless)

## Completed Steps

- [x] Repository audit
- [x] packages/contracts — canonical Pydantic models and enums
- [x] edge-agent/config — pydantic-settings, .env.example, zone YAML
- [x] camera layer — CameraConfig, FramePacket, BoundedFrameBuffer, MockSource, FileSource, RTSPSource (reconnect)
- [x] inference layer — Detector protocol, MockDetector, YOLO26Detector wrapper, make_detector factory
- [x] tracking layer — Tracker protocol, MockTracker, ByteTrackTracker, make_tracker factory
- [x] geometry layer — point_in_polygon, validate_polygon, foot_point, ZonePresenceState, ZoneEngine, load_zones_from_yaml
- [x] events layer — IntrusionEngine (temporal confirmation, dedup, OPEN/RESOLVED lifecycle)
- [x] evidence layer — EvidenceStore (annotated snapshot, metadata JSON, SHA-256, atomic write)
- [x] alerts layer — AlertSink protocol, ConsoleAlertSink, AlertCooldown, AlertDispatcher
- [x] storage layer — SQLiteEventStore (schema, upsert, list, evidence, alerts, health check)
- [x] observability — structlog JSON logging, in-process metrics registry, health state registry
- [x] main.py — CameraPipeline, FastAPI app, /health/live /health/ready /metrics, graceful shutdown
- [x] unit tests — geometry, intrusion transitions, MockDetector, MockTracker, AlertCooldown, EvidenceStore, SQLiteEventStore
- [x] integration tests — full pipeline: MockSource → Detect → Track → Zone → Event → Evidence → Store → Alert
- [x] scripts/generate_fixture_video.py — synthetic 120-frame demo_walk.mp4
- [x] scripts/verify_yolo26.py — model verification gate
- [x] scripts/test_rtsp.py — RTSP connectivity test
- [x] scripts/benchmark_detector.py — FPS/latency benchmark
- [x] models/manifest.yaml — model governance

## Current Blocker
None.

## Known Issues
None at this phase.

## Architecture Decisions Made
- Detector and tracker are behind Protocol interfaces — YOLO/ByteTrack are pluggable.
- MockDetector has three sequences: walk_through_zone, outside_only, static_inside.
- Confirmation requires 3 consecutive inside frames (configurable) before an event is emitted.
- Alert cooldown key: (camera_id, zone_id, track_id, event_type).
- CRITICAL alerts bypass cooldown by default.
- SQLite uses WAL mode for concurrent reads.
- Evidence uses atomic write (write temp → fsync → rename).
- Per-camera state (tracker, zone engine, intrusion engine) resets on every stream session change (reconnect).
- structlog is used throughout — JSON in production, coloured console in development.
- In-process metrics registry (no prometheus_client dependency for Phase 1).

## Last Verified Test Command
```powershell
# From ibvap/apps/edge-agent/
cd apps/edge-agent
pip install -e ".[dev]"
pip install -e "../../packages/contracts"
pytest tests/ -v --tb=short -m "unit or integration"
```

## Next Phase
Phase 2 — Camera + Video Pipeline:
  - FileSource integration test with synthetic fixture video
  - RTSP acceptance test (requires live camera)
  - ByteTrack live integration
  - Debug visualization overlay
  - FPS pacing validation
  - Failure injection tests (camera disconnect, bad frames)
