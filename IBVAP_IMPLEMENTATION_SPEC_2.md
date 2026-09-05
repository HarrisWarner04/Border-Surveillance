# IBVAP — Intelligent Border Video Analytics Platform
## Production-Level Prototype Implementation Specification for Agentic AI Developers

**Document type:** Master implementation specification

---

# 0A. SPEC DETERMINISM / SINGLE SOURCE OF TRUTH

This section overrides any less-specific wording elsewhere in this document.

## Canonical contracts

`packages/contracts` is the **single source of truth** for all cross-service contracts.

The following must be defined once and imported/reused everywhere:

- domain enums
- event taxonomy
- risk levels
- risk signal identifiers
- Pydantic/domain DTOs
- JSON Schemas
- API request/response models
- WebSocket event payloads
- sync envelopes

Do **not** redefine these schemas independently in `edge-agent`, `central-api`, or `dashboard`.

When a contract changes:

1. update the canonical contract
2. update schema version if wire compatibility changes
3. regenerate dependent clients/types
4. run contract tests
5. update migrations if persistence changes
6. document the change

## Canonical enum values

### RiskLevel

```text
LOW
MEDIUM
HIGH
CRITICAL
```

### EventStatus

```text
OPEN
UPDATED
RESOLVED
CANCELLED
```

### AlertStatus

```text
PENDING
DELIVERING
DELIVERED
ACKNOWLEDGED
RESOLVED
FAILED
```

### SyncStatus

```text
PENDING
UPLOADING
SYNCED
RETRY_WAIT
FAILED
```

### CameraStatus

```text
ONLINE
DEGRADED
OFFLINE
DISABLED
```

### Event taxonomy

The event taxonomy in Section 13 is canonical. It must be represented as an enum/string-literal union in `packages/contracts` and imported by every service.

## Progress state is also canonical

The repository must contain:

```text
PROGRESS.md
.agent/state.json
```

The agent must read both before starting meaningful work and update both before ending a work session.

`PROGRESS.md` is the human-readable project state.

`.agent/state.json` is machine-readable execution state.

---

# 0B. VERSION / TOOLCHAIN BASELINE

The baseline is intentionally conservative for ML compatibility and reproducibility.

| Component | Baseline |
|---|---|
| Python | **3.12.14** |
| Node.js | **24.x LTS** |
| React | **19.2.x** |
| TypeScript | **5.x**, exact version locked in `package-lock.json`/`pnpm-lock.yaml` |
| PostgreSQL | **17.11** |
| Redis | **7.x**, exact image tag pinned in Compose |
| Docker Engine | **27.x or newer**, exact CI runner documented |
| Docker Compose | **v2.x** |
| FastAPI | **0.1xx**, exact resolved version committed in Python lockfile |
| Pydantic | **2.x**, exact resolved version committed in Python lockfile |
| Pytest | **8.x**, exact resolved version committed in Python lockfile |
| Vite/Next.js | choose one; exact major/minor committed and documented |
| Playwright | **1.x**, exact resolved version committed in lockfile |

### Pinning rule

Major/minor baselines above are compatibility targets. **All application dependencies must be resolved and locked to exact versions in the repository lockfiles.**

Never use:
- `latest`
- floating Docker tags such as `postgres:latest`
- unbounded dependency ranges
- runtime package installation without a lockfile

For container images, pin a concrete image tag. For security-sensitive base images, also record the image digest when practical.

Python 3.12.14 is used instead of 3.14 for the prototype baseline because the computer-vision/ML ecosystem may lag the newest Python feature release. Python 3.12.14 is a current security release, while Python 3.14 is the latest feature series.

Node 24.x is the preferred Node baseline because it is an LTS release. React 19.2.x is the current React major/minor baseline. PostgreSQL 17.11 is the selected central-database baseline for compatibility and long support runway.

---

# 0C. CROSS-SERVICE CONTRACT VERSIONING

Every wire contract must carry a schema version.

Example:

```json
{
  "schema_version": "1.0"
}
```

For breaking changes:

```text
1.0 → 2.0
```

For additive backward-compatible changes:

```text
1.0 → 1.1
```

The edge agent must remain able to process the current central API contract during the supported compatibility window.

Contract tests must verify:
- required fields
- enum values
- nullable fields
- backward compatibility
- unknown-field behavior
- idempotency semantics

  
**Project:** Smart India Hackathon 2026 — Software Problem Statement #187  
**Official problem statement:** **AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure.**  
**Organization:** Ministry of Home Affairs  
**Project codename:** `IBVAP`  
**Primary objective:** Build a production-grade prototype that demonstrates intelligent surveillance using existing CCTV, with edge-first processing, offline operation, contextual risk scoring, local alerts, and secure synchronization with a central command dashboard.

---

## 1. READ THIS FIRST — AGENT OPERATING CONTRACT

You are an **agentic software-development AI** responsible for implementing IBVAP.

Do not redesign the project into a generic cloud CCTV application.

Preserve these non-negotiable principles:

1. **Existing CCTV first.** The system must accept existing camera/DVR/NVR streams rather than requiring replacement smart cameras.
2. **Edge first.** Core detection, tracking, event generation, and risk evaluation must work locally.
3. **Offline capable.** Loss of internet connectivity must not stop surveillance or local alerting.
4. **Event driven.** Do not continuously upload all video to the cloud by default. Store locally and synchronize important events.
5. **Context aware.** Do not trigger a critical alert from a single weak signal when multiple contextual signals can be correlated.
6. **Human in the loop.** AI assists operators; it must expose evidence, reasons, confidence, and event history.
7. **Secure by default.** Authentication, authorization, encryption, audit logging, and controlled data retention are part of the system design.
8. **Prototype realism.** Every major subsystem must be runnable locally with simulated/sample video before hardware deployment.
9. **Production engineering.** Use typed contracts, structured logging, health checks, configuration management, database migrations, tests, containerization, and graceful failure handling.
10. **No fabricated performance claims.** Accuracy, latency, false-alarm reduction, throughput, and other metrics must be measured by the implemented test suite or clearly labelled as targets.

### Agent behavior

Before changing architecture:
- Inspect repository structure.
- Inspect existing code and configuration.
- Preserve working functionality.
- Prefer small, testable modules.
- Avoid large monolithic files.
- Add tests with implementation.
- Update documentation when behavior or API contracts change.
- Never hardcode secrets.
- Never commit local credentials, private keys, or surveillance data.
- Ask for clarification only when a decision is genuinely blocking; otherwise choose a sensible documented default and continue.

---

# 2. PROJECT CONTEXT

## 2.1 Official SIH problem

The project is based on SIH 2026 Problem Statement #187 from the Ministry of Home Affairs:

> **AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure.**

The supplied SIH problem-statement document lists it as a **Software** problem with a 10 September 2026 institute-level idea-submission deadline.

The official requirement is the source of truth for the problem framing. The architecture and engineering enhancements in this document are our proposed solution.

---

# 3. PRODUCT VISION

IBVAP converts existing heterogeneous CCTV infrastructure into an intelligent, distributed surveillance network.

### One-line product definition

> **IBVAP is an offline-first edge-AI video analytics platform that receives existing CCTV streams, detects and tracks people/vehicles/objects, analyzes behavior and context, correlates events across cameras and time, calculates risk, triggers local responses, stores evidence locally, and securely synchronizes important events with a central command center whenever connectivity is available.**

### Core differentiator

> **We do not replace CCTV. We make existing CCTV intelligent.**

### Operational differentiator

> **Even when the internet goes down, local security intelligence continues running.**

### Intelligence differentiator

> **We do not stop at object detection; we correlate context and prioritize threats using a risk engine.**

---

# 4. PROBLEM WE ARE SOLVING

Existing CCTV systems are often excellent at recording video but weak at continuously understanding it.

For remote and border environments, additional constraints exist:

- large geographical coverage
- remote/forest terrain
- unreliable internet
- intermittent network access
- heterogeneous camera infrastructure
- human operators cannot watch every feed continuously
- cloud-only analytics can fail during outages
- continuously transmitting video consumes bandwidth
- valuable events can be buried in hours of footage

IBVAP addresses these issues using local AI, event-based intelligence, local response, and eventual synchronization.

---

# 5. PRODUCT GOALS

## 5.1 Primary goals

### G1 — Existing infrastructure integration
Connect to:
- RTSP camera streams
- ONVIF-capable IP cameras where practical
- DVR/NVR stream outputs
- local video files for development/demo
- simulated streams for testing

### G2 — Real-time edge analytics
Support:
- object detection
- multi-object tracking
- configurable zones
- intrusion/crossing detection
- dwell/loitering detection
- basic suspicious-activity rules
- event creation

### G3 — Risk intelligence
Correlate:
- object detection
- tracking
- time
- location/zone
- motion/behavior
- watchlists
- repeated events
- optional identity/vehicle signals

into a risk score and priority level.

### G4 — Local response
Generate:
- dashboard alerts
- local operator notifications
- configurable webhook notifications
- optional siren/relay adapter
- optional online messaging adapter

### G5 — Offline operation
Continue core surveillance when network access is unavailable.

### G6 — Store-and-forward
Persist events locally and synchronize them after connectivity returns.

### G7 — Central command
Provide:
- multi-site dashboard
- map
- event search
- event playback
- alert handling
- reports
- audit trail
- system health

---

# 6. NON-GOALS FOR THE FIRST PROTOTYPE

Do **not** make these mandatory for the MVP:

- nation-wide production deployment
- full-blown blockchain network
- autonomous law-enforcement decision making
- continuous cloud video streaming
- perfect face recognition in all conditions
- complex satellite integration
- fully autonomous patrol deployment
- every possible activity-recognition model
- every possible AI model in one pipeline

These can be future extensions.

---

# 7. MVP DEFINITION

The first production-level prototype is successful when the following scenario works end-to-end:

```text
Sample/RTSP CCTV
    ↓
Video ingestion
    ↓
Object detector
    ↓
Multi-object tracker
    ↓
Virtual zone / intrusion rule
    ↓
Context + risk engine
    ↓
Event created
    ↓
Local database
    ↓
Dashboard alert
    ↓
Network disconnected
    ↓
Detection and local alerts still continue
    ↓
Network restored
    ↓
Queued event synchronizes
    ↓
Central dashboard shows synchronized event
```

### MVP must demonstrate

- at least one live/simulated camera
- person/vehicle detection
- persistent track IDs
- configurable restricted zone
- intrusion event
- risk score
- local event storage
- event snapshot
- event clip
- dashboard
- offline queue
- synchronization after reconnect
- audit log
- health endpoints
- automated tests

---

# 8. REFERENCE SYSTEM ARCHITECTURE

```text
                    ┌─────────────────────────────┐
                    │       EXISTING CCTV         │
                    │ IP / Analog / DVR / NVR     │
                    └──────────────┬──────────────┘
                                   │
                              RTSP / ONVIF
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │     VIDEO INGESTION         │
                    │ GStreamer / FFmpeg /         │
                    │ DeepStream / OpenCV         │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │       EDGE AI ENGINE        │
                    │                             │
                    │ Detection                   │
                    │ Tracking                    │
                    │ Zone analytics              │
                    │ Behavior rules              │
                    │ Optional identity / ANPR    │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │        EVENT ENGINE         │
                    │ Normalize + deduplicate     │
                    │ + enrich events             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │         RISK ENGINE          │
                    │ Rules + context + ML        │
                    │ temporal/cross-camera       │
                    │ correlation                 │
                    └──────────────┬──────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
          ┌───────────────────┐       ┌───────────────────┐
          │ LOCAL RESPONSE    │       │ LOCAL STORAGE     │
          │ Dashboard alert   │       │ SQLite/Postgres   │
          │ Siren/relay       │       │ snapshots/clips   │
          │ Webhook           │       │ logs/audit        │
          └────────┬──────────┘       └─────────┬─────────┘
                   │                            │
                   └────────────┬───────────────┘
                                ▼
                    ┌─────────────────────────────┐
                    │     SYNC / OUTBOX LAYER     │
                    │ Retry + backoff + checksum  │
                    │ Store-and-forward            │
                    └──────────────┬──────────────┘
                                   │
                         when connectivity exists
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │     CENTRAL API / HQ        │
                    │ FastAPI + DB + object store │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │      COMMAND DASHBOARD      │
                    │ React + map + alerts +      │
                    │ playback + reporting        │
                    └─────────────────────────────┘
```

---

# 9. REPOSITORY STRUCTURE

Use a modular monorepo.

```text
ibvap/
├── README.md
├── PROJECT_MEMORY.md
├── IMPLEMENTATION_SPEC.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
│
├── apps/
│   ├── edge-agent/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── config/
│   │   │   ├── ingestion/
│   │   │   ├── pipelines/
│   │   │   ├── inference/
│   │   │   ├── tracking/
│   │   │   ├── analytics/
│   │   │   ├── events/
│   │   │   ├── risk/
│   │   │   ├── storage/
│   │   │   ├── sync/
│   │   │   ├── notifications/
│   │   │   ├── health/
│   │   │   └── telemetry/
│   │   └── tests/
│   │
│   ├── central-api/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── auth/
│   │   │   ├── sites/
│   │   │   ├── cameras/
│   │   │   ├── events/
│   │   │   ├── alerts/
│   │   │   ├── sync/
│   │   │   ├── reports/
│   │   │   ├── audit/
│   │   │   ├── db/
│   │   │   └── telemetry/
│   │   └── tests/
│   │
│   └── dashboard/
│       ├── package.json
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── features/
│       │   │   ├── cameras/
│       │   │   ├── events/
│       │   │   ├── alerts/
│       │   │   ├── map/
│       │   │   ├── playback/
│       │   │   ├── reports/
│       │   │   ├── settings/
│       │   │   └── health/
│       │   ├── api/
│       │   ├── hooks/
│       │   ├── stores/
│       │   ├── types/
│       │   └── utils/
│       └── tests/
│
├── packages/
│   ├── contracts/
│   │   ├── event-schema/
│   │   └── openapi/
│   ├── risk-engine/
│   └── common/
│
├── models/
│   ├── detection/
│   ├── tracking/
│   ├── behavior/
│   ├── face/
│   ├── anpr/
│   └── README.md
│
├── datasets/
│   ├── README.md
│   ├── raw/
│   ├── processed/
│   ├── annotations/
│   └── splits/
│
├── simulator/
│   ├── sample-videos/
│   ├── scenario-configs/
│   └── event-generator/
│
├── infra/
│   ├── docker/
│   ├── postgres/
│   ├── redis/
│   ├── monitoring/
│   └── reverse-proxy/
│
├── scripts/
│   ├── bootstrap/
│   ├── migrations/
│   ├── benchmark/
│   └── demo/
│
└── docs/
    ├── architecture/
    ├── api/
    ├── deployment/
    ├── operations/
    ├── security/
    └── demo/
```

Do not create this exact structure blindly if the repository already has an established structure. Adapt to the existing repository while preserving these logical boundaries.

---

# 10. TECHNOLOGY BASELINE

## 10.1 Edge/backend

Preferred:
- Python
- FastAPI for service APIs
- Pydantic models
- SQLAlchemy/SQLModel or equivalent typed ORM
- SQLite for single-site edge prototype
- PostgreSQL for central aggregation
- Redis where useful for transient state/events

## 10.2 Video

Preferred:
- GStreamer
- NVIDIA DeepStream when NVIDIA GPU acceleration is available
- FFmpeg
- OpenCV for utilities and image operations

## 10.3 Detection

Primary candidate:
- Ultralytics YOLO26 nano/small variants

Fallback/benchmark:
- YOLO11 nano/small

Earlier architecture artifacts also referenced YOLOv8/YOLOv11. Keep model selection configurable; do not hardwire model assumptions throughout the application.

## 10.4 Tracking

Primary:
- ByteTrack

Alternative:
- BoT-SORT

Legacy/experimental:
- DeepSORT

Tracking must be behind a stable application interface.

## 10.5 Behavior

Prototype:
- deterministic temporal rules first

Possible advanced modules:
- RTMPose
- 3D CNN
- TimeSformer
- SlowFast
- I3D
- custom domain models

Do not add heavyweight behavior models until the baseline event pipeline is stable.

## 10.6 Face

Optional module:
- SCRFD for face detection
- ArcFace for recognition

This module must be configurable and disabled by default unless an authorized watchlist is configured.

## 10.7 ANPR

Optional:
- PaddleOCR
- LPRNet
- EasyOCR

Again, this should be a separate plugin/module, not a dependency of the basic detector.

## 10.8 Frontend

Preferred:
- React
- TypeScript
- React 19-compatible stack
- modern router/query/state solution
- Tailwind CSS or equivalent
- Mapbox or Leaflet for geospatial visualization

## 10.9 Infrastructure

Development:
- Docker Compose

Production-style prototype:
- Docker containers
- Linux
- reverse proxy
- PostgreSQL
- Redis
- monitoring/metrics

---

# 11. MODEL ABSTRACTION

Never couple business logic directly to one specific model package.

Create an interface similar to:

```python
class ObjectDetector(Protocol):
    async def infer(
        self,
        frame: Frame,
        context: InferenceContext,
    ) -> list[Detection]:
        ...
```

Tracking:

```python
class MultiObjectTracker(Protocol):
    def update(
        self,
        detections: list[Detection],
        frame_context: FrameContext,
    ) -> list[Track]:
        ...
```

Behavior:

```python
class BehaviorAnalyzer(Protocol):
    def analyze(
        self,
        tracks: list[Track],
        context: SceneContext,
    ) -> list[BehaviorSignal]:
        ...
```

This lets the project switch between:
- YOLO26
- YOLO11
- ONNX
- TensorRT
- mocked detectors
- CPU fallback

without rewriting the event and risk layers.

---

# 12. DOMAIN DATA MODELS

All cross-service domain models are defined in:

```text
packages/contracts/
```

Each contract must have:
- Pydantic model
- JSON Schema
- stable enum definitions
- validation tests
- documented nullability
- schema version

The examples below are normative starting contracts.

## 12.1 Common scalar types

```python
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID
```

Identifiers use UUIDv4 unless an existing repository convention requires UUIDv7/ULID. Pick one repository-wide; do not mix identifier formats.

Timestamps are ISO-8601 UTC datetimes.

Coordinates:
- latitude: `float | None`
- longitude: `float | None`

Confidence:
- `float`
- inclusive range `[0.0, 1.0]`

Risk score:
- `int`
- inclusive range `[0, 100]`

## 12.2 Enumerations

```python
CameraProtocol = Literal[
    "RTSP",
    "ONVIF",
    "FILE",
    "MOCK",
]

CameraStatus = Literal[
    "ONLINE",
    "DEGRADED",
    "OFFLINE",
    "DISABLED",
]

EventStatus = Literal[
    "OPEN",
    "UPDATED",
    "RESOLVED",
    "CANCELLED",
]

RiskLevel = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
]

EvidenceKind = Literal[
    "SNAPSHOT",
    "VIDEO_CLIP",
    "METADATA",
]

AlertStatus = Literal[
    "PENDING",
    "DELIVERING",
    "DELIVERED",
    "ACKNOWLEDGED",
    "RESOLVED",
    "FAILED",
]

SyncStatus = Literal[
    "PENDING",
    "UPLOADING",
    "SYNCED",
    "RETRY_WAIT",
    "FAILED",
]
```

## 12.3 Camera

```python
class Camera(BaseModel):
    id: UUID
    site_id: UUID
    name: str
    protocol: CameraProtocol
    stream_uri_ref: str
    enabled: bool = True
    target_fps: int = Field(default=5, ge=1, le=60)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    timezone: str
    status: CameraStatus
    created_at: datetime
    updated_at: datetime
```

`stream_uri_ref` is a secret-store/configuration reference, never the plaintext URI containing credentials.

## 12.4 Detection

```python
class BoundingBox(BaseModel):
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)

class Detection(BaseModel):
    id: UUID
    camera_id: UUID
    timestamp: datetime
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    track_id: int | None = Field(default=None, ge=1)
    model_name: str
    model_version: str
```

## 12.5 Track

```python
class Track(BaseModel):
    track_id: int = Field(ge=1)
    camera_id: UUID
    class_name: str
    first_seen: datetime
    last_seen: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    current_bbox: BoundingBox
    trajectory: list[tuple[float, float]] = Field(default_factory=list)
    zone_ids: list[UUID] = Field(default_factory=list)
```

Trajectory points use normalized image coordinates.

## 12.6 Zone

```python
ZoneType = Literal[
    "RESTRICTED",
    "MONITORING",
    "ENTRY",
    "SAFE",
]

GeometryType = Literal[
    "POLYGON",
    "LINE",
    "RECTANGLE",
]

class Zone(BaseModel):
    id: UUID
    camera_id: UUID
    name: str
    type: ZoneType
    geometry_type: GeometryType
    coordinates: list[list[float]]
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
```

Coordinates are normalized to `[0,1]` for camera-image geometry.

## 12.7 RiskSignal

```python
RiskSignalCode = Literal[
    "RESTRICTED_ZONE_ENTRY",
    "UNUSUAL_TIME",
    "RUNNING",
    "HIDING",
    "LOITERING",
    "WEAPON_LIKE_OBJECT",
    "GROUP_MOVEMENT",
    "CROWD_ANOMALY",
    "WATCHLIST_MATCH",
    "ANPR_MATCH",
    "REPEATED_ACTIVITY",
    "CAMERA_SITE_SENSITIVITY",
    "PERIMETER_INTRUSION",
    "LINE_CROSSING",
    "CROSS_CAMERA_CORRELATION",
]

class RiskSignal(BaseModel):
    code: RiskSignalCode
    score_contribution: int
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_event_id: UUID | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
```

## 12.8 RiskResult

```python
class RiskResult(BaseModel):
    score: int = Field(ge=0, le=100)
    level: RiskLevel
    signals: list[RiskSignal]
    reason_codes: list[RiskSignalCode]
    scoring_version: str
    calculated_at: datetime
```

## 12.9 Event

```python
EventType = Literal[
    "PERSON_DETECTED",
    "VEHICLE_DETECTED",
    "OBJECT_DETECTED",
    "ZONE_ENTRY",
    "ZONE_EXIT",
    "PERIMETER_INTRUSION",
    "LINE_CROSSING",
    "LOITERING",
    "RUNNING",
    "SUDDEN_MOVEMENT",
    "CROWD_FORMATION",
    "CROWD_ANOMALY",
    "WATCHLIST_MATCH",
    "ANPR_MATCH",
    "REPEATED_ACTIVITY",
    "CROSS_CAMERA_ACTIVITY",
    "ANOMALY_SIGNAL",
    "CAMERA_OFFLINE",
    "STREAM_DEGRADED",
    "EDGE_SERVICE_DEGRADED",
    "SYNC_BACKLOG_HIGH",
]

class Event(BaseModel):
    schema_version: str = "1.0"
    event_id: UUID
    site_id: UUID
    camera_id: UUID | None
    event_type: EventType
    status: EventStatus
    timestamp_start: datetime
    timestamp_end: datetime | None
    zone_id: UUID | None
    track_ids: list[int] = Field(default_factory=list)
    risk: RiskResult | None
    evidence_ids: list[UUID] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
```

## 12.10 Evidence

```python
class Evidence(BaseModel):
    evidence_id: UUID
    event_id: UUID
    kind: EvidenceKind
    storage_uri: str
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    size_bytes: int = Field(ge=0)
    created_at: datetime
    retention_until: datetime | None
```

## 12.11 Alert

```python
class Alert(BaseModel):
    alert_id: UUID
    event_id: UUID
    channel: str
    priority: RiskLevel
    status: AlertStatus
    created_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: UUID | None
    resolved_at: datetime | None
    last_error: str | None
```

## 12.12 AuditLog

```python
class AuditLog(BaseModel):
    audit_id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    timestamp: datetime
    source_ip: str | None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
```

## 12.13 SyncEnvelope

```python
class SyncEnvelope(BaseModel):
    schema_version: str = "1.0"
    sync_id: UUID
    site_id: UUID
    edge_device_id: UUID
    event_id: UUID
    idempotency_key: str
    payload_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    event: Event
    evidence_refs: list[Evidence] = Field(default_factory=list)
    created_at: datetime
```

The server must treat `idempotency_key` as unique.

## 12.14 JSON Schema generation

The canonical Pydantic models must generate JSON Schemas during CI.

Example:

```bash
python scripts/contracts/export_json_schema.py
```

Generated files belong under:

```text
packages/contracts/json-schema/
```

Do not hand-edit generated schema artifacts.

# 13. EVENT TAXONOMY


Use a stable event taxonomy.

Example:

```text
PERSON_DETECTED
VEHICLE_DETECTED
OBJECT_DETECTED

ZONE_ENTRY
ZONE_EXIT
PERIMETER_INTRUSION
LINE_CROSSING

LOITERING
RUNNING
SUDDEN_MOVEMENT
CROWD_FORMATION
CROWD_ANOMALY

WATCHLIST_MATCH
ANPR_MATCH

REPEATED_ACTIVITY
CROSS_CAMERA_ACTIVITY

ANOMALY_SIGNAL

CAMERA_OFFLINE
STREAM_DEGRADED
EDGE_SERVICE_DEGRADED
SYNC_BACKLOG_HIGH
```

Event names are internal contracts. They must remain stable even if models change.

---

# 14. VIDEO INGESTION DESIGN

Implement a camera adapter layer.

```text
CameraSource
├── RTSPSource
├── FileSource
├── MockSource
└── FutureONVIFSource
```

Requirements:

- reconnect automatically
- exponential backoff
- configurable retry limit
- emit health status
- detect stalled streams
- timestamp frames
- preserve camera identity
- never block the entire edge pipeline because one camera fails

Use per-camera isolation.

A failure in Camera A must not stop Camera B.

---

# 15. FRAME PROCESSING PIPELINE

Preferred processing flow:

```text
Frame
 ↓
Decode
 ↓
Resize / normalize
 ↓
Primary detection
 ↓
Tracking
 ↓
Zone membership
 ↓
Temporal rules
 ↓
Optional identity/ANPR
 ↓
Event normalization
 ↓
Risk engine
 ↓
Evidence capture
 ↓
Local persistence
 ↓
Notifications
```

Do not run every heavy model on every frame.

Introduce configurable frequencies:

```text
detection_fps
tracking_fps
behavior_analysis_interval
face_analysis_interval
anpr_interval
snapshot_interval
```

Use frame skipping and tracking to control compute.

---

# 16. DETECTION OUTPUT

Standardize detector output:

```json
{
  "camera_id": "cam-01",
  "timestamp": "2026-09-04T12:00:00Z",
  "model": {
    "name": "yolo26n",
    "version": "configured-version"
  },
  "detections": [
    {
      "class": "person",
      "confidence": 0.94,
      "bbox": [0.11, 0.24, 0.27, 0.86]
    }
  ]
}
```

Use normalized coordinates where practical.

Keep raw model output out of the business/domain layer.

---

# 17. TRACKING

Tracking should produce persistent IDs:

```text
Camera 01
Person #23
   ↓
frame 1
   ↓
frame 2
   ↓
frame 3
   ↓
frame 4
```

For every track maintain:

- first seen
- last seen
- current location
- velocity estimate
- path
- dwell time
- zone history
- event history

Use TTL cleanup so abandoned tracks don't remain forever.

---

# 18. VIRTUAL ZONES

Operators must be able to create:

- restricted zones
- safe zones
- entry zones
- monitoring zones

Zone shape:
- polygon
- line
- rectangle

Example:

```json
{
  "zone_id": "border-fence-01",
  "camera_id": "cam-04",
  "type": "restricted",
  "polygon": [
    [0.15, 0.32],
    [0.85, 0.30],
    [0.92, 0.88],
    [0.12, 0.90]
  ]
}
```

Use normalized coordinates so the zone survives common resolution changes.

---

# 19. EVENT RULE ENGINE

Start with deterministic rules before ML risk scoring.

Example:

### Perimeter intrusion

```text
track crosses restricted zone boundary
→ PERIMETER_INTRUSION
```

### Loitering

```text
track remains inside restricted zone
for longer than configured threshold
→ LOITERING
```

### Repeated activity

```text
same track/cross-camera identity
re-enters monitored zone repeatedly
within configurable time window
→ REPEATED_ACTIVITY
```

### Night activity

```text
event.timestamp in configured night period
→ add NIGHT_TIME context signal
```

### Running

Use trajectory/speed estimation initially.

Advanced activity models can replace this later.

---

# 20. RISK ENGINE

The risk engine is one of the defining components of IBVAP.

## 20.1 Required architecture

```text
Raw module outputs
      ↓
Normalize
      ↓
Deduplicate
      ↓
Attach context
      ↓
Temporal correlation
      ↓
Cross-camera correlation
      ↓
Rule scoring
      ↓
Optional ML scoring
      ↓
Risk aggregation
      ↓
Risk level
      ↓
Response policy
```

## 20.2 Canonical risk signals

The following 15 signals are the complete initial scoring vocabulary.

| Signal code | Meaning | Initial weight | Required at MVP |
|---|---|---:|---|
| `RESTRICTED_ZONE_ENTRY` | entering configured restricted zone | 20 | Yes |
| `UNUSUAL_TIME` | activity during configured unusual/night period | 5 | Yes |
| `RUNNING` | running/sustained high-motion behavior | 10 | Yes |
| `HIDING` | configured hiding/occlusion behavior signal | 10 | No |
| `LOITERING` | dwell beyond threshold | 15 | Yes |
| `WEAPON_LIKE_OBJECT` | detector reports configured weapon-like object | 30 | No |
| `GROUP_MOVEMENT` | multiple related tracks moving together | 10 | Yes |
| `CROWD_ANOMALY` | abnormal crowd-density/movement signal | 15 | No |
| `WATCHLIST_MATCH` | authorized identity watchlist match | 35 | No |
| `ANPR_MATCH` | authorized vehicle/plate watchlist match | 30 | No |
| `REPEATED_ACTIVITY` | repeated event/activity in configured window | 10 | Yes |
| `CAMERA_SITE_SENSITIVITY` | configured sensitivity multiplier/bonus for site | 5 | Yes |
| `PERIMETER_INTRUSION` | crossing a restricted perimeter | 25 | Yes |
| `LINE_CROSSING` | configured line crossing | 15 | No |
| `CROSS_CAMERA_CORRELATION` | correlated movement/event across cameras | 10 | No |

These are **initial calibration values**, not validated scientific weights.

### Scoring rule

1. Gather all active signals.
2. Sum their configured contributions.
3. Apply configured caps/adjustments.
4. Clamp final score to `[0,100]`.
5. Derive level from the canonical thresholds.
6. Persist all contributing signals and reason codes.

If two signals represent the same underlying event, the implementation must define whether they stack or whether one supersedes the other. For the initial implementation:
- `PERIMETER_INTRUSION` and `RESTRICTED_ZONE_ENTRY` may both contribute only when they describe distinct event semantics.
- Duplicate copies of the same event must be deduplicated before scoring.

### Configuration format

The signal weights must be configuration-driven:

```yaml
risk:
  weights:
    RESTRICTED_ZONE_ENTRY: 20
    UNUSUAL_TIME: 5
    RUNNING: 10
    HIDING: 10
    LOITERING: 15
    WEAPON_LIKE_OBJECT: 30
    GROUP_MOVEMENT: 10
    CROWD_ANOMALY: 15
    WATCHLIST_MATCH: 35
    ANPR_MATCH: 30
    REPEATED_ACTIVITY: 10
    CAMERA_SITE_SENSITIVITY: 5
    PERIMETER_INTRUSION: 25
    LINE_CROSSING: 15
    CROSS_CAMERA_CORRELATION: 10
```

No hard-coded scoring constants may exist elsewhere in the codebase.

## 20.3 Canonical risk levels

```text
0–19     LOW
20–49    MEDIUM
50–79    HIGH
80–100   CRITICAL
```

These thresholds are configurable but these values are the canonical prototype defaults.

## 20.4 Risk explainability

Every non-zero score must include:
- signal codes
- contribution values
- source event IDs when applicable
- scoring version
- timestamp

Example:

```json
{
  "score": 82,
  "level": "CRITICAL",
  "scoring_version": "rules-v1",
  "reason_codes": [
    "PERIMETER_INTRUSION",
    "UNUSUAL_TIME",
    "RUNNING"
  ]
}
```

## 20.5 ML risk model

Do not introduce ML risk scoring before deterministic rule scoring is stable.

Later architecture may be:

```text
rule_score
      +
ml_score
      ↓
calibration layer
      ↓
final risk score
```

The ML model must be versioned, evaluated, and compared against the rule baseline.

# 21. RISK SCORING IMPLEMENTATION

Start with a deterministic weighted rule engine.

Required tests:

- every one of the 15 signals
- combinations of signals
- duplicate-event behavior
- score clamping
- threshold boundaries
- no-signal case
- missing optional metadata
- invalid signal code rejection
- configuration loading
- configuration validation

Boundary tests must explicitly cover:

```text
19 → LOW
20 → MEDIUM
49 → MEDIUM
50 → HIGH
79 → HIGH
80 → CRITICAL
100 → CRITICAL
```

No agent is allowed to invent additional risk signals or weights without updating the canonical contract and this specification.

# 22. ALERT POLICY

Example response matrix:

```text
LOW
→ log only

MEDIUM
→ dashboard notification
→ continue monitoring

HIGH
→ dashboard alert
→ operator notification
→ local response if configured

CRITICAL
→ immediate dashboard alert
→ local response
→ high-priority notification
→ evidence preservation
```

Never automatically deploy a physical response based solely on an unverified AI classification in the prototype.

The prototype should support configurable action policies.

---

# 23. LOCAL ALERT ADAPTERS

Create an interface:

```python
class AlertChannel(Protocol):
    async def send(self, alert: Alert) -> DeliveryResult:
        ...
```

Adapters:

```text
DashboardChannel
WebhookChannel
EmailChannel
SMSChannel
TelegramChannel
SirenRelayChannel
```

For development, use:

```text
MockAlertChannel
```

so the system can demonstrate alerts without real external services.

---

# 24. EVIDENCE CAPTURE

When an event crosses an evidence threshold:

Capture:

1. snapshot before/at event
2. snapshot after event
3. short event clip
4. event metadata
5. risk score
6. reason codes
7. model versions
8. camera/site information
9. timestamp

Recommended configurable clip window:

```text
pre_event_seconds
post_event_seconds
```

Example default:

```text
pre_event_seconds = 5
post_event_seconds = 10
```

These are configuration defaults, not requirements.

---

# 25. LOCAL STORAGE

Edge prototype:

- SQLite
- local encrypted filesystem where practical
- SSD/NVMe for media

Store:

```text
database/
media/
  snapshots/
  clips/
logs/
outbox/
```

Do not store massive continuous video in the SQLite database.

Store file references in DB.

Each evidence artifact should have a checksum:

```text
SHA-256
```

---

# 26. OUTBOX / STORE-AND-FORWARD

The edge service must use an outbox pattern.

State machine:

```text
PENDING
  ↓
UPLOADING
  ↓
SYNCED

failure:
UPLOADING
  ↓
RETRY_WAIT
  ↓
PENDING
```

Requirements:

- idempotency key
- retry count
- exponential backoff
- jitter
- checksum verification
- resumable/atomic upload where practical
- offline queue visibility
- failed-item diagnostics

Example:

```text
event_id
payload_hash
attempt_count
next_attempt_at
status
last_error
created_at
```

Never upload duplicate events because of reconnect retries.

---

# 27. CENTRAL SYNC API

Suggested endpoint family:

```text
POST /api/v1/sync/events
POST /api/v1/sync/evidence
GET  /api/v1/sync/status
POST /api/v1/sync/heartbeat
```

Use an edge/site credential rather than a personal user token.

Every event must carry:

```text
site_id
edge_device_id
event_id
created_at
schema_version
payload_hash
```

Server must be idempotent.

---

# 28. CENTRAL API

Suggested API groups:

```text
/api/v1/auth
/api/v1/sites
/api/v1/cameras
/api/v1/zones
/api/v1/events
/api/v1/alerts
/api/v1/evidence
/api/v1/reports
/api/v1/users
/api/v1/roles
/api/v1/audit
/api/v1/health
/api/v1/sync
```

Use consistent error format:

```json
{
  "error": {
    "code": "CAMERA_NOT_FOUND",
    "message": "Camera cam-04 does not exist",
    "request_id": "..."
  }
}
```

Every request should receive a correlation/request ID.

---

# 29. AUTHENTICATION AND AUTHORIZATION

Minimum prototype:

- username/password or OIDC-compatible authentication
- secure password hashing
- session/JWT handling
- role-based authorization

Roles:

```text
ADMIN
SECURITY_OPERATOR
INVESTIGATOR
ANALYST
VIEWER
```

Example permissions:

```text
ADMIN
  all

SECURITY_OPERATOR
  live view
  acknowledge alerts
  playback
  create zones

INVESTIGATOR
  search events
  playback
  export evidence

ANALYST
  analytics/reports

VIEWER
  read-only dashboard
```

Never send privileged capabilities based only on frontend route hiding. Enforce authorization on the API.

---

# 30. PRIVACY AND IDENTITY ANALYTICS

Face recognition is optional and must be explicitly enabled.

Design requirements:

- watchlists must be configured by authorized operators
- face embeddings should not be displayed unnecessarily
- store references rather than raw biometrics where possible
- encrypt sensitive data
- add retention policies
- audit every watchlist access/match review
- do not make an automatic high-stakes determination from a face match alone

Face recognition is an assistive signal for verification.

---

# 31. ANPR

ANPR is optional.

Pipeline:

```text
Vehicle detected
 ↓
plate region
 ↓
OCR
 ↓
normalization
 ↓
confidence threshold
 ↓
watchlist comparison
 ↓
event/risk signal
```

Store:
- plate text
- OCR confidence
- crop/evidence reference
- timestamp
- camera
- model version

Never treat low-confidence OCR as a definitive match.

---

# 32. CROSS-CAMERA CORRELATION

First prototype version:

Use logical correlation rather than heavy re-identification.

Example:

```text
Camera A:
Person track exits zone at 18:21

Camera B:
Person-like track enters route at 18:23
```

Create a correlation event when configurable temporal/spatial conditions are satisfied.

Advanced appearance-based Re-ID can be added later.

Candidate model:
- OSNet

Do not block MVP on Re-ID.

---

# 33. ANOMALY DETECTION

Optional research module.

Potential technologies:
- Anomalib
- PatchCore
- STFPM-style approaches

Architecture rule:

> Anomaly score is a secondary signal, not the sole basis for an intervention decision.

Example:

```text
anomaly_score
+
known event signals
+
context
→ risk engine
```

---

# 34. NIGHT/TERRAIN CONDITIONS

The system should support scene profiles.

Example:

```text
DAY_PROFILE
NIGHT_PROFILE
LOW_LIGHT_PROFILE
```

Night profile can change:

- detector threshold
- frame rate
- exposure preprocessing
- behavior thresholds
- false-positive filtering

Future hardware support:
- IR cameras
- thermal cameras

Do not assume generic daytime models perform equally well in all night conditions.

---

# 35. HEALTH MONITORING

Every site must expose:

```text
camera status
stream FPS
inference FPS
CPU
GPU
RAM
disk usage
queue depth
database size
sync status
last successful sync
active alerts
model version
service uptime
```

Suggested endpoints:

```text
GET /health/live
GET /health/ready
GET /metrics
```

A camera that stops sending video must produce a `CAMERA_OFFLINE` or degraded-health event.

---

# 36. OBSERVABILITY

Use structured JSON logs.

Every log should contain where applicable:

```text
timestamp
level
service
request_id
site_id
camera_id
event_id
trace_id
message
```

Implement:

- rotating file logs
- stdout logs in containers
- metrics
- health endpoints
- optional OpenTelemetry-ready tracing

Never put:
- passwords
- API keys
- raw face embeddings
- full stream credentials

into logs.

---

# 37. FRONTEND — COMMAND DASHBOARD

The dashboard should feel like a real command application, not a generic admin panel.

## Main screens

### 1. Operations Dashboard

Show:

- critical alerts
- high alerts
- live camera status
- recent events
- system health
- active site summary
- map

### 2. Live Camera View

Show:

- camera feed
- bounding boxes
- track IDs
- zone overlays
- event markers

### 3. Event Center

Filter by:

- time
- site
- camera
- event type
- risk level
- status
- person/vehicle signal
- zone

### 4. Event Details

Show:

- snapshot
- clip
- risk score
- reasons
- timeline
- track
- metadata
- audit history

### 5. Map

Show:

- sites
- cameras
- active alerts
- risk heatmap
- recent event locations

### 6. Playback

Show:

- event clip
- timestamp
- camera
- synchronized metadata

### 7. Reports

Examples:

- events by day
- events by site
- risk distribution
- repeated intrusion zones
- camera availability
- sync statistics

### 8. Administration

Manage:
- sites
- cameras
- zones
- thresholds
- users
- roles
- notifications
- retention settings

---

# 38. REAL-TIME DASHBOARD TRANSPORT

Use WebSocket or Server-Sent Events for alert updates.

Example:

```text
event.created
event.updated
alert.created
alert.acknowledged
camera.status_changed
sync.status_changed
```

Define event schemas centrally.

---

# 39. MAP

Use Mapbox or Leaflet.

Each site:

```text
site_id
name
latitude
longitude
risk_summary
camera_count
online_camera_count
last_event_at
```

Cluster markers when many sites are shown.

Do not render every historical event simultaneously.

Use time-window queries.

---

# 40. DATABASE DESIGN

Central database should include at minimum:

```text
users
roles
permissions

sites
edge_devices
cameras
zones

events
event_signals
event_tracks
evidence

alerts
notification_deliveries

sync_batches
sync_items

audit_logs

model_versions
system_health
```

Use migrations from day one.

Do not manually edit production DB schemas.

---

# 41. DATABASE INDEXING

Important indexes:

```text
events(site_id, timestamp)
events(camera_id, timestamp)
events(risk_level, timestamp)
events(event_type, timestamp)
events(status, timestamp)

alerts(status, created_at)

evidence(event_id)
audit_logs(actor_id, timestamp)
```

Use pagination for all historical endpoints.

---

# 42. RETENTION POLICY

Make retention configurable.

Example:

```text
event_metadata_days = 90
event_clip_days = 30
audit_log_days = 365
```

These are sample defaults only.

Do not hardcode retention in application logic.

---

# 43. SECURITY REQUIREMENTS

Minimum:

- TLS for central connections
- encrypted credentials
- secret injection through environment/secret manager
- RBAC
- audit logging
- secure password hashing
- API rate limiting
- request validation
- input sanitization
- upload restrictions
- content-type validation
- checksum verification
- bounded media sizes
- secure headers
- dependency scanning
- container image scanning in CI

For edge-to-HQ synchronization:
- use TLS
- authenticate the edge device
- use idempotent event submission
- rotate credentials
- revoke compromised devices

---

# 44. THREAT MODEL

Threats to consider:

### T1 — Stolen edge device
Mitigations:
- encrypted storage
- device identity
- secrets not embedded in source

### T2 — Stolen API credential
Mitigations:
- scoped credentials
- rotation
- revocation
- rate limiting
- audit logs

### T3 — Evidence tampering
Mitigations:
- SHA-256 checksums
- immutable audit records where possible
- optional later blockchain anchoring

### T4 — Network interception
Mitigation:
- TLS

### T5 — Malicious media upload
Mitigation:
- size limits
- content validation
- sandbox/isolated processing where applicable

### T6 — Model manipulation
Mitigations:
- model checksum
- signed/verified artifact source
- versioned models

### T7 — False-positive attack
Mitigation:
- context/risk fusion
- human verification
- alert throttling

---

# 45. OPTIONAL BLOCKCHAIN INTEGRITY MODULE

Blockchain is NOT an MVP dependency.

If implemented later:

```text
Event created
    ↓
canonical event hash
    ↓
hash anchored in private ledger
    ↓
audit/reference ID
```

Potential technology:
- Hyperledger Fabric
- private Ethereum-compatible network

Use it only for integrity/audit.

Do not store large video files directly on blockchain.

---

# 46. CONFIGURATION

Use environment/config files.

Example:

```env
APP_ENV=development

EDGE_SITE_ID=site-demo-01
EDGE_DEVICE_ID=edge-demo-01

DATABASE_URL=sqlite:///./data/edge.db

CENTRAL_API_URL=http://central-api:8000

MODEL_DETECTOR=yolo26n
MODEL_DEVICE=cpu

DETECTION_FPS=5
TRACKING_FPS=10

RISK_LOW_MAX=19
RISK_MEDIUM_MAX=49
RISK_HIGH_MAX=79

PRE_EVENT_SECONDS=5
POST_EVENT_SECONDS=10

SYNC_ENABLED=true
SYNC_BATCH_SIZE=25

LOG_LEVEL=INFO
```

Use `.env.example`, never commit real `.env`.

---

# 47. API CONTRACT RULES

All API contracts must be versioned:

```text
/api/v1/...
```

Use OpenAPI.

Generate TypeScript API types from the OpenAPI schema where practical.

Avoid maintaining duplicate request/response types manually.

---

# 48. ERROR HANDLING

Every service must distinguish:

```text
validation error
authentication error
authorization error
not found
conflict
dependency unavailable
timeout
temporary network failure
permanent failure
internal error
```

Do not catch all exceptions and silently continue.

For video pipelines:
- log failure
- mark camera degraded
- retry
- isolate the failing source

For sync:
- retry transient errors
- quarantine poison items after configurable failures
- expose the failure in dashboard

---

# 49A. TEST COVERAGE ACCEPTANCE BAR

Coverage is not the only quality metric, but it is a release gate.

Minimum targets:

| Area | Minimum line coverage | Additional requirement |
|---|---:|---|
| Risk engine | **90%** | critical branches and threshold boundaries covered |
| Sync/outbox | **90%** | retry, duplicate, crash-recovery paths covered |
| Auth/RBAC | **90%** | every role/permission denial path tested |
| Domain contracts | **95%** | validation and enum cases covered |
| Zone/event logic | **90%** | geometry and deduplication edge cases covered |
| Central API | **80%** | happy/error paths covered |
| Edge ingestion adapters | **80%** | reconnect and failure paths covered |
| Dashboard application | **70%** | critical user flows covered with component/E2E tests |

Coverage below these bars blocks phase completion unless an explicit exception is documented in `PROGRESS.md` with rationale.

# 49. TESTING STRATEGY

## Unit tests

Test:

- zone geometry
- intrusion detection
- dwell timers
- scoring
- event normalization
- retry logic
- sync idempotency
- permission checks

## Integration tests

Test:

```text
camera adapter
→ detection mock
→ tracker mock
→ event engine
→ risk engine
→ DB
```

## End-to-end tests

Run:

```text
sample video
→ event
→ risk
→ evidence
→ dashboard API
→ sync
```

## Failure tests

Simulate:

- camera disconnect
- central API unavailable
- network loss
- database restart
- disk nearly full
- duplicate sync
- malformed event
- invalid credentials

The system must degrade gracefully.

---

# 50. PERFORMANCE BENCHMARKS

Benchmark separately:

### Video ingestion

- stream startup latency
- reconnect time
- frames received/sec

### Detection

- inference latency
- FPS
- CPU/GPU utilization

### Tracking

- tracking throughput
- ID switches for test scenarios

### Event engine

- events/sec

### Risk engine

- score latency

### Sync

- events/minute
- bandwidth usage
- retry recovery time

Do not invent benchmark numbers.

Store actual benchmarks in:

```text
docs/operations/benchmarks/
```

---

# 51. TARGET PROTOTYPE PERFORMANCE

These are engineering targets for iteration, NOT claims.

The team should benchmark and adjust based on hardware.

Suggested targets:

- local alert propagation: near real-time
- API p95 latency for normal queries: <500 ms on prototype infrastructure
- risk calculation: <50 ms excluding model inference
- reconnect handling: automatic
- event synchronization: resilient under intermittent connectivity
- dashboard alert delivery: seconds, not minutes

Actual achieved values must be measured.

---

# 52. DEMO SCENARIO — PRIMARY

## Scenario

A person approaches a restricted border zone at night.

### Sequence

```text
CCTV
 ↓
Person detected
 ↓
Track ID #23
 ↓
Track enters restricted polygon
 ↓
PERIMETER_INTRUSION
 ↓
Night-time context
 ↓
Running behavior signal
 ↓
Risk engine
 ↓
Risk = 82
 ↓
CRITICAL/HIGH depending configured threshold
 ↓
Local alert
 ↓
Event snapshot + clip stored
 ↓
Internet disconnected
 ↓
System continues
 ↓
Internet restored
 ↓
Event syncs to HQ
 ↓
HQ dashboard receives event
```

The example score of 82 is illustrative only.

---

# 53. DEMO SCENARIO — OFFLINE MODE

### Step 1

Start system.

### Step 2

Play CCTV sample.

### Step 3

Trigger intrusion.

### Step 4

Verify local alert.

### Step 5

Disable internet/network access.

### Step 6

Trigger second intrusion.

Expected:

```text
AI still works
event still created
risk score still calculated
local alert still works
event queued for sync
```

### Step 7

Restore connectivity.

Expected:

```text
outbox retries
event uploads
checksum validates
server accepts idempotently
edge marks SYNCED
dashboard updates
```

This is a core differentiator and should be part of the official demo.

---

# 54. DEMO SCENARIO — FALSE ALARM CONTROL

Demonstrate that:

```text
Person walking normally
```

does not automatically become critical.

Then show:

```text
restricted zone
+
night
+
running
+
repeat behavior
```

increasing the priority.

This demonstrates why the risk engine exists.

---

# 55. MODEL MANAGEMENT

Every model must have:

```text
name
version
file checksum
framework
input size
classes
training dataset/version
deployment target
created_at
```

Example:

```yaml
name: yolo26n
version: demo-001
sha256: <actual checksum>
device: cpu
input_size: 640
```

Never download arbitrary model files at runtime without verification.

---

# 56. DATASET STRATEGY

Prototype development may begin with:
- public surveillance/video datasets
- synthetic scenarios
- recorded controlled scenes

For project-specific performance:
- build a labeled domain dataset
- include daylight
- night
- occlusion
- camera compression
- varying viewpoints
- different clothing/backgrounds
- border-style terrain where legally and ethically available

Dataset versioning is required.

Example:

```text
dataset-v0.1
dataset-v0.2
```

Track:
- source
- license
- classes
- annotation rules
- train/val/test split
- preprocessing

---

# 57. MODEL EVALUATION

Object detection:

- precision
- recall
- mAP
- per-class metrics
- night vs day breakdown

Tracking:

- IDF1
- HOTA or appropriate MOT metric
- ID switches

Behavior:

- precision
- recall
- confusion matrix

Risk engine:

- false alert rate
- missed critical-event rate
- calibration
- per-scenario performance

The system must distinguish:
- AI model metrics
- end-to-end product metrics

---

# 58. MODEL DEPLOYMENT STRATEGY

Development:

```text
Python / PyTorch
```

Optimization:

```text
ONNX / TensorRT where appropriate
```

NVIDIA deployments:

```text
DeepStream + TensorRT
```

CPU fallback:

```text
ONNX Runtime / CPU inference
```

Use a common detector interface so optimization does not affect business logic.

---

# 59. GPU / CPU FALLBACK

The application must detect hardware capability.

Example:

```text
GPU available
→ optimized inference

GPU unavailable
→ CPU fallback with reduced processing rate
```

Expose:

```text
inference_backend
device
precision
model_name
```

in health information.

---

# 60. RESOURCE MANAGEMENT

The edge service must prevent:

- memory leaks
- unbounded queues
- unlimited event storage
- runaway retries
- CPU starvation
- GPU oversubscription

Every queue should have limits.

When limits are reached:
- drop non-critical intermediate frames
- preserve event/evidence data
- expose overload status

Never silently drop critical events.

---

# 61. VIDEO BUFFER

Keep a rolling in-memory or disk-backed buffer for recent frames.

Purpose:

> allow a detected event to include pre-event footage.

Example:

```text
continuous ring buffer
       ↓
event occurs
       ↓
capture previous 5 sec
+
capture next 10 sec
       ↓
write evidence clip
```

Do not permanently encode the entire stream if unnecessary.

---

# 62. EVENT DEDUPLICATION

The same intrusion may remain true across many frames.

Do not create:

```text
1000 alerts for one continuous intrusion
```

Create one event with:

```text
started_at
ended_at
max_risk
track_id
evidence
```

Use event lifecycle:

```text
OPEN
→ UPDATED
→ RESOLVED
```

Potential event grouping keys:

```text
camera_id
track_id
event_type
zone_id
time-window
```

---

# 63. ALERT THROTTLING

Implement notification throttling.

Example:

```text
same event
→ one high-priority notification
→ updates in dashboard
→ no spam loop
```

Critical new events can bypass normal throttling.

---

# 64. TIME HANDLING

Use UTC internally.

Store:

```text
UTC timestamp
site timezone
```

Render local time in UI.

Never compare raw local timestamps across sites without timezone awareness.

---

# 65. AUDITABILITY

Audit:

- login
- logout
- event viewed
- evidence downloaded
- event acknowledged
- event resolved
- zone created/edited
- camera configuration changed
- risk thresholds changed
- watchlist modified
- user/role changes
- model changed

Audit logs should be append-only at the application level.

---

# 66. EXPORT

Investigators/operators may export:

- event summary
- snapshot
- event clip
- metadata
- audit record
- checksum

Create a clear evidence package:

```text
event-<id>/
├── summary.json
├── snapshot.jpg
├── clip.mp4
├── metadata.json
├── checksums.txt
└── audit.json
```

---

# 67. DOCUMENTATION REQUIREMENTS

The implementation must maintain:

### `README.md`
- what it is
- how to start
- demo instructions

### `IMPLEMENTATION_SPEC.md`
- this document

### `ARCHITECTURE.md`
- system diagrams
- data flows

### `API.md`
- API usage
- auth
- examples

### `DEPLOYMENT.md`
- local Docker
- edge deployment
- central deployment

### `SECURITY.md`
- threat model
- secrets
- access

### `MODEL_CARD.md`
- model source
- version
- license
- evaluation

### `DEMO.md`
- exact judge demo procedure

---

# 67A. CONTRACT TESTING

`packages/contracts` must be tested independently.

CI must verify:

```text
Pydantic validation
→ JSON Schema generation
→ OpenAPI compatibility
→ frontend generated types
→ edge ↔ central payload compatibility
```

Add at least one consumer/provider contract test for:

```text
Event
RiskResult
Evidence
SyncEnvelope
Alert
```

A contract-breaking change must fail CI unless the schema major version is intentionally incremented.

# 68. CI/CD

GitHub Actions or equivalent.

Pipeline:

```text
lint
 ↓
type check
 ↓
unit tests
 ↓
integration tests
 ↓
build frontend
 ↓
build backend
 ↓
container build
 ↓
security/dependency scan
 ↓
artifact publication
```

Block merges on:
- failing tests
- type errors
- formatting/lint violations
- critical security findings

---

# 69. CODING STANDARDS

Python:

- type hints everywhere practical
- Pydantic schemas
- dependency injection for services
- async where I/O benefits
- clear module boundaries

TypeScript:

- strict mode
- avoid `any`
- typed API client
- feature-oriented organization

General:

- descriptive names
- small functions
- no hidden global state
- config-driven thresholds
- test business rules independently

---

# 70. DESIGN PATTERNS TO USE

Recommended:

### Adapter
For:
- camera sources
- notification channels
- model backends

### Strategy
For:
- risk scoring
- detection backend
- behavior algorithms

### Repository
For:
- event persistence
- users
- cameras

### Outbox
For:
- sync

### Event-driven architecture
For:
- alert propagation
- dashboard updates

Avoid unnecessary microservices in the prototype.

Use clear modules within a small number of services.

---

# 71. SERVICE BOUNDARIES

Recommended prototype services:

```text
1. edge-agent
2. central-api
3. dashboard
4. postgres
5. redis (optional)
```

Do NOT split:
- detection
- tracking
- risk engine
- event engine

into separate network services unless scaling requires it.

Keep them in one edge process/application for the prototype.

---

# 72. LOCAL DEVELOPMENT

Recommended developer command flow:

```bash
docker compose up -d postgres redis
```

Then:

```bash
make install
make dev
```

Or equivalent project-specific commands.

Provide:

```bash
make test
make lint
make typecheck
make format
make demo
```

The exact commands may differ with the repo; keep them documented.

---

# 72A. DEMO ASSET SOURCING / LICENSING

Do not fabricate surveillance media and present it as real-world footage.

For the prototype, use one of:

1. internally recorded controlled scenes,
2. synthetic/generated test video,
3. legally reusable/public-domain/royalty-free video with documented license.

Store an asset manifest:

```text
simulator/assets/ASSET_MANIFEST.md
```

Each asset must record:

```text
filename
source
license
license_url
download/creation date
intended use
checksum
```

Never commit sensitive real surveillance footage.

For deterministic CI tests, prefer synthetic fixtures or short local clips that can be legally redistributed with the repository.

# 73. DEMO DATA

Provide a deterministic demo dataset.

Example:

```text
simulator/
  scenarios/
    perimeter_intrusion.yaml
    night_intrusion.yaml
    normal_activity.yaml
```

Scenario configuration should define:

```yaml
name: night-perimeter-intrusion
camera: cam-04
start_time: ...
zone: border-fence-01
events:
  - person_detected
  - zone_crossing
  - running
network:
  disconnect_after: ...
  reconnect_after: ...
```

This allows the whole system to be demonstrated repeatedly.

---

# 74. SIMULATION MODE

The system must have:

```text
DEMO_MODE=true
```

Demo mode can:
- generate predictable events
- use local sample videos
- use mock notifications
- simulate network loss
- avoid external provider credentials

Never mix demo mocks into production business logic. Use interfaces/adapters.

---

# 75. NETWORK FAILURE SIMULATION

Create a test utility or simulator operation:

```text
DISCONNECT_CENTRAL
RECONNECT_CENTRAL
```

Expected:

```text
Central unavailable
→ edge remains healthy
→ outbox grows

Central returns
→ backlog drains
→ dashboard catches up
```

---

# 76. OBSERVABILITY DASHBOARD

Expose metrics:

```text
cameras_total
cameras_online
frames_processed_total
inference_latency_ms
tracks_active
events_total
alerts_total
risk_score_distribution
sync_pending
sync_failed
sync_success
disk_usage
gpu_utilization
```

Use Prometheus-compatible metrics where practical.

---

# 77. LOGGING EXAMPLE

Good:

```json
{
  "timestamp": "2026-09-04T12:00:01Z",
  "level": "INFO",
  "service": "edge-agent",
  "camera_id": "cam-04",
  "event_id": "evt-123",
  "message": "perimeter intrusion event created",
  "risk_score": 82
}
```

Bad:

```text
Something went wrong!!!
```

Logs must be actionable.

---

# 78. FAILURE PHILOSOPHY

The edge must prefer:

> **degraded operation over total shutdown.**

Examples:

### Detector fails
Tracking may stop, but:
- camera health stays visible
- service retries
- operator gets degraded alert

### Central API fails
Local operation continues.

### One camera fails
Other cameras continue.

### Disk nearly full
Raise warning and apply retention policy.

### GPU unavailable
Use CPU fallback or reduced analytics.

---

# 79. DATA FLOW FOR NORMAL OPERATION

```text
camera
 ↓
decoder
 ↓
frame
 ↓
detector
 ↓
detections
 ↓
tracker
 ↓
tracks
 ↓
zone analysis
 ↓
behavior
 ↓
event
 ↓
risk
 ↓
evidence
 ↓
local DB
 ↓
alert
 ↓
outbox
 ↓
central API
 ↓
central DB
 ↓
dashboard
```

---

# 80. DATA FLOW FOR OFFLINE OPERATION

```text
camera
 ↓
AI
 ↓
event
 ↓
risk
 ↓
evidence
 ↓
local DB
 ↓
outbox
 ├───────────────┐
 │ no network    │
 │               │
 │ queue remains │
 └───────────────┘
        ↓
 network restored
        ↓
 sync worker
        ↓
 central API
        ↓
 acknowledged
        ↓
 MARK SYNCED
```

---

# 81. PRODUCT UX PRINCIPLES

The dashboard should optimize for an operator under pressure.

Prioritize:

1. what needs attention now
2. why it is important
3. where it happened
4. what evidence exists
5. what the operator can do

Don't bury critical alerts under charts.

---

# 82. EVENT DETAIL UX

An event detail page should visibly answer:

### WHAT?
Perimeter intrusion

### WHERE?
Site / camera / zone

### WHEN?
Local + UTC timestamp

### WHO/WHAT?
Person #23 / vehicle / object

### WHY?
Night + zone crossing + running

### RISK?
82 / 100

### EVIDENCE?
Snapshot + clip

### ACTION?
Acknowledge / escalate / resolve

---

# 83. ACCESS CONTROL UX

Frontend hides options based on permissions for usability.

Backend independently enforces the permission.

Every privileged action should produce an audit event.

---

# 84. MODEL / SOFTWARE LICENSE DISCIPLINE

Before shipping any dependency or model, verify:

- license
- redistribution restrictions
- commercial-use restrictions
- attribution requirements
- dataset licensing

Do not assume that “open source” means unrestricted commercial use.

Ultralytics documentation specifically provides licensing information; the project team must review the applicable license before any non-academic deployment.

---

# 85. ACCEPTANCE CRITERIA

## A. Camera ingestion

- [ ] RTSP source can be configured.
- [ ] Sample-file source works for development.
- [ ] Camera reconnects after temporary failure.
- [ ] Camera failure does not stop other cameras.
- [ ] Camera health appears in dashboard.

## B. Detection

- [ ] Person detection works.
- [ ] Vehicle detection works.
- [ ] Model/version appears in system state.
- [ ] Inference can run on CPU in development.
- [ ] GPU backend can be added/configured.

## C. Tracking

- [ ] Persistent track IDs are generated.
- [ ] Tracks expire safely.
- [ ] Tracking state is camera-scoped.

## D. Zone analytics

- [ ] Zone can be created/edited.
- [ ] Zone coordinates are normalized.
- [ ] Boundary crossing generates an event.

## E. Risk

- [ ] Risk score always 0..100.
- [ ] Reason codes are stored.
- [ ] Risk thresholds are configurable.
- [ ] Risk engine is independently unit-tested.

## F. Evidence

- [ ] Snapshot captured.
- [ ] Event clip captured.
- [ ] Evidence checksum created.
- [ ] Evidence stored locally.
- [ ] Evidence is linked to event.

## G. Alerts

- [ ] Dashboard notification generated.
- [ ] Duplicate alert spam is prevented.
- [ ] Critical/high alerts have priority.
- [ ] Acknowledgement is logged.

## H. Offline

- [ ] Central connection can be disabled.
- [ ] Edge detection continues.
- [ ] Events are queued.
- [ ] Queue status visible.

## I. Sync

- [ ] Events upload when central returns.
- [ ] Duplicate requests are idempotent.
- [ ] Retry/backoff works.
- [ ] Checksum validation works.
- [ ] Synced state is persisted.

## J. Security

- [ ] API authentication exists.
- [ ] RBAC enforced server-side.
- [ ] Secrets are not hardcoded.
- [ ] Audit logs exist.
- [ ] Sensitive data is not logged.

## K. Dashboard

- [ ] Operations dashboard exists.
- [ ] Event center exists.
- [ ] Event detail exists.
- [ ] Map exists.
- [ ] Camera health exists.
- [ ] Playback works for event clips.

---

# 85A. AGENT PROGRESS TRACKING

Every repository must contain:

```text
PROGRESS.md
.agent/state.json
```

## `PROGRESS.md`

Human-readable status including:

```text
Current phase
Completed phases
Active task
Blocked tasks
Known bugs
Last successful test command
Last successful demo command
Architecture decisions made
Pending decisions
```

## `.agent/state.json`

Machine-readable example:

```json
{
  "spec_version": "1.1",
  "current_phase": 0,
  "phase_status": "IN_PROGRESS",
  "active_task": "repository-audit",
  "completed_tasks": [],
  "blocked_tasks": [],
  "last_commit": null,
  "last_test_status": null,
  "last_test_command": null,
  "last_demo_status": null,
  "updated_at": null
}
```

## Mandatory session behavior

At session start:

```text
read IMPLEMENTATION_SPEC.md
read PROGRESS.md
read .agent/state.json
inspect git status
inspect recent commits
```

At session end:

```text
run relevant tests
update PROGRESS.md
update .agent/state.json
summarize changed files
summarize tests
record unresolved failures
```

Do not claim a phase is complete unless its acceptance criteria are satisfied.

# 86. IMPLEMENTATION PHASES

## Phase 0 — Repository audit

Agent must first:
- inspect existing code
- identify runtime
- identify package managers
- identify current services
- identify existing UI
- identify database
- identify deployment files

Deliver:
```text
REPO_AUDIT.md
```

Do not rewrite code yet.

---

## Phase 1 — Foundation

Implement:

- configuration
- structured logging
- health endpoints
- database
- migrations
- shared models
- OpenAPI base
- Docker Compose

Acceptance:
- services start
- health checks pass
- migrations run
- tests pass

---

## Phase 2 — Camera + video pipeline

Implement:

- file source
- RTSP source
- reconnect logic
- normalized frame abstraction
- basic detector abstraction

Acceptance:
- sample video runs
- detector output visible
- camera health visible

---

## Phase 3 — Tracking + zones

Implement:

- ByteTrack integration
- track lifecycle
- zone CRUD
- point-in-polygon
- crossing event

Acceptance:
- stable IDs visible
- crossing generates correct event

---

## Phase 4 — Event + risk engine

Implement:

- event normalization
- deduplication
- temporal context
- rule-based risk engine
- risk levels
- reason codes

Acceptance:
- same scenario generates repeatable score
- thresholds configurable
- unit tests comprehensive

---

## Phase 5 — Evidence + local response

Implement:

- ring buffer
- snapshot
- clip creation
- local DB
- alert adapter
- dashboard alert stream

Acceptance:
- intrusion creates evidence
- alert appears immediately
- duplicate spam controlled

---

## Phase 6 — Offline + sync

Implement:

- outbox
- retry
- idempotency
- checksums
- reconnect detection
- sync status UI

Acceptance:
- disconnect network
- generate events
- reconnect
- events arrive exactly once logically

---

## Phase 7 — Command dashboard

Implement:

- operations dashboard
- event center
- event details
- map
- camera health
- basic reports

Acceptance:
- a judge can understand system state without developer assistance

---

## Phase 8 — Security hardening

Implement:

- authentication
- RBAC
- audit logs
- secret configuration
- rate limits
- secure headers
- dependency scan

---

## Phase 9 — Optional AI modules

Add only after MVP:

- ANPR
- face
- Re-ID
- behavior model
- anomaly model

Each module must have:
- independent interface
- test fixture
- feature flag
- model version
- fallback behavior

---

## Phase 10 — Benchmark and demo hardening

Measure:
- FPS
- latency
- CPU/GPU
- sync behavior
- offline queue
- event correctness

Produce:
```text
BENCHMARK_REPORT.md
DEMO_RUNBOOK.md
```

---

# 87. AGENT TASK EXECUTION LOOP

When an agent receives a development task:

```text
1. Understand requirement
2. Inspect repository
3. Identify affected modules
4. Define smallest implementation
5. Update contracts/types
6. Implement
7. Write/update tests
8. Run formatter/linter
9. Run type checks
10. Run unit/integration tests
11. Run relevant demo
12. Inspect logs/errors
13. Update docs
14. Summarize exactly what changed
```

Never skip testing because the task appears small.

---

# 88. AGENT IMPLEMENTATION RULES

### Rule 1
Do not introduce a new framework without a concrete benefit.

### Rule 2
Do not duplicate domain logic in frontend and backend.

### Rule 3
Do not mix model inference with DB persistence.

### Rule 4
Do not let UI directly control privileged hardware without authorization.

### Rule 5
Do not store secrets in source code.

### Rule 6
Do not silently swallow exceptions.

### Rule 7
Do not use real external notification credentials in demo mode.

### Rule 8
Do not claim production accuracy from pretrained models.

### Rule 9
Do not make blockchain required for core functionality.

### Rule 10
Do not make internet availability a prerequisite for edge surveillance.

---

# 89. INITIAL RECOMMENDED IMPLEMENTATION STACK

For the fastest path to a convincing prototype:

```text
EDGE
Python
FastAPI
OpenCV
Ultralytics YOLO26n
ByteTrack
SQLite
Local filesystem
WebSocket

CENTRAL
FastAPI
PostgreSQL
Redis optional

FRONTEND
React
TypeScript
Tailwind
Leaflet

INFRA
Docker Compose
Nginx or equivalent reverse proxy

TEST
Pytest
Playwright
frontend unit/component tests

OBSERVABILITY
Structured JSON logs
Prometheus-compatible metrics
Grafana optional
```

For NVIDIA edge hardware:

```text
DeepStream
TensorRT
Jetson
```

can replace/accelerate selected inference components after the base pipeline is validated.

---

# 90. WHY THE MVP SHOULD START WITH RULE-BASED RISK

A production-quality prototype needs explainability and predictability.

Start with:

```text
rule signals
→ weighted score
→ reason codes
```

Then optionally add:

```text
ML score
```

as a second component.

This allows:
- reproducible demos
- easy debugging
- understandable judge explanations
- easier threshold tuning
- lower training burden

---

# 91. WHAT THE FINAL DEMO SHOULD LOOK LIKE

### Screen 1 — Command Dashboard

```text
CRITICAL  2
HIGH      4
MEDIUM    8
CAMERAS  23 / 24 ONLINE
SYNC      ONLINE
```

Map with active events.

### Screen 2 — Live feed

Bounding boxes:

```text
Person #23
Person #31
Vehicle #7
```

Restricted zone overlay.

### Screen 3 — Alert

```text
PERIMETER INTRUSION

Risk: 82 / 100
Level: CRITICAL

Reasons:
✓ Restricted Zone
✓ Night Time
✓ Running

Camera: CAM-04
Site: Demo Border Site
```

### Screen 4 — Event evidence

Snapshot + event clip + timeline.

### Screen 5 — Offline demonstration

```text
CENTRAL: OFFLINE
EDGE: HEALTHY
SYNC QUEUE: 3
LOCAL ALERTS: ACTIVE
```

Then restore connection:

```text
CENTRAL: ONLINE
SYNC QUEUE: 0
```

---

# 92. FINAL JUDGE STORY

The demo narrative should be:

> Existing CCTV is already deployed, but it mostly records video. Our platform adds intelligence locally at the edge. The system detects and tracks objects, understands events such as perimeter intrusion and loitering, combines context such as location and time, and calculates an explainable risk score. High-risk events trigger local alerts immediately. If the internet is unavailable, surveillance continues and evidence is stored locally. When connectivity returns, the platform securely synchronizes important events to the central command center. This makes existing CCTV smarter without replacing it and keeps the system useful even in low-connectivity environments.

---

# 93. IMPORTANT DISTINCTION — SOURCE REQUIREMENT VS OUR ENGINEERING DESIGN

### Officially grounded
- SIH software problem #187
- MHA
- border surveillance
- intelligent video analytics
- existing CCTV infrastructure

### Our proposed engineering design
- edge-first execution
- offline-first operation
- store-and-forward
- risk engine
- virtual zones
- cross-camera correlation
- ANPR
- face recognition
- Re-ID
- anomaly detection
- blockchain integrity
- dashboard architecture
- exact model candidates
- exact risk thresholds

Treat these as **proposed solution elements**, not as official statements from the SIH problem description.

---

# 94. SOURCE / REFERENCE NOTES

Primary project source:
- User-provided `Problem Statements.pdf`, containing SIH 2026 problem statement #187.

Project design references already developed:
- IBVAP architecture diagrams
- IBVAP technology-stack slide
- IBVAP end-to-end product-flow slide
- IBVAP deployment view

Current external technical references to verify during implementation:
- Ultralytics YOLO documentation: https://docs.ultralytics.com/
- Ultralytics YOLO26 documentation: https://docs.ultralytics.com/models/yolo26
- NVIDIA Metropolis / DeepStream documentation: https://docs.nvidia.com/metropolis/
- React documentation: https://react.dev/
- FastAPI documentation: https://fastapi.tiangolo.com/

Technical libraries and APIs can change. During implementation, verify current official documentation rather than relying on copied API snippets from this document.

---

# 95. IMPORTANT MODEL NOTE

YOLO26 is currently a valid Ultralytics model family and is a candidate for the primary detector because of its edge-oriented efficiency and export/deployment options.

However:

> The application architecture must not depend on YOLO26-specific APIs.

The detector must be abstracted so YOLO11, ONNX, TensorRT, a future model, or a mock backend can be substituted.

Also verify the applicable Ultralytics licensing terms before any deployment beyond the intended prototype.

---

# 96. FINAL DEFINITION OF DONE

IBVAP is considered prototype-complete when:

```text
[✓] Existing/simulated CCTV input
[✓] Detection
[✓] Tracking
[✓] Virtual zone
[✓] Intrusion event
[✓] Explainable risk score
[✓] Local storage
[✓] Event evidence
[✓] Local alert
[✓] Dashboard
[✓] Offline operation
[✓] Outbox queue
[✓] Secure synchronization
[✓] Central event view
[✓] Authentication
[✓] RBAC
[✓] Audit logs
[✓] Health monitoring
[✓] Automated tests
[✓] Docker deployment
[✓] Repeatable demo scenario
[✓] Measured benchmark report
[✓] Security/documentation review
```

---

# 97. FINAL ARCHITECTURAL PRINCIPLE

The entire project should be mentally compressed to:

```text
EXISTING CCTV
      ↓
EDGE INTELLIGENCE
      ↓
DETECT
      ↓
TRACK
      ↓
UNDERSTAND
      ↓
CORRELATE
      ↓
RISK SCORE
      ↓
LOCAL ACTION
      ↓
STORE
      ↓
SYNC WHEN AVAILABLE
      ↓
HQ COMMAND
```

The strongest product statement is:

> **IBVAP makes existing CCTV intelligent, keeps security intelligence running locally during connectivity loss, and converts raw video into explainable, actionable security events.**

---

## HANDOFF INSTRUCTION TO ANY FUTURE AI AGENT

When this file is provided to an AI coding agent, the agent should:

1. Treat this document as the primary implementation specification for IBVAP.
2. Preserve the product's edge-first/offline-first architecture.
3. Inspect the actual repository before writing code.
4. Implement the MVP phases in order.
5. Prefer modular interfaces over hard-coded model integrations.
6. Make every important feature testable.
7. Never fabricate benchmark results.
8. Never hardcode secrets.
9. Clearly mark optional/experimental modules.
10. Leave the repository runnable after every completed phase.

The target is **not a fake demo with static screenshots**.

The target is a **real, runnable, production-quality prototype** that can ingest video, detect and track objects, create explainable events, calculate risk, generate evidence and alerts, continue operating offline, synchronize after reconnect, and expose the results through a professional command dashboard.


---

# 98. SPEC CHANGELOG

## 1.1 — Determinism Hardening

Changes added after technical review:

- explicit typed domain schemas
- canonical cross-service contract source
- canonical enum values
- complete 15-signal risk table
- canonical risk thresholds
- deterministic risk boundary tests
- persistent cross-session progress tracking
- pinned toolchain baseline
- lockfile/dependency pinning rules
- explicit coverage requirements
- contract-test requirements
- deterministic demo asset licensing/manifest rules
- clarification that illustrative metrics are not measured results
- explicit override against service-local contract redefinition

Current verified baseline references:
- Python 3.12.14
- Node.js 24.x LTS
- React 19.2.x
- PostgreSQL 17.11

The baseline intentionally does not force every individual library to one patch version in this document; exact dependency resolutions must be captured in repository lockfiles and CI artifacts.
